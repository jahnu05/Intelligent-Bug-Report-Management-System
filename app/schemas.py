from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RepositorySummary(BaseModel):
    owner: str
    name: str
    full_name: str
    description: str | None = None
    default_branch: str | None = None
    private: bool = False
    html_url: str | None = None
    last_synced_at: datetime | None = None
    commit_count: int = 0
    contributor_count: int = 0
    sync_status: str = "never_synced"
    sync_error: str | None = None


class ContributorSummary(BaseModel):
    repository_full_name: str
    contributor_key: str
    github_login: str | None = None
    display_name: str | None = None
    commit_count: int = 0
    first_commit_at: datetime | None = None
    last_commit_at: datetime | None = None
    recent_commit_messages: list[str] = Field(default_factory=list)
    summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    collaboration_style: str | None = None
    evidence: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    work_area_analysis: str | None = None
    confidence: str = "low"
    generated_with: str = ""
    source_commit_shas: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class CommitRecord(BaseModel):
    repository_full_name: str
    sha: str
    contributor_key: str
    github_login: str | None = None
    author_name: str | None = None
    author_email: str | None = None
    message: str
    html_url: str | None = None
    authored_at: datetime
    committed_at: datetime | None = None
    additions: int | None = None
    deletions: int | None = None
    files_changed: int | None = None
    total_changes: int | None = None


class SyncRequest(BaseModel):
    max_pages: int | None = None
    per_page: int | None = None
    recent_n_commits: int | None = Field(default=None, ge=1)


class RandomIssueFetchRequest(BaseModel):
    state: str = "open"
    max_pages: int = Field(default=2, ge=1, le=10)
    per_page: int = Field(default=100, ge=1, le=100)


class BulkIssueFetchRequest(BaseModel):
    state: str = "open"
    max_issues: int = Field(default=200, ge=1, le=1000)


class AssignmentGenerateRequest(BaseModel):
    issue_number: int | None = Field(default=None, ge=1)
    issue_state: str = "open"


class SyncRunResult(BaseModel):
    repository_full_name: str
    status: str
    commits_ingested: int
    contributors_profiled: int
    started_at: datetime
    finished_at: datetime
    message: str


class IssueRecord(BaseModel):
    repository_full_name: str
    issue_number: int
    title: str
    body: str | None = None
    state: str
    labels: list[str] = Field(default_factory=list)
    html_url: str | None = None
    author_login: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    fetched_at: datetime | None = None


class AssignmentRecord(BaseModel):
    repository_full_name: str
    issue_number: int
    issue_title: str
    issue_url: str | None = None
    issue_state: str = "open"
    assigned_contributor_key: str
    assigned_github_login: str | None = None
    assigned_display_name: str | None = None
    rationale: str
    confidence: str
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    source_contributor_count: int = 0
    generated_with: str = ""
    generated_at: datetime | None = None
    approved: bool = False
    overridden: bool = False


class OverrideRequest(BaseModel):
    contributor_key: str


class DuplicateDetectionRequest(BaseModel):
    similarity_threshold: float = Field(default=0.8, ge=0.1, le=1.0)
    max_results: int = Field(default=10, ge=1, le=50)


class DuplicateIssue(BaseModel):
    issue_number: int
    title: str
    body: str | None = None
    state: str
    similarity_score: float
    html_url: str | None = None
    author_login: str | None = None
    created_at: datetime | None = None


class DuplicateDetectionResult(BaseModel):
    target_issue: int
    duplicates_found: int
    similarity_threshold: float
    duplicates: list[DuplicateIssue]


class ApiMessage(BaseModel):
    message: str
    data: Any | None = None
