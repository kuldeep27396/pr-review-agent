from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from pydantic import Field

from pr_review_agent.config import Settings, parse_repo_config
from pr_review_agent.github import GitHubClient
from pr_review_agent.llm import LLMClient
from pr_review_agent.models import (
    AppBaseModel,
    ChangedFile,
    PullRequestContext,
    PullRequestWebhookPayload,
    ReviewOutput,
)
from pr_review_agent.review import ReviewService


class PRReviewGraphState(AppBaseModel):
    payload: PullRequestWebhookPayload
    delivery_id: str
    owner: str = ""
    repo: str = ""
    pr_number: int = 0
    installation_id: int = 0
    installation_token: str | None = None
    pr_context: PullRequestContext | None = None
    effective_settings: Settings | None = None
    include_paths: set[str] | None = None
    files: list[ChangedFile] = Field(default_factory=list)
    review: ReviewOutput | None = None
    skip_processing: bool = False
    skip_reason: str = ""


def route_after_rule_evaluation(state: PRReviewGraphState) -> Literal["determine_incremental_scope", END]:
    if state.skip_processing:
        return END
    return "determine_incremental_scope"


def route_after_incremental_scope(state: PRReviewGraphState) -> Literal["fetch_reviewable_files", END]:
    if state.skip_processing:
        return END
    return "fetch_reviewable_files"


def route_after_file_fetch(state: PRReviewGraphState) -> Literal["generate_review", END]:
    if state.skip_processing or not state.files:
        return END
    return "generate_review"


def route_after_review_generation(state: PRReviewGraphState) -> Literal["post_review", END]:
    if state.skip_processing or state.review is None:
        return END
    return "post_review"


def build_pr_review_graph(
    base_settings: Settings,
    github_client: GitHubClient,
    llm_client: LLMClient,
    logger: Any,
):
    async def initialize_context(state: PRReviewGraphState) -> dict[str, Any]:
        return {
            "owner": state.payload.repository.owner.login,
            "repo": state.payload.repository.name,
            "pr_number": state.payload.pull_request.number,
            "installation_id": state.payload.installation.id,
        }

    async def fetch_installation_token(state: PRReviewGraphState) -> dict[str, Any]:
        token = await github_client.get_installation_token(state.installation_id)
        return {"installation_token": token}

    async def fetch_pull_request_context(state: PRReviewGraphState) -> dict[str, Any]:
        pr_context = await github_client.get_pull_request(
            state.owner,
            state.repo,
            state.pr_number,
            state.installation_token,
        )
        return {"pr_context": pr_context}

    async def resolve_effective_settings(state: PRReviewGraphState) -> dict[str, Any]:
        repo_config_text = await github_client.get_repo_config_text(
            state.owner,
            state.repo,
            state.pr_context.head_sha,
            state.installation_token,
        )
        if not repo_config_text:
            return {"effective_settings": base_settings}
        try:
            effective_settings = base_settings.with_overrides(parse_repo_config(repo_config_text))
        except Exception:
            logger.exception("Failed parsing repo config owner=%s repo=%s", state.owner, state.repo)
            effective_settings = base_settings
        return {"effective_settings": effective_settings}

    async def apply_pr_rules(state: PRReviewGraphState) -> dict[str, Any]:
        pr_text = f"{state.pr_context.title}\n{state.pr_context.body}"
        effective_settings = state.effective_settings

        if effective_settings.should_ignore_pr(pr_text):
            logger.info(
                "Ignoring PR by keyword owner=%s repo=%s pr=%s",
                state.owner,
                state.repo,
                state.pr_number,
            )
            return {"skip_processing": True, "skip_reason": "ignored by keyword"}

        if effective_settings.is_summary_only(pr_text):
            effective_settings = effective_settings.with_overrides({"max_comments_per_review": 0})

        return {"effective_settings": effective_settings}

    async def determine_incremental_scope(state: PRReviewGraphState) -> dict[str, Any]:
        if not state.effective_settings.enable_incremental_reviews:
            return {}

        latest_commit = await github_client.get_latest_agent_review_commit(
            state.owner,
            state.repo,
            state.pr_number,
            state.installation_token,
        )
        if latest_commit == state.pr_context.head_sha:
            logger.info(
                "Skipping duplicate reviewed commit owner=%s repo=%s pr=%s",
                state.owner,
                state.repo,
                state.pr_number,
            )
            return {"skip_processing": True, "skip_reason": "already reviewed commit"}

        if not latest_commit:
            return {}

        try:
            include_paths = await github_client.compare_filenames(
                state.owner,
                state.repo,
                latest_commit,
                state.pr_context.head_sha,
                state.installation_token,
            )
            return {"include_paths": include_paths}
        except Exception:
            logger.exception(
                "Incremental compare failed; falling back to full PR review owner=%s repo=%s pr=%s",
                state.owner,
                state.repo,
                state.pr_number,
            )
            return {"include_paths": None}

    async def fetch_reviewable_files(state: PRReviewGraphState) -> dict[str, Any]:
        files = await github_client.get_reviewable_files(
            state.owner,
            state.repo,
            state.pr_context,
            state.installation_token,
            review_settings=state.effective_settings,
            include_paths=state.include_paths,
        )
        if not files:
            logger.info("No reviewable files found for %s/%s#%s", state.owner, state.repo, state.pr_number)
            return {"files": [], "skip_processing": True, "skip_reason": "no reviewable files"}
        return {"files": files}

    async def generate_review(state: PRReviewGraphState) -> dict[str, Any]:
        review_service = ReviewService(state.effective_settings, llm_client, logger)
        review = await review_service.review_pull_request(state.files, state.pr_context)
        if review is None:
            logger.info("No review generated for %s/%s#%s", state.owner, state.repo, state.pr_number)
            return {"skip_processing": True, "skip_reason": "no review generated"}

        total_issues = sum(len(analysis.issues) for analysis in review.analyses)
        if total_issues == 0 and not state.effective_settings.post_review_summary:
            logger.info(
                "Clean review for %s/%s#%s; summary posting disabled",
                state.owner,
                state.repo,
                state.pr_number,
            )
            return {"review": review, "skip_processing": True, "skip_reason": "clean review without summary"}

        return {"review": review}

    async def post_review(state: PRReviewGraphState) -> dict[str, Any]:
        await github_client.post_review(
            state.owner,
            state.repo,
            state.pr_number,
            state.review,
            state.installation_token,
            state.pr_context.head_sha,
        )
        logger.info(
            "Posted review owner=%s repo=%s pr=%s event=%s inline_comments=%s",
            state.owner,
            state.repo,
            state.pr_number,
            state.review.event,
            len(state.review.comments),
        )
        return {}

    builder = StateGraph(PRReviewGraphState)
    builder.add_node("initialize_context", initialize_context)
    builder.add_node("fetch_installation_token", fetch_installation_token)
    builder.add_node("fetch_pull_request_context", fetch_pull_request_context)
    builder.add_node("resolve_effective_settings", resolve_effective_settings)
    builder.add_node("apply_pr_rules", apply_pr_rules)
    builder.add_node("determine_incremental_scope", determine_incremental_scope)
    builder.add_node("fetch_reviewable_files", fetch_reviewable_files)
    builder.add_node("generate_review", generate_review)
    builder.add_node("post_review", post_review)

    builder.add_edge(START, "initialize_context")
    builder.add_edge("initialize_context", "fetch_installation_token")
    builder.add_edge("fetch_installation_token", "fetch_pull_request_context")
    builder.add_edge("fetch_pull_request_context", "resolve_effective_settings")
    builder.add_edge("resolve_effective_settings", "apply_pr_rules")
    builder.add_conditional_edges("apply_pr_rules", route_after_rule_evaluation)
    builder.add_conditional_edges("determine_incremental_scope", route_after_incremental_scope)
    builder.add_conditional_edges("fetch_reviewable_files", route_after_file_fetch)
    builder.add_conditional_edges("generate_review", route_after_review_generation)
    builder.add_edge("post_review", END)

    return builder.compile()
