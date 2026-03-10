from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

from pr_review_agent.config import Settings, get_settings, parse_repo_config
from pr_review_agent.github import GitHubClient
from pr_review_agent.llm import LLMClient
from pr_review_agent.logging_utils import configure_logging
from pr_review_agent.pr_review_graph import build_pr_review_graph
from pr_review_agent.review import ReviewService


class AppContext:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.logger = configure_logging(self.settings.log_level, self.settings.log_format)
        self.github_client = GitHubClient(self.settings, self.logger)
        self.llm_client = LLMClient(self.settings, self.logger)
        self.pr_review_graph = build_pr_review_graph(
            self.settings,
            self.github_client,
            self.llm_client,
            self.logger,
        )
        self._processed_deliveries: dict[str, float] = {}

    async def close(self) -> None:
        await self.github_client.aclose()
        await self.llm_client.aclose()

    def verify_signature(self, payload: bytes, signature: str | None) -> bool:
        if not signature or not self.settings.github_webhook_secret:
            return False
        digest = hmac.new(
            self.settings.github_webhook_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(signature, f"sha256={digest}")

    def prune_deliveries(self) -> None:
        cutoff = time.monotonic() - self.settings.delivery_ttl_seconds
        expired = [delivery_id for delivery_id, seen_at in self._processed_deliveries.items() if seen_at < cutoff]
        for delivery_id in expired:
            self._processed_deliveries.pop(delivery_id, None)

    def is_duplicate_delivery(self, delivery_id: str) -> bool:
        return delivery_id in self._processed_deliveries

    def track_delivery(self, delivery_id: str) -> None:
        self._processed_deliveries[delivery_id] = time.monotonic()

    def clear_delivery(self, delivery_id: str) -> None:
        self._processed_deliveries.pop(delivery_id, None)

    async def resolve_effective_settings(
        self,
        owner: str,
        repo: str,
        ref: str,
        installation_token: str,
    ) -> Settings:
        repo_config_text = await self.github_client.get_repo_config_text(owner, repo, ref, installation_token)
        if not repo_config_text:
            return self.settings
        try:
            return self.settings.with_overrides(parse_repo_config(repo_config_text))
        except Exception:
            self.logger.exception("Failed parsing repo config owner=%s repo=%s", owner, repo)
            return self.settings

    def create_review_service(self, settings: Settings | None = None) -> ReviewService:
        return ReviewService(settings or self.settings, self.llm_client, self.logger)
