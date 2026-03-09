from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_REVIEWABLE_EXTENSIONS = frozenset(
    {
        ".c",
        ".cpp",
        ".cs",
        ".css",
        ".dart",
        ".go",
        ".h",
        ".html",
        ".java",
        ".js",
        ".json",
        ".jsx",
        ".kt",
        ".less",
        ".php",
        ".py",
        ".r",
        ".rb",
        ".rs",
        ".scala",
        ".scss",
        ".sh",
        ".sql",
        ".svelte",
        ".swift",
        ".ts",
        ".tsx",
        ".vue",
        ".xml",
        ".yaml",
        ".yml",
    }
)


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    parts = [item.strip() for item in value.split(",")]
    return tuple(item for item in parts if item)


def _parse_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def _load_dotenv_file(path: str = ".env") -> None:
    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _parse_env_value(raw_value)


_load_dotenv_file()


@dataclass(frozen=True)
class Settings:
    github_app_id: str | None
    github_private_key: str | None
    github_webhook_secret: str | None
    groq_api_key: str | None
    openai_api_key: str | None
    llm_provider: str
    fallback_llm_provider: str | None
    review_model: str
    summary_model: str | None
    fallback_review_model: str | None
    fallback_summary_model: str | None
    port: int
    environment: str
    log_level: str
    log_format: str
    max_files_to_review: int
    max_file_size_kb: int
    review_timeout_ms: int
    max_patch_chars: int
    max_file_context_chars: int
    max_comments_per_review: int
    review_simple_changes: bool
    post_review_summary: bool
    enable_incremental_reviews: bool
    enable_conversation: bool
    enable_test_plan: bool
    config_file_path: str
    delivery_ttl_seconds: int
    include_patterns: tuple[str, ...] = field(default_factory=tuple)
    exclude_patterns: tuple[str, ...] = field(default_factory=tuple)
    bot_aliases: tuple[str, ...] = field(default_factory=tuple)
    ignore_keywords: tuple[str, ...] = field(default_factory=tuple)
    summary_only_keywords: tuple[str, ...] = field(default_factory=tuple)
    generated_markers: tuple[str, ...] = field(default_factory=tuple)
    request_parallelism: int = 3
    webhook_actions: tuple[str, ...] = field(default_factory=tuple)
    reviewable_extensions: frozenset[str] = DEFAULT_REVIEWABLE_EXTENSIONS
    fallback_groq_api_key: str | None = None
    fallback_openai_api_key: str | None = None

    @property
    def api_key(self) -> str | None:
        if self.llm_provider == "groq":
            return self.groq_api_key
        if self.llm_provider == "openai":
            return self.openai_api_key
        return None

    @property
    def fallback_api_key(self) -> str | None:
        if self.fallback_llm_provider == "groq":
            return self.fallback_groq_api_key or self.groq_api_key
        if self.fallback_llm_provider == "openai":
            return self.fallback_openai_api_key or self.openai_api_key
        return None

    @property
    def normalized_private_key(self) -> str | None:
        if not self.github_private_key:
            return None
        return self.github_private_key.replace("\\n", "\n")

    @property
    def resolved_summary_model(self) -> str:
        return self.summary_model or self.review_model

    @property
    def resolved_fallback_review_model(self) -> str:
        return self.fallback_review_model or self.review_model

    @property
    def resolved_fallback_summary_model(self) -> str:
        return self.fallback_summary_model or self.resolved_summary_model

    def validate_runtime(self) -> None:
        missing = []
        if not self.github_app_id:
            missing.append("GITHUB_APP_ID")
        if not self.github_private_key:
            missing.append("GITHUB_PRIVATE_KEY")
        if not self.github_webhook_secret:
            missing.append("GITHUB_WEBHOOK_SECRET")
        if not self.api_key:
            missing.append("GROQ_API_KEY" if self.llm_provider == "groq" else "OPENAI_API_KEY")
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        if self.llm_provider not in {"groq", "openai"}:
            raise ValueError("LLM_PROVIDER must be one of: groq, openai")
        if self.fallback_llm_provider and self.fallback_llm_provider not in {"groq", "openai"}:
            raise ValueError("FALLBACK_LLM_PROVIDER must be one of: groq, openai")

    def should_review_path(self, path: str) -> bool:
        suffix = Path(path).suffix.lower()
        if suffix not in self.reviewable_extensions:
            return False
        if self.include_patterns and not any(Path(path).match(pattern) for pattern in self.include_patterns):
            return False
        if any(Path(path).match(pattern) for pattern in self.exclude_patterns):
            return False
        return True

    def should_ignore_pr(self, text: str) -> bool:
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in self.ignore_keywords)

    def is_summary_only(self, text: str) -> bool:
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in self.summary_only_keywords)

    def is_bot_mentioned(self, text: str) -> bool:
        lowered = text.lower()
        return any(alias.lower() in lowered for alias in self.bot_aliases)

    def with_overrides(self, overrides: dict[str, Any]) -> "Settings":
        allowed = {
            "review_model",
            "summary_model",
            "fallback_review_model",
            "fallback_summary_model",
            "max_files_to_review",
            "max_comments_per_review",
            "review_simple_changes",
            "post_review_summary",
            "enable_incremental_reviews",
            "enable_conversation",
            "enable_test_plan",
            "include_patterns",
            "exclude_patterns",
            "ignore_keywords",
            "summary_only_keywords",
            "bot_aliases",
            "generated_markers",
        }
        normalized: dict[str, Any] = {}
        for key, value in overrides.items():
            if key not in allowed or value is None:
                continue
            if key in {
                "include_patterns",
                "exclude_patterns",
                "ignore_keywords",
                "summary_only_keywords",
                "bot_aliases",
                "generated_markers",
            }:
                if isinstance(value, str):
                    normalized[key] = _parse_csv(value)
                else:
                    normalized[key] = tuple(str(item).strip() for item in value if str(item).strip())
            else:
                normalized[key] = value
        return replace(self, **normalized)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        github_app_id=os.getenv("GITHUB_APP_ID"),
        github_private_key=os.getenv("GITHUB_PRIVATE_KEY"),
        github_webhook_secret=os.getenv("GITHUB_WEBHOOK_SECRET"),
        groq_api_key=os.getenv("GROQ_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        llm_provider=os.getenv("LLM_PROVIDER", "groq").strip().lower(),
        fallback_llm_provider=os.getenv("FALLBACK_LLM_PROVIDER", "").strip().lower() or None,
        review_model=os.getenv("REVIEW_MODEL", "llama-3.3-70b-versatile"),
        summary_model=os.getenv("SUMMARY_MODEL"),
        fallback_review_model=os.getenv("FALLBACK_REVIEW_MODEL"),
        fallback_summary_model=os.getenv("FALLBACK_SUMMARY_MODEL"),
        port=int(os.getenv("PORT", "3000")),
        environment=os.getenv("NODE_ENV", "production"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_format=os.getenv("LOG_FORMAT", "plain").lower(),
        max_files_to_review=int(os.getenv("MAX_FILES_TO_REVIEW", "10")),
        max_file_size_kb=int(os.getenv("MAX_FILE_SIZE_KB", "100")),
        review_timeout_ms=int(os.getenv("REVIEW_TIMEOUT_MS", "30000")),
        max_patch_chars=int(os.getenv("MAX_PATCH_CHARS", "12000")),
        max_file_context_chars=int(os.getenv("MAX_FILE_CONTEXT_CHARS", "8000")),
        max_comments_per_review=int(os.getenv("MAX_COMMENTS_PER_REVIEW", "20")),
        review_simple_changes=_parse_bool(os.getenv("REVIEW_SIMPLE_CHANGES"), False),
        post_review_summary=_parse_bool(os.getenv("POST_REVIEW_SUMMARY"), True),
        enable_incremental_reviews=_parse_bool(os.getenv("ENABLE_INCREMENTAL_REVIEWS"), True),
        enable_conversation=_parse_bool(os.getenv("ENABLE_CONVERSATION"), True),
        enable_test_plan=_parse_bool(os.getenv("ENABLE_TEST_PLAN"), True),
        config_file_path=os.getenv("CONFIG_FILE_PATH", ".pr_review_agent.toml"),
        delivery_ttl_seconds=int(os.getenv("DELIVERY_TTL_SECONDS", "900")),
        include_patterns=_parse_csv(os.getenv("INCLUDE_PATTERNS")),
        exclude_patterns=_parse_csv(
            os.getenv(
                "EXCLUDE_PATTERNS",
                "*.lock,package-lock.json,pnpm-lock.yaml,yarn.lock",
            )
        ),
        bot_aliases=_parse_csv(os.getenv("BOT_ALIASES", "@pr-review-agent,@agent")),
        ignore_keywords=_parse_csv(os.getenv("IGNORE_KEYWORDS", "@agent ignore,@pr-review-agent ignore")),
        summary_only_keywords=_parse_csv(
            os.getenv("SUMMARY_ONLY_KEYWORDS", "@agent summary-only,@pr-review-agent summary-only")
        ),
        generated_markers=_parse_csv(
            os.getenv(
                "GENERATED_MARKERS",
                "@generated,generated by,auto-generated,automatically generated,do not edit",
            )
        ),
        request_parallelism=max(1, int(os.getenv("REQUEST_PARALLELISM", "3"))),
        webhook_actions=_parse_csv(
            os.getenv(
                "WEBHOOK_ACTIONS",
                "opened,synchronize,reopened,ready_for_review",
            )
        ),
        fallback_groq_api_key=os.getenv("FALLBACK_GROQ_API_KEY"),
        fallback_openai_api_key=os.getenv("FALLBACK_OPENAI_API_KEY"),
    )


def parse_repo_config(content: str) -> dict[str, Any]:
    data = tomllib.loads(content)
    section = data.get("review") or data.get("pr_review_agent") or data
    if not isinstance(section, dict):
        return {}
    return section
