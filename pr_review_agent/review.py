from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any

from pr_review_agent.config import Settings
from pydantic import ValidationError

from pr_review_agent.models import (
    ChangedFile,
    FileReview,
    LLMReviewResponse,
    PullRequestContext,
    ReviewComment,
    ReviewCommentContext,
    ReviewIssue,
    ReviewOutput,
)

if TYPE_CHECKING:
    from pr_review_agent.llm import LLMClient


REVIEW_SYSTEM_PROMPT = """
You are an expert code reviewer.
Focus on correctness, security, performance, maintainability, and regression risk.
Ignore minor style feedback unless it materially affects readability or correctness.
Return valid JSON only.
""".strip()

SUMMARY_SYSTEM_PROMPT = """
You summarize pull request reviews for GitHub.
Be factual, concise, and action-oriented.
Return concise markdown bullets only.
""".strip()


class ReviewService:
    def __init__(self, settings: Settings, llm_client: LLMClient, logger: Any) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self.logger = logger

    async def review_pull_request(
        self,
        files: list[ChangedFile],
        pull_request: PullRequestContext,
    ) -> ReviewOutput | None:
        if not files:
            return None

        semaphore = asyncio.Semaphore(self.settings.request_parallelism)

        async def review_file(file: ChangedFile) -> FileReview:
            async with semaphore:
                try:
                    return await self._review_file(file, pull_request)
                except Exception:
                    self.logger.exception("File review failed path=%s", file.path)
                    return FileReview(
                        path=file.path,
                        assessment="COMMENT",
                        summary="Automated analysis failed for this file due to an upstream provider error.",
                        issues=[],
                        patch=file.patch,
                        errored=True,
                    )

        analyses = await asyncio.gather(*(review_file(file) for file in files))
        active_analyses = [analysis for analysis in analyses if not analysis.skipped]

        if not active_analyses and not self.settings.post_review_summary:
            return None

        comments, overflow_issues = self._build_inline_comments(active_analyses)
        summary = await self._build_summary(active_analyses, pull_request, overflow_issues, comments)
        return ReviewOutput(
            event=self._determine_event(active_analyses),
            body=summary,
            comments=comments,
            analyses=analyses,
        )

    async def _review_file(self, file: ChangedFile, pull_request: PullRequestContext) -> FileReview:
        if self._should_skip_simple_change(file):
            return FileReview(
                path=file.path,
                assessment="COMMENT",
                summary="Skipped trivial change",
                skipped=True,
                skip_reason="trivial change",
                patch=file.patch,
            )

        prompt = self._build_review_prompt(file, pull_request)
        content = await self.llm_client.chat(
            messages=[
                {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            model=self.settings.review_model,
            fallback_model=self.settings.resolved_fallback_review_model,
            max_tokens=1200,
        )
        return self._parse_review_response(content, file)

    def _build_review_prompt(self, file: ChangedFile, pull_request: PullRequestContext) -> str:
        truncated_patch = file.patch[: self.settings.max_patch_chars]
        truncated_content = file.content[: self.settings.max_file_context_chars]
        return f"""
Review this pull request change.

PR title: {pull_request.title}
PR description:
{pull_request.body or "No description provided"}

File: {file.path}
Status: {file.status}
Additions: {file.additions}
Deletions: {file.deletions}

Rules:
- Focus on the changed code, not the entire repository.
- For modified files, only report inline issues on added lines in the diff.
- Avoid low-value praise and cosmetic comments.
- Reason through correctness, failure paths, regressions, and test impact before deciding there is no issue.
- If the change is safe, explain why briefly in the file summary.
- Report at most 3 meaningful issues.

Unified diff:
```diff
{truncated_patch or "Patch unavailable"}
```

Current file content:
```text
{truncated_content or "Content unavailable"}
```

Return JSON using this schema:
{{
  "assessment": "APPROVE|COMMENT|REQUEST_CHANGES",
  "summary": "short summary",
  "issues": [
    {{
      "line": 12,
      "type": "bug|security|performance|maintainability|best-practice",
      "severity": "high|medium|low",
      "message": "issue description",
      "suggestion": "specific fix"
    }}
  ]
}}
""".strip()

    def _parse_review_response(self, response_text: str, file: ChangedFile) -> FileReview:
        raw_json = self._extract_json_block(response_text)
        if not raw_json:
            return FileReview(
                path=file.path,
                assessment="COMMENT",
                summary=response_text.strip() or "Review completed.",
                issues=[],
                patch=file.patch,
            )

        try:
            data = LLMReviewResponse.model_validate_json(raw_json)
        except ValidationError:
            return FileReview(
                path=file.path,
                assessment="COMMENT",
                summary=response_text.strip() or "Review completed.",
                issues=[],
                patch=file.patch,
            )

        return FileReview(
            path=file.path,
            assessment=data.assessment.strip().upper(),
            summary=data.summary.strip(),
            issues=[
                ReviewIssue(
                    line=max(1, issue.line),
                    type=issue.issue_type.strip().lower(),
                    severity=issue.severity.strip().lower(),
                    message=issue.message.strip(),
                    suggestion=issue.suggestion.strip(),
                )
                for issue in data.issues[:3]
                if issue.message.strip()
            ],
            patch=file.patch,
        )

    async def _build_summary(
        self,
        analyses: list[FileReview],
        pull_request: PullRequestContext,
        overflow_issues: list[tuple[str, ReviewIssue]],
        comments: list[ReviewComment],
    ) -> str:
        verdict = self._determine_event(analyses)
        if not analyses:
            return self._compose_structured_summary(
                verdict=verdict,
                executive_summary="No substantive files were reviewed. The changes were filtered out or skipped as trivial.",
                analyses=[],
                overflow_issues=[],
                comments=[],
            )

        issue_count = sum(len(analysis.issues) for analysis in analyses)
        facts = "\n".join(
            [
                f"- {analysis.path}: {analysis.assessment} | {analysis.summary}"
                for analysis in analyses
            ]
        )
        overflow = "\n".join(
            [
                f"- {path}:{issue.line} [{issue.severity}/{issue.issue_type}] {issue.message}"
                for path, issue in overflow_issues
            ]
        )

        test_plan_instruction = "- a short test plan section" if self.settings.enable_test_plan else ""
        prompt = f"""
Summarize this pull request review as compact markdown bullets.

PR title: {pull_request.title}
PR URL: {pull_request.html_url}
Files reviewed: {len(analyses)}
Inline comments posted: {len(comments)}
Total issues found: {issue_count}
Final review event: {verdict}
Merge recommendation: {self._merge_recommendation(verdict)}

Per-file review results:
{facts}

Issues not posted inline:
{overflow or "- none"}

Write:
- 2 to 4 bullets total
- mention the highest-risk findings first
- mention whether the PR is ready to merge
{test_plan_instruction}
""".strip()

        try:
            executive_summary = await self.llm_client.chat(
                messages=[
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                model=self.settings.resolved_summary_model,
                fallback_model=self.settings.resolved_fallback_summary_model,
                max_tokens=700,
                temperature=0.0,
            )
        except Exception:
            self.logger.exception("Falling back to local summary generation")
            executive_summary = self._fallback_executive_summary(analyses, overflow_issues, comments)

        return self._compose_structured_summary(
            verdict=verdict,
            executive_summary=executive_summary,
            analyses=analyses,
            overflow_issues=overflow_issues,
            comments=comments,
        )

    def _fallback_executive_summary(
        self,
        analyses: list[FileReview],
        overflow_issues: list[tuple[str, ReviewIssue]],
        comments: list[ReviewComment],
    ) -> str:
        high_risk = [
            issue
            for analysis in analyses
            for issue in analysis.issues
            if issue.severity == "high"
        ]
        lines = [
            f"- Review outcome: **{self._determine_event(analyses)}** with {len(high_risk)} high-severity issue(s) across {len(analyses)} reviewed file(s).",
            f"- Inline comments posted: {len(comments)}. Additional non-inline issues: {len(overflow_issues)}.",
        ]
        lines.extend(f"- `{analysis.path}`: {analysis.summary}" for analysis in analyses[:3])
        return "\n".join(lines)

    def _compose_structured_summary(
        self,
        *,
        verdict: str,
        executive_summary: str,
        analyses: list[FileReview],
        overflow_issues: list[tuple[str, ReviewIssue]],
        comments: list[ReviewComment],
    ) -> str:
        issue_count = sum(len(analysis.issues) for analysis in analyses)
        files_reviewed = len(analyses)
        merge_decision = self._merge_recommendation(verdict)
        badge = self._decision_badge(verdict)
        overview_rows = [
            ("Decision", f"{badge} {verdict}"),
            ("Merge recommendation", merge_decision),
            ("Files reviewed", str(files_reviewed)),
            ("Issues found", str(issue_count)),
            ("Inline comments posted", str(len(comments))),
            ("Additional issues", str(len(overflow_issues))),
        ]

        lines = [
            "## PR Review",
            "",
            "### Decision",
            "",
            "| Item | Value |",
            "| --- | --- |",
        ]
        lines.extend(f"| {label} | {value} |" for label, value in overview_rows)
        lines.extend(
            [
                "",
                "### Merge Flow",
                "",
                self._build_mermaid_diagram(verdict, issue_count),
                "",
                "### Executive Summary",
                "",
                executive_summary.strip() or "- Review completed.",
            ]
        )

        if analyses:
            lines.extend(["", "### File Summary", "", "| File | Assessment | Issues | Summary |", "| --- | --- | ---: | --- |"])
            for analysis in analyses[:10]:
                lines.append(
                    f"| `{analysis.path}` | {analysis.assessment} | {len(analysis.issues)} | {self._sanitize_table_text(analysis.summary)} |"
                )

        risk_lines = self._build_risk_lines(analyses, overflow_issues)
        if risk_lines:
            lines.extend(["", "### Key Risks", ""])
            lines.extend(risk_lines)

        if self.settings.enable_test_plan:
            lines.extend(["", "### Suggested Test Plan", ""])
            lines.extend(self._build_test_plan(analyses))

        lines.extend(
            [
                "",
                "### Merge Recommendation",
                "",
                f"**{merge_decision}**",
            ]
        )
        return "\n".join(lines)

    def _build_test_plan(self, analyses: list[FileReview]) -> list[str]:
        focus_areas: list[str] = []
        for analysis in analyses:
            for issue in analysis.issues:
                if issue.issue_type == "security":
                    focus_areas.append("- Exercise authorization, validation, and failure-path tests for the touched code.")
                elif issue.issue_type == "performance":
                    focus_areas.append("- Run a before/after benchmark around the changed hot path.")
                elif issue.issue_type == "bug":
                    focus_areas.append("- Add regression coverage for the changed branch conditions and edge cases.")
        if not focus_areas:
            focus_areas.append("- Run targeted tests for the touched files and a smoke test of the main user flow.")
        deduped: list[str] = []
        for item in focus_areas:
            if item not in deduped:
                deduped.append(item)
        return deduped[:4]

    def _build_risk_lines(
        self,
        analyses: list[FileReview],
        overflow_issues: list[tuple[str, ReviewIssue]],
    ) -> list[str]:
        ranked: list[tuple[str, ReviewIssue]] = []
        for analysis in analyses:
            for issue in analysis.issues:
                ranked.append((analysis.path, issue))
        ranked.extend(overflow_issues)
        ranked.sort(key=lambda item: (self._severity_rank(item[1].severity), item[0], item[1].line))

        lines: list[str] = []
        seen: set[tuple[str, int, str]] = set()
        for path, issue in ranked:
            key = (path, issue.line, issue.message)
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"- `{path}:{issue.line}` [{issue.severity}/{issue.issue_type}] {issue.message}"
            )
            if len(lines) == 6:
                break
        return lines

    @staticmethod
    def _severity_rank(severity: str) -> int:
        return {"high": 0, "medium": 1, "low": 2}.get(severity, 3)

    @staticmethod
    def _sanitize_table_text(text: str) -> str:
        return " ".join(text.replace("|", "/").split())

    @staticmethod
    def _decision_badge(verdict: str) -> str:
        return {
            "APPROVE": "🟢",
            "COMMENT": "🟡",
            "REQUEST_CHANGES": "🔴",
        }.get(verdict, "⚪")

    def _merge_recommendation(self, verdict: str) -> str:
        return {
            "APPROVE": "Ready to merge",
            "COMMENT": "Merge after reviewing suggested improvements",
            "REQUEST_CHANGES": "Do not merge until blocking issues are fixed",
        }.get(verdict, "Review manually before merging")

    def _build_mermaid_diagram(self, verdict: str, issue_count: int) -> str:
        recommendation = self._merge_recommendation(verdict)
        if verdict == "REQUEST_CHANGES":
            decision_node = "hold[Do Not Merge Yet]"
            decision_class = "hold"
            path_label = "blocking issues"
        elif verdict == "COMMENT":
            decision_node = "caution[Merge After Suggested Fixes]"
            decision_class = "caution"
            path_label = "non-blocking issues"
        else:
            decision_node = "go[Ready To Merge]"
            decision_class = "go"
            path_label = "no blocking issues"

        return "\n".join(
            [
                "```mermaid",
                "flowchart LR",
                "    pr[PR Diff] --> scan[Structured Review]",
                f"    scan --> findings[Issues: {issue_count}]",
                f"    findings -->|{path_label}| {decision_node}",
                "    classDef go fill:#d1fae5,stroke:#059669,color:#065f46;",
                "    classDef caution fill:#fef3c7,stroke:#d97706,color:#92400e;",
                "    classDef hold fill:#fee2e2,stroke:#dc2626,color:#991b1b;",
                f"    class {decision_class} {decision_class};",
                "```",
            ]
        )

    def _build_inline_comments(
        self,
        analyses: list[FileReview],
    ) -> tuple[list[ReviewComment], list[tuple[str, ReviewIssue]]]:
        comments: list[ReviewComment] = []
        overflow_issues: list[tuple[str, ReviewIssue]] = []
        seen: set[tuple[str, int, str]] = set()

        for analysis in analyses:
            valid_lines = extract_added_lines(analysis.patch)
            for issue in analysis.issues:
                issue_key = (analysis.path, issue.line, issue.message)
                if issue_key in seen:
                    continue
                seen.add(issue_key)

                if valid_lines and issue.line in valid_lines and len(comments) < self.settings.max_comments_per_review:
                    comments.append(
                        ReviewComment(
                            path=analysis.path,
                            line=issue.line,
                            body=self._format_comment(issue),
                        )
                    )
                else:
                    overflow_issues.append((analysis.path, issue))

        return comments, overflow_issues

    def _format_comment(self, issue: ReviewIssue) -> str:
        severity_emoji = {
            "high": "🔴",
            "medium": "🟡",
            "low": "🟢",
        }.get(issue.severity, "⚪")
        type_label = issue.issue_type.upper()
        body = f"{severity_emoji} **{type_label}** ({issue.severity})\n\n{issue.message}"
        if issue.suggestion:
            body += f"\n\nSuggested fix: {issue.suggestion}"
        return body

    def _determine_event(self, analyses: list[FileReview]) -> str:
        for analysis in analyses:
            for issue in analysis.issues:
                if issue.severity == "high" or issue.issue_type in {"security", "bug"}:
                    return "REQUEST_CHANGES"
        if any(analysis.issues for analysis in analyses):
            return "COMMENT"
        return "APPROVE"

    def _should_skip_simple_change(self, file: ChangedFile) -> bool:
        if self.settings.review_simple_changes:
            return False
        if file.status == "added":
            return False
        added_lines = [
            line[1:].strip()
            for line in file.patch.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
        removed_lines = [
            line[1:].strip()
            for line in file.patch.splitlines()
            if line.startswith("-") and not line.startswith("---")
        ]
        if len(added_lines) + len(removed_lines) > 4:
            return False
        meaningful_lines = [line for line in added_lines + removed_lines if line]
        if not meaningful_lines:
            return True
        comment_only = all(
            line.startswith(("#", "//", "/*", "*", "<!--"))
            for line in meaningful_lines
        )
        token_count = sum(len(line) for line in meaningful_lines)
        return comment_only or token_count < 40

    @staticmethod
    def _extract_json_block(text: str) -> str | None:
        match = re.search(r"\{[\s\S]*\}", text)
        return match.group(0) if match else None

    async def answer_review_comment(
        self,
        comment: ReviewCommentContext,
        pull_request: PullRequestContext,
        file: ChangedFile,
    ) -> str:
        prompt = f"""
You are replying to a GitHub pull request review comment.

PR title: {pull_request.title}
PR URL: {pull_request.html_url}
Comment author: {comment.user_login}
File: {comment.path}
Line: {comment.line or "unknown"}

Original comment:
{comment.body}

Diff hunk:
```diff
{comment.diff_hunk or "Unavailable"}
```

Current file content:
```text
{file.content[: self.settings.max_file_context_chars] or "Unavailable"}
```

Reply concisely. Answer directly, explain tradeoffs when relevant, and suggest a concrete next step if the commenter is asking for a fix or clarification.
""".strip()

        return await self.llm_client.chat(
            messages=[
                {"role": "system", "content": "You are a pull request review assistant. Reply in concise markdown."},
                {"role": "user", "content": prompt},
            ],
            model=self.settings.review_model,
            fallback_model=self.settings.resolved_fallback_review_model,
            max_tokens=700,
            temperature=0.1,
        )

    async def answer_pull_request_comment(
        self,
        prompt_text: str,
        pull_request: PullRequestContext,
        review: ReviewOutput | None = None,
    ) -> str:
        findings_context = self._build_findings_context(review)
        prompt = f"""
You are replying to a GitHub pull request conversation comment.

PR title: {pull_request.title}
PR URL: {pull_request.html_url}
PR description:
{pull_request.body or "Unavailable"}

Current review findings:
{findings_context}

User request:
{prompt_text or "Explain the current review concerns and next steps."}

Reply concisely. Base the answer on the current PR review findings, explain tradeoffs when useful, and end with a concrete next step when the user is asking for help.
""".strip()

        return await self.llm_client.chat(
            messages=[
                {"role": "system", "content": "You are a pull request review assistant. Reply in concise markdown."},
                {"role": "user", "content": prompt},
            ],
            model=self.settings.review_model,
            fallback_model=self.settings.resolved_fallback_review_model,
            max_tokens=700,
            temperature=0.1,
        )

    def _build_findings_context(self, review: ReviewOutput | None) -> str:
        if review is None:
            return "No fresh review findings are available."

        verdict = review.event
        lines = [f"Verdict: {verdict}"]
        for analysis in review.analyses[:8]:
            issue_summaries = [
                f"{issue.severity}/{issue.issue_type} at line {issue.line}: {issue.message}"
                for issue in analysis.issues[:3]
            ]
            joined_issues = "; ".join(issue_summaries) if issue_summaries else "no material issues reported"
            lines.append(f"- {analysis.path}: {analysis.summary} | {joined_issues}")
        return "\n".join(lines)


def extract_added_lines(patch: str) -> set[int]:
    if not patch:
        return set()

    lines = set()
    current_line = 0
    for raw_line in patch.splitlines():
        if raw_line.startswith("@@"):
            match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw_line)
            if match:
                current_line = int(match.group(1))
            continue
        if raw_line.startswith("+++"):
            continue
        if raw_line.startswith("+"):
            lines.add(current_line)
            current_line += 1
            continue
        if raw_line.startswith(" "):
            current_line += 1
            continue
        if raw_line.startswith("-"):
            continue
    return lines
