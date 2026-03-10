from __future__ import annotations

import base64
import time
from typing import Any
from urllib.parse import quote

import httpx
import jwt

from pr_review_agent.config import Settings
from pr_review_agent.models import (
    ChangedFile,
    GitHubChangedFile,
    GitHubCompareResponse,
    GitHubPullRequest,
    GitHubReviewRecord,
    PullRequestContext,
    ReviewOutput,
)


class GitHubClient:
    api_url = "https://api.github.com"
    review_marker = "<!-- pr-review-agent -->"

    def __init__(self, settings: Settings, logger: Any) -> None:
        self.settings = settings
        self.logger = logger
        timeout = max(10.0, settings.review_timeout_ms / 1000)
        self.client = httpx.AsyncClient(base_url=self.api_url, timeout=timeout)

    async def aclose(self) -> None:
        await self.client.aclose()

    def _build_app_jwt(self) -> str:
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + 540,
            "iss": self.settings.github_app_id,
        }
        return jwt.encode(
            payload,
            self.settings.normalized_private_key,
            algorithm="RS256",
        )

    def _default_headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        response = await self.client.request(
            method,
            url,
            headers=headers,
            json=json,
            params=params,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "GitHub API request failed for %s %s: %s",
                method,
                url,
                exc.response.text,
            )
            raise
        return response

    async def get_installation_token(self, installation_id: int) -> str:
        token = self._build_app_jwt()
        response = await self._request(
            "POST",
            f"/app/installations/{installation_id}/access_tokens",
            headers=self._default_headers(token),
        )
        return response.json()["token"]

    async def _installation_request(
        self,
        method: str,
        url: str,
        installation_token: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        return await self._request(
            method,
            url,
            headers=self._default_headers(installation_token),
            json=json,
            params=params,
        )

    async def get_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        installation_token: str,
    ) -> PullRequestContext:
        response = await self._installation_request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            installation_token,
        )
        return GitHubPullRequest.model_validate(response.json()).to_context()

    async def list_pull_request_files(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        installation_token: str,
    ) -> list[GitHubChangedFile]:
        files: list[GitHubChangedFile] = []
        page = 1
        while True:
            response = await self._installation_request(
                "GET",
                f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
                installation_token,
                params={"per_page": 100, "page": page},
            )
            batch = [GitHubChangedFile.model_validate(item) for item in response.json()]
            if not batch:
                break
            files.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return files

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
        installation_token: str,
    ) -> str:
        response = await self._installation_request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{quote(path, safe='/')}",
            installation_token,
            params={"ref": ref},
        )
        data = response.json()
        encoded = data.get("content")
        if not encoded:
            return ""
        return base64.b64decode(encoded).decode("utf-8", errors="replace")

    async def get_optional_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
        installation_token: str,
    ) -> str | None:
        response = await self.client.request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{quote(path, safe='/')}",
            headers=self._default_headers(installation_token),
            params={"ref": ref},
        )
        if response.status_code == 404:
            return None
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "GitHub API request failed for GET %s: %s",
                f"/repos/{owner}/{repo}/contents/{quote(path, safe='/')}",
                exc.response.text,
            )
            raise

        data = response.json()
        encoded = data.get("content")
        if not encoded:
            return ""
        return base64.b64decode(encoded).decode("utf-8", errors="replace")

    async def get_repo_config_text(
        self,
        owner: str,
        repo: str,
        ref: str,
        installation_token: str,
    ) -> str | None:
        return await self.get_optional_file_content(
            owner,
            repo,
            self.settings.config_file_path,
            ref,
            installation_token,
        )

    async def get_reviewable_files(
        self,
        owner: str,
        repo: str,
        pr: PullRequestContext,
        installation_token: str,
        review_settings: Settings | None = None,
        include_paths: set[str] | None = None,
    ) -> list[ChangedFile]:
        effective_settings = review_settings or self.settings
        raw_files = await self.list_pull_request_files(owner, repo, pr.number, installation_token)
        result: list[ChangedFile] = []
        max_changes = effective_settings.max_file_size_kb * 10

        for item in raw_files:
            path = item.filename
            status = item.status
            if include_paths is not None and path not in include_paths:
                continue
            if status == "removed":
                continue
            if item.changes > max_changes:
                continue
            if not effective_settings.should_review_path(path):
                continue
            if len(result) >= effective_settings.max_files_to_review:
                break

            content = ""
            for ref in (pr.head_sha, pr.head_ref):
                try:
                    fetched = await self.get_optional_file_content(owner, repo, path, ref, installation_token)
                    if fetched is not None:
                        content = fetched
                        break
                except httpx.HTTPError:
                    continue

            if self._is_generated_file(path, content, effective_settings):
                continue

            result.append(
                ChangedFile(
                    path=path,
                    status=status,
                    additions=item.additions,
                    deletions=item.deletions,
                    patch=item.patch,
                    content=content,
                )
            )

        return result

    def _is_generated_file(self, path: str, content: str, review_settings: Settings) -> bool:
        if self._has_generated_header_marker(content, review_settings):
            return True
        if path.endswith((".min.js", ".min.css")):
            return True
        lines = content.splitlines()
        if content and len(content) > 5000 and len(lines) <= 10:
            return True
        return False

    @staticmethod
    def _has_generated_header_marker(content: str, review_settings: Settings) -> bool:
        comment_prefixes = ("#", "//", "/*", "*", "<!--", "--", ";")
        candidate_lines = [line.strip().lower() for line in content.splitlines()[:20] if line.strip()]
        for line in candidate_lines:
            if not line.startswith(comment_prefixes):
                continue
            if any(marker.lower() in line for marker in review_settings.generated_markers):
                return True
        return False

    async def list_reviews(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        installation_token: str,
    ) -> list[GitHubReviewRecord]:
        response = await self._installation_request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            installation_token,
            params={"per_page": 100},
        )
        return [GitHubReviewRecord.model_validate(item) for item in response.json()]

    async def get_latest_agent_review_commit(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        installation_token: str,
    ) -> str | None:
        reviews = await self.list_reviews(owner, repo, pr_number, installation_token)
        for review in reversed(reviews):
            body = review.body or ""
            if self.review_marker in body:
                return review.commit_id
        return None

    async def compare_filenames(
        self,
        owner: str,
        repo: str,
        base: str,
        head: str,
        installation_token: str,
    ) -> set[str]:
        response = await self._installation_request(
            "GET",
            f"/repos/{owner}/{repo}/compare/{base}...{head}",
            installation_token,
        )
        data = GitHubCompareResponse.model_validate(response.json())
        return {item.filename for item in data.files}

    async def post_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        review: ReviewOutput,
        installation_token: str,
        commit_id: str,
    ) -> None:
        payload: dict[str, Any] = {
            "event": review.event,
            "body": f"{self.review_marker}\n{review.body}",
            "commit_id": commit_id,
        }
        if review.comments:
            payload["comments"] = [
                {
                    "path": comment.path,
                    "line": comment.line,
                    "body": comment.body,
                }
                for comment in review.comments
            ]
        await self._installation_request(
            "POST",
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            installation_token,
            json=payload,
        )

    async def reply_to_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        in_reply_to: int,
        body: str,
        installation_token: str,
    ) -> None:
        await self._installation_request(
            "POST",
            f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
            installation_token,
            json={"body": body, "in_reply_to": in_reply_to},
        )

    async def post_issue_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
        installation_token: str,
    ) -> None:
        await self._installation_request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            installation_token,
            json={"body": body},
        )
