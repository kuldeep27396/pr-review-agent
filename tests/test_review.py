import unittest

from pr_review_agent.config import Settings, parse_repo_config
from pr_review_agent.models import ChangedFile, LLMReviewResponse, PullRequestWebhookPayload
from pr_review_agent.review import ReviewService, extract_added_lines


class DummySettings:
    review_simple_changes = False


class ReviewTests(unittest.TestCase):
    def test_repo_config_parser(self) -> None:
        parsed = parse_repo_config(
            """
[review]
max_comments_per_review = 5
ignore_keywords = ["@agent ignore"]
"""
        )
        self.assertEqual(parsed["max_comments_per_review"], 5)
        self.assertEqual(parsed["ignore_keywords"], ["@agent ignore"])

    def test_settings_overrides_and_keywords(self) -> None:
        base = Settings(
            github_app_id=None,
            github_private_key=None,
            github_webhook_secret=None,
            groq_api_key=None,
            openai_api_key=None,
            llm_provider="groq",
            fallback_llm_provider=None,
            review_model="a",
            summary_model=None,
            fallback_review_model=None,
            fallback_summary_model=None,
            port=3000,
            environment="test",
            log_level="INFO",
            log_format="plain",
            max_files_to_review=10,
            max_file_size_kb=100,
            review_timeout_ms=30000,
            max_patch_chars=100,
            max_file_context_chars=100,
            max_comments_per_review=20,
            review_simple_changes=False,
            post_review_summary=True,
            enable_incremental_reviews=True,
            enable_conversation=True,
            enable_test_plan=True,
            config_file_path=".pr_review_agent.toml",
            delivery_ttl_seconds=10,
            include_patterns=(),
            exclude_patterns=(),
            bot_aliases=("@agent",),
            ignore_keywords=("@agent ignore",),
            summary_only_keywords=("@agent summary-only",),
            generated_markers=("@generated",),
        )
        updated = base.with_overrides(
            {
                "max_comments_per_review": 5,
                "ignore_keywords": ["skip this"],
            }
        )
        self.assertEqual(updated.max_comments_per_review, 5)
        self.assertTrue(updated.should_ignore_pr("please skip this pr"))
        self.assertTrue(updated.is_bot_mentioned("@agent please explain"))

    def test_extract_added_lines_tracks_new_file_positions(self) -> None:
        patch = """@@ -1,2 +1,4 @@
+import os
+import sys
+value = 1
+print(value)
"""
        self.assertEqual(extract_added_lines(patch), {1, 2, 3, 4})

    def test_extract_added_lines_handles_mixed_hunks(self) -> None:
        patch = """@@ -10,3 +10,4 @@
 context
-old_line
+new_line = True
 kept = call()
+if new_line:
+    run()
"""
        self.assertEqual(extract_added_lines(patch), {11, 13, 14})

    def test_simple_change_skip_logic(self) -> None:
        file = ChangedFile(
            path="src/example.py",
            status="modified",
            additions=1,
            deletions=1,
            patch="""@@ -1 +1 @@
- old
+ new
""",
            content="new",
        )
        service = ReviewService.__new__(ReviewService)
        service.settings = DummySettings()
        self.assertTrue(service._should_skip_simple_change(file))

    def test_llm_review_response_parses_type_alias(self) -> None:
        parsed = LLMReviewResponse.model_validate_json(
            """
{"assessment":"COMMENT","summary":"ok","issues":[{"line":4,"type":"bug","severity":"high","message":"bad","suggestion":"fix"}]}
"""
        )
        self.assertEqual(parsed.issues[0].issue_type, "bug")

    def test_pull_request_webhook_payload_parses_nested_context(self) -> None:
        payload = PullRequestWebhookPayload.model_validate(
            {
                "action": "opened",
                "pull_request": {
                    "number": 7,
                    "title": "Test",
                    "body": "Body",
                    "html_url": "https://example.com/pr/7",
                    "head": {"sha": "abc123", "ref": "feature"},
                },
                "repository": {"name": "repo", "owner": {"login": "owner"}},
                "installation": {"id": 99},
            }
        )
        context = payload.pull_request.to_context()
        self.assertEqual(context.head_sha, "abc123")
        self.assertEqual(payload.repository.owner.login, "owner")


if __name__ == "__main__":
    unittest.main()
