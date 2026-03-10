import unittest

from pr_review_agent.config import Settings, parse_repo_config
from pr_review_agent.github import GitHubClient
from pr_review_agent.models import (
    ChangedFile,
    FileReview,
    GitHubPullRequest,
    IssueCommentWebhookPayload,
    LLMReviewResponse,
    PullRequestWebhookPayload,
    ReviewIssue,
    ReviewOutput,
)
from pr_review_agent.pr_review_graph import (
    PRReviewGraphState,
    route_after_file_fetch,
    route_after_incremental_scope,
    route_after_review_generation,
    route_after_rule_evaluation,
)
from pr_review_agent.review import ReviewService, extract_added_lines


class DummySettings:
    review_simple_changes = False
    enable_test_plan = True


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
        self.assertEqual(updated.extract_staff_review_prompt("/staff-review explain this"), "explain this")
        self.assertEqual(updated.extract_staff_review_prompt("/staff-review"), "")
        self.assertIsNone(updated.extract_staff_review_prompt("@agent explain this"))

    def test_private_key_normalization_handles_wrapped_and_escaped_pem(self) -> None:
        settings = Settings(
            github_app_id="1",
            github_private_key='"-----BEGIN RSA PRIVATE KEY-----\\nline-1\\nline-2\\n-----END RSA PRIVATE KEY-----\\n"',
            github_webhook_secret="secret",
            groq_api_key="key",
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
            staff_review_commands=("/staff-review",),
            generated_markers=("@generated",),
        )
        self.assertEqual(
            settings.normalized_private_key,
            "-----BEGIN RSA PRIVATE KEY-----\nline-1\nline-2\n-----END RSA PRIVATE KEY-----",
        )

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

    def test_structured_summary_includes_merge_recommendation_and_file_table(self) -> None:
        service = ReviewService.__new__(ReviewService)
        service.settings = DummySettings()
        analysis = FileReview(
            path="pr_review_agent/llm.py",
            assessment="REQUEST_CHANGES",
            summary="Missing retry handling for provider failures.",
            issues=[
                ReviewIssue(
                    line=12,
                    type="bug",
                    severity="high",
                    message="Transient API failures can abort the review path.",
                    suggestion="Add retries and bounded fallback behavior.",
                )
            ],
            patch="@@ -10,1 +12,1 @@",
        )
        body = service._compose_structured_summary(
            verdict="REQUEST_CHANGES",
            executive_summary="- High-risk provider failure path still aborts important work.",
            analyses=[analysis],
            overflow_issues=[(analysis.path, analysis.issues[0])],
            comments=[],
        )
        self.assertIn("### Merge Recommendation", body)
        self.assertIn("Do not merge until blocking issues are fixed", body)
        self.assertIn("```mermaid", body)
        self.assertIn("| `pr_review_agent/llm.py` | REQUEST_CHANGES | 1 |", body)

    def test_pull_request_comment_context_uses_review_findings(self) -> None:
        service = ReviewService.__new__(ReviewService)
        review = ReviewOutput(
            event="COMMENT",
            body="summary",
            comments=[],
            analyses=[
                FileReview(
                    path="pr_review_agent/github.py",
                    assessment="COMMENT",
                    summary="HTTP error handling can be clearer.",
                    issues=[
                        ReviewIssue(
                            line=85,
                            type="maintainability",
                            severity="medium",
                            message="The request error path logs but does not include method context in the raised error.",
                            suggestion="Wrap the exception with request metadata.",
                        )
                    ],
                    patch="@@ -80,1 +85,1 @@",
                )
            ],
        )
        findings = service._build_findings_context(review)
        self.assertIn("Verdict: COMMENT", findings)
        self.assertIn("pr_review_agent/github.py", findings)
        self.assertIn("medium/maintainability", findings)

    def test_generated_file_detection_ignores_marker_inside_regular_code(self) -> None:
        client = GitHubClient.__new__(GitHubClient)
        settings = Settings(
            github_app_id="1",
            github_private_key="key",
            github_webhook_secret="secret",
            groq_api_key="key",
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
            staff_review_commands=("/staff-review",),
            generated_markers=("@generated",),
        )
        content = 'config = {"generated_markers": ["@generated"]}\nprint(config)\n'
        self.assertFalse(client._is_generated_file("tests/test_review.py", content, settings))

    def test_generated_file_detection_accepts_header_comment_marker(self) -> None:
        client = GitHubClient.__new__(GitHubClient)
        settings = Settings(
            github_app_id="1",
            github_private_key="key",
            github_webhook_secret="secret",
            groq_api_key="key",
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
            staff_review_commands=("/staff-review",),
            generated_markers=("@generated",),
        )
        content = "# @generated by tooling\nprint('hello')\n"
        self.assertTrue(client._is_generated_file("src/generated.py", content, settings))

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

    def test_pull_request_model_normalizes_null_text_fields(self) -> None:
        payload = GitHubPullRequest.model_validate(
            {
                "number": 7,
                "title": None,
                "body": None,
                "html_url": None,
                "head": {"sha": "abc123", "ref": "feature"},
            }
        )
        self.assertEqual(payload.title, "")
        self.assertEqual(payload.body, "")
        self.assertEqual(payload.html_url, "")

    def test_issue_comment_webhook_payload_parses_pull_request_comment(self) -> None:
        payload = IssueCommentWebhookPayload.model_validate(
            {
                "action": "created",
                "comment": {
                    "id": 12,
                    "body": "/staff-review explain this issue",
                    "user": {"login": "alice", "type": "User"},
                },
                "issue": {
                    "number": 7,
                    "pull_request": {"url": "https://api.github.com/repos/owner/repo/pulls/7"},
                },
                "repository": {"name": "repo", "owner": {"login": "owner"}},
                "installation": {"id": 99},
            }
        )
        self.assertEqual(payload.issue.number, 7)
        self.assertEqual(payload.comment.user.login, "alice")

    def test_issue_comment_payload_normalizes_null_body(self) -> None:
        payload = IssueCommentWebhookPayload.model_validate(
            {
                "action": "edited",
                "comment": {
                    "id": 12,
                    "body": None,
                    "user": {"login": "alice", "type": "User"},
                },
                "issue": {
                    "number": 7,
                    "pull_request": {"url": "https://api.github.com/repos/owner/repo/pulls/7"},
                },
                "repository": {"name": "repo", "owner": {"login": "owner"}},
                "installation": {"id": 99},
            }
        )
        self.assertEqual(payload.comment.body, "")
        self.assertEqual(payload.action, "edited")

    def test_langgraph_route_helpers(self) -> None:
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
        state = PRReviewGraphState(payload=payload, delivery_id="delivery-1")
        self.assertEqual(route_after_rule_evaluation(state), "determine_incremental_scope")
        self.assertEqual(route_after_incremental_scope(state), "fetch_reviewable_files")
        self.assertEqual(route_after_file_fetch(state), "__end__")
        self.assertEqual(route_after_review_generation(state), "__end__")


if __name__ == "__main__":
    unittest.main()
