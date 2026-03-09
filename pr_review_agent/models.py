from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AppBaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class PullRequestContext(AppBaseModel):
    number: int
    title: str
    body: str = ""
    html_url: str
    head_sha: str
    head_ref: str


class ChangedFile(AppBaseModel):
    path: str
    status: str
    additions: int
    deletions: int
    patch: str = ""
    content: str = ""


class ReviewIssue(AppBaseModel):
    line: int
    issue_type: str = Field(alias="type")
    severity: str
    message: str
    suggestion: str = ""


class FileReview(AppBaseModel):
    path: str
    assessment: str
    summary: str
    issues: list[ReviewIssue] = Field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""
    patch: str = ""
    errored: bool = False


class ReviewComment(AppBaseModel):
    path: str
    line: int
    body: str


class ReviewOutput(AppBaseModel):
    event: str
    body: str
    comments: list[ReviewComment]
    analyses: list[FileReview]


class ReviewCommentContext(AppBaseModel):
    comment_id: int
    body: str
    path: str = ""
    diff_hunk: str = ""
    line: int | None = None
    user_login: str = ""


class LLMReviewResponse(AppBaseModel):
    assessment: str = "COMMENT"
    summary: str = "Review completed."
    issues: list[ReviewIssue] = Field(default_factory=list)


class GitHubAccount(AppBaseModel):
    login: str
    type: str | None = None


class GitHubRepository(AppBaseModel):
    name: str
    owner: GitHubAccount


class GitHubInstallation(AppBaseModel):
    id: int


class GitHubHead(AppBaseModel):
    sha: str
    ref: str


class GitHubPullRequest(AppBaseModel):
    number: int
    title: str = ""
    body: str = ""
    html_url: str = ""
    head: GitHubHead

    def to_context(self) -> PullRequestContext:
        return PullRequestContext(
            number=self.number,
            title=self.title,
            body=self.body,
            html_url=self.html_url,
            head_sha=self.head.sha,
            head_ref=self.head.ref,
        )


class PullRequestWebhookPayload(AppBaseModel):
    action: str
    pull_request: GitHubPullRequest
    repository: GitHubRepository
    installation: GitHubInstallation


class GitHubReviewComment(AppBaseModel):
    id: int
    body: str = ""
    path: str = ""
    diff_hunk: str = ""
    line: int | None = None
    user: GitHubAccount


class ReviewCommentWebhookPayload(AppBaseModel):
    action: Literal["created"] | str
    comment: GitHubReviewComment
    pull_request: GitHubPullRequest
    repository: GitHubRepository
    installation: GitHubInstallation


class GitHubChangedFile(AppBaseModel):
    filename: str
    status: str
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str = ""


class GitHubReviewRecord(AppBaseModel):
    body: str = ""
    commit_id: str | None = None


class GitHubCompareFile(AppBaseModel):
    filename: str


class GitHubCompareResponse(AppBaseModel):
    files: list[GitHubCompareFile] = Field(default_factory=list)
