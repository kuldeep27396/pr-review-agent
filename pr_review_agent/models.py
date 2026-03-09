from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PullRequestContext:
    number: int
    title: str
    body: str
    html_url: str
    head_sha: str
    head_ref: str


@dataclass(slots=True)
class ChangedFile:
    path: str
    status: str
    additions: int
    deletions: int
    patch: str
    content: str


@dataclass(slots=True)
class ReviewIssue:
    line: int
    issue_type: str
    severity: str
    message: str
    suggestion: str = ""


@dataclass(slots=True)
class FileReview:
    path: str
    assessment: str
    summary: str
    issues: list[ReviewIssue] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""
    patch: str = ""
    errored: bool = False


@dataclass(slots=True)
class ReviewComment:
    path: str
    line: int
    body: str


@dataclass(slots=True)
class ReviewOutput:
    event: str
    body: str
    comments: list[ReviewComment]
    analyses: list[FileReview]


@dataclass(slots=True)
class ReviewCommentContext:
    comment_id: int
    body: str
    path: str
    diff_hunk: str
    line: int | None = None
    user_login: str = ""
