from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from pr_review_agent.app_context import AppContext
from pr_review_agent.models import (
    ChangedFile,
    PullRequestWebhookPayload,
    ReviewCommentContext,
    ReviewCommentWebhookPayload,
)
from pr_review_agent.pr_review_graph import PRReviewGraphState


class WebhookHandler:
    def __init__(self, context: AppContext) -> None:
        self.context = context

    def root_response(self) -> JSONResponse:
        payload: dict[str, Any] = {
            "name": "GitHub PR Review Agent",
            "description": "Automated PR reviews powered by Python",
            "status": "running",
            "runtime": "python",
        }
        missing = self.context.settings.missing_runtime_variables()
        if missing:
            payload["configuration"] = {
                "status": "incomplete",
                "missing": list(missing),
            }
        return JSONResponse(
            payload
        )

    def health_response(self) -> JSONResponse:
        missing = self.context.settings.missing_runtime_variables()
        status = "healthy" if not missing else "degraded"
        status_code = 200 if not missing else 503
        return JSONResponse(
            {
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "missing_configuration": list(missing),
            },
            status_code=status_code,
        )

    async def handle_webhook(self, request: Request) -> JSONResponse:
        missing = self.context.settings.missing_runtime_variables()
        if missing:
            return JSONResponse(
                {
                    "status": "error",
                    "reason": "runtime not configured",
                    "missing_configuration": list(missing),
                },
                status_code=503,
            )

        body = await request.body()
        signature = request.headers.get("x-hub-signature-256")
        event = request.headers.get("x-github-event")
        delivery_id = request.headers.get("x-github-delivery", "unknown")

        if not self.context.verify_signature(body, signature):
            raise HTTPException(status_code=401, detail="Unauthorized")

        self.context.prune_deliveries()
        if self.context.is_duplicate_delivery(delivery_id):
            return JSONResponse({"status": "ignored", "reason": "duplicate delivery"})

        self.context.logger.info("Received GitHub event=%s delivery=%s", event, delivery_id)

        if event == "pull_request":
            payload = self._parse_payload(PullRequestWebhookPayload, body, "Invalid pull_request payload")
            if payload.action not in self.context.settings.webhook_actions:
                return JSONResponse({"status": "ignored", "reason": f"unsupported action: {payload.action}"})
            self.context.track_delivery(delivery_id)
            asyncio.create_task(self.process_pull_request_event(payload, delivery_id))
            return JSONResponse({"status": "accepted"})

        if event == "pull_request_review_comment":
            payload = self._parse_payload(
                ReviewCommentWebhookPayload,
                body,
                "Invalid pull_request_review_comment payload",
            )
            if payload.action != "created":
                return JSONResponse({"status": "ignored", "reason": f"unsupported action: {payload.action}"})
            self.context.track_delivery(delivery_id)
            asyncio.create_task(self.process_review_comment_event(payload, delivery_id))
            return JSONResponse({"status": "accepted"})

        return JSONResponse({"status": "ignored", "reason": f"unsupported event: {event}"})

    @staticmethod
    def _parse_payload(model, body: bytes, error_detail: str):
        try:
            return model.model_validate_json(body)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=error_detail) from exc

    async def process_pull_request_event(
        self,
        payload: PullRequestWebhookPayload,
        delivery_id: str,
    ) -> None:
        owner = payload.repository.owner.login
        repo = payload.repository.name
        pr_number = payload.pull_request.number

        try:
            await self.context.pr_review_graph.ainvoke(
                PRReviewGraphState(payload=payload, delivery_id=delivery_id)
            )
        except Exception:
            self.context.clear_delivery(delivery_id)
            self.context.logger.exception("Failed processing %s/%s#%s", owner, repo, pr_number)

    async def process_review_comment_event(
        self,
        payload: ReviewCommentWebhookPayload,
        delivery_id: str,
    ) -> None:
        owner = payload.repository.owner.login
        repo = payload.repository.name
        pr_number = payload.pull_request.number
        installation_id = payload.installation.id

        try:
            if payload.comment.user.type == "Bot":
                return

            installation_token = await self.context.github_client.get_installation_token(installation_id)
            pr_context = await self.context.github_client.get_pull_request(
                owner,
                repo,
                pr_number,
                installation_token,
            )
            effective_settings = await self.context.resolve_effective_settings(
                owner,
                repo,
                pr_context.head_sha,
                installation_token,
            )
            if not effective_settings.enable_conversation:
                return
            if not effective_settings.is_bot_mentioned(payload.comment.body):
                return

            path = payload.comment.path
            content = ""
            if path:
                content = (
                    await self.context.github_client.get_optional_file_content(
                        owner,
                        repo,
                        path,
                        pr_context.head_sha,
                        installation_token,
                    )
                    or ""
                )

            review_service = self.context.create_review_service(effective_settings)
            reply = await review_service.answer_review_comment(
                ReviewCommentContext(
                    comment_id=payload.comment.id,
                    body=payload.comment.body,
                    path=path,
                    diff_hunk=payload.comment.diff_hunk,
                    line=payload.comment.line,
                    user_login=payload.comment.user.login,
                ),
                pr_context,
                ChangedFile(
                    path=path,
                    status="modified",
                    additions=0,
                    deletions=0,
                    patch=payload.comment.diff_hunk,
                    content=content,
                ),
            )
            await self.context.github_client.reply_to_review_comment(
                owner,
                repo,
                pr_number,
                payload.comment.id,
                reply,
                installation_token,
            )
            self.context.logger.info(
                "Posted conversational reply owner=%s repo=%s pr=%s",
                owner,
                repo,
                pr_number,
            )
        except Exception:
            self.context.clear_delivery(delivery_id)
            self.context.logger.exception(
                "Failed processing review comment owner=%s repo=%s pr=%s",
                owner,
                repo,
                pr_number,
            )
