from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from datetime import datetime, timezone
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from pr_review_agent.config import get_settings, parse_repo_config
from pr_review_agent.github import GitHubClient
from pr_review_agent.llm import LLMClient
from pr_review_agent.logging_utils import configure_logging
from pr_review_agent.models import ChangedFile, ReviewCommentContext
from pr_review_agent.review import ReviewService


settings = get_settings()
logger = configure_logging(settings.log_level, settings.log_format)
github_client = GitHubClient(settings, logger)
llm_client = LLMClient(settings, logger)
processed_deliveries: dict[str, float] = {}

app = FastAPI(title="GitHub PR Review Agent", version="2.0.0")


def verify_signature(payload: bytes, signature: str | None) -> bool:
    if not signature or not settings.github_webhook_secret:
        return False
    digest = hmac.new(
        settings.github_webhook_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(signature, expected)


@app.on_event("startup")
async def on_startup() -> None:
    settings.validate_runtime()
    logger.info("Starting Python PR review agent")
    logger.info("Environment: %s", settings.environment)
    logger.info("LLM provider: %s", settings.llm_provider)
    logger.info("Review model: %s", settings.review_model)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await github_client.aclose()
    await llm_client.aclose()


@app.get("/")
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "name": "GitHub PR Review Agent",
            "description": "Automated PR reviews powered by Python",
            "status": "running",
            "runtime": "python",
        }
    )


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.post("/webhook")
async def webhook(request: Request) -> JSONResponse:
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256")
    event = request.headers.get("x-github-event")
    delivery_id = request.headers.get("x-github-delivery", "unknown")

    if not verify_signature(body, signature):
        raise HTTPException(status_code=401, detail="Unauthorized")

    _prune_deliveries()
    if delivery_id in processed_deliveries:
        return JSONResponse({"status": "ignored", "reason": "duplicate delivery"})

    payload = await request.json()
    logger.info("Received GitHub event=%s delivery=%s", event, delivery_id)

    if event == "pull_request":
        action = payload.get("action")
        if action not in settings.webhook_actions:
            return JSONResponse({"status": "ignored", "reason": f"unsupported action: {action}"})
        processed_deliveries[delivery_id] = time.monotonic()
        asyncio.create_task(process_pull_request_event(payload, delivery_id))
        return JSONResponse({"status": "accepted"})

    if event == "pull_request_review_comment":
        action = payload.get("action")
        if action != "created":
            return JSONResponse({"status": "ignored", "reason": f"unsupported action: {action}"})
        processed_deliveries[delivery_id] = time.monotonic()
        asyncio.create_task(process_review_comment_event(payload, delivery_id))
        return JSONResponse({"status": "accepted"})

    return JSONResponse({"status": "ignored", "reason": f"unsupported event: {event}"})


def _prune_deliveries() -> None:
    cutoff = time.monotonic() - settings.delivery_ttl_seconds
    expired = [delivery_id for delivery_id, seen_at in processed_deliveries.items() if seen_at < cutoff]
    for delivery_id in expired:
        processed_deliveries.pop(delivery_id, None)


async def _resolve_effective_settings(
    owner: str,
    repo: str,
    head_ref: str,
    installation_token: str,
) -> Any:
    repo_config_text = await github_client.get_repo_config_text(owner, repo, head_ref, installation_token)
    if not repo_config_text:
        return settings
    try:
        return settings.with_overrides(parse_repo_config(repo_config_text))
    except Exception:
        logger.exception("Failed parsing repo config owner=%s repo=%s", owner, repo)
        return settings


async def process_pull_request_event(payload: dict[str, Any], delivery_id: str) -> None:
    pull_request = payload["pull_request"]
    repository = payload["repository"]
    installation = payload["installation"]

    owner = repository["owner"]["login"]
    repo = repository["name"]
    pr_number = pull_request["number"]
    installation_id = installation["id"]

    try:
        installation_token = await github_client.get_installation_token(installation_id)
        pr_context = await github_client.get_pull_request(owner, repo, pr_number, installation_token)
        effective_settings = await _resolve_effective_settings(owner, repo, pr_context.head_sha, installation_token)
        pr_text = f"{pr_context.title}\n{pr_context.body}"

        if effective_settings.should_ignore_pr(pr_text):
            logger.info("Ignoring PR by keyword owner=%s repo=%s pr=%s", owner, repo, pr_number)
            return

        if effective_settings.is_summary_only(pr_text):
            effective_settings = effective_settings.with_overrides({"max_comments_per_review": 0})

        include_paths: set[str] | None = None
        if effective_settings.enable_incremental_reviews:
            latest_commit = await github_client.get_latest_agent_review_commit(owner, repo, pr_number, installation_token)
            if latest_commit == pr_context.head_sha:
                logger.info("Skipping duplicate reviewed commit owner=%s repo=%s pr=%s", owner, repo, pr_number)
                return
            if latest_commit:
                try:
                    include_paths = await github_client.compare_filenames(
                        owner,
                        repo,
                        latest_commit,
                        pr_context.head_sha,
                        installation_token,
                    )
                except Exception:
                    logger.exception(
                        "Incremental compare failed; falling back to full PR review owner=%s repo=%s pr=%s",
                        owner,
                        repo,
                        pr_number,
                    )
                    include_paths = None

        files = await github_client.get_reviewable_files(
            owner,
            repo,
            pr_context,
            installation_token,
            review_settings=effective_settings,
            include_paths=include_paths,
        )

        if not files:
            logger.info("No reviewable files found for %s/%s#%s", owner, repo, pr_number)
            return

        review_service = ReviewService(effective_settings, llm_client, logger)
        review = await review_service.review_pull_request(files, pr_context)
        if review is None:
            logger.info("No review generated for %s/%s#%s", owner, repo, pr_number)
            return

        total_issues = sum(len(analysis.issues) for analysis in review.analyses)
        if total_issues == 0 and not settings.post_review_summary:
            logger.info("Clean review for %s/%s#%s; summary posting disabled", owner, repo, pr_number)
            return

        await github_client.post_review(owner, repo, pr_number, review, installation_token, pr_context.head_sha)
        logger.info(
            "Posted review owner=%s repo=%s pr=%s event=%s inline_comments=%s",
            owner,
            repo,
            pr_number,
            review.event,
            len(review.comments),
        )
    except Exception:
        processed_deliveries.pop(delivery_id, None)
        logger.exception("Failed processing %s/%s#%s", owner, repo, pr_number)


async def process_review_comment_event(payload: dict[str, Any], delivery_id: str) -> None:
    repository = payload["repository"]
    installation = payload["installation"]
    comment = payload["comment"]
    pull_request = payload["pull_request"]

    owner = repository["owner"]["login"]
    repo = repository["name"]
    pr_number = pull_request["number"]
    installation_id = installation["id"]

    try:
        if comment.get("user", {}).get("type") == "Bot":
            return

        installation_token = await github_client.get_installation_token(installation_id)
        pr_context = await github_client.get_pull_request(owner, repo, pr_number, installation_token)
        effective_settings = await _resolve_effective_settings(owner, repo, pr_context.head_sha, installation_token)
        if not effective_settings.enable_conversation:
            return
        if not effective_settings.is_bot_mentioned(comment.get("body", "")):
            return

        path = comment.get("path") or ""
        content = ""
        if path:
            content = (
                await github_client.get_optional_file_content(
                    owner,
                    repo,
                    path,
                    pr_context.head_sha,
                    installation_token,
                )
                or ""
            )

        review_service = ReviewService(effective_settings, llm_client, logger)
        reply = await review_service.answer_review_comment(
            ReviewCommentContext(
                comment_id=comment["id"],
                body=comment.get("body", ""),
                path=path,
                diff_hunk=comment.get("diff_hunk") or "",
                line=comment.get("line"),
                user_login=comment.get("user", {}).get("login", ""),
            ),
            pr_context,
            ChangedFile(
                path=path,
                status="modified",
                additions=0,
                deletions=0,
                patch=comment.get("diff_hunk") or "",
                content=content,
            ),
        )
        await github_client.reply_to_review_comment(
            owner,
            repo,
            pr_number,
            comment["id"],
            reply,
            installation_token,
        )
        logger.info("Posted conversational reply owner=%s repo=%s pr=%s", owner, repo, pr_number)
    except Exception:
        processed_deliveries.pop(delivery_id, None)
        logger.exception("Failed processing review comment owner=%s repo=%s pr=%s", owner, repo, pr_number)


def run() -> None:
    uvicorn.run("pr_review_agent.main:app", host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    run()
