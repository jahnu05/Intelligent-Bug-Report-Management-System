from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import random
from typing import Any

import requests


class GitHubAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubCommit:
    repository_full_name: str
    sha: str
    contributor_key: str
    github_login: str | None
    author_name: str | None
    author_email: str | None
    message: str
    html_url: str | None
    authored_at: datetime
    committed_at: datetime | None
    additions: int | None = None
    deletions: int | None = None
    files_changed: int | None = None
    total_changes: int | None = None


@dataclass(frozen=True)
class GitHubIssue:
    repository_full_name: str
    issue_number: int
    title: str
    body: str | None
    state: str
    labels: list[str]
    html_url: str | None
    author_login: str | None
    created_at: datetime | None
    updated_at: datetime | None


class GitHubClient:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        if token:
            self._session.headers["Authorization"] = f"Bearer {token}"

    def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        response = self._session.get(url, params=params, timeout=30)
        if response.status_code >= 400:
            raise GitHubAPIError(f"GitHub API request failed ({response.status_code}): {response.text}")
        return response.json()

    def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        return self._request(f"/repos/{owner}/{repo}")

    def get_issue(self, owner: str, repo: str, issue_number: int) -> GitHubIssue:
        payload = self._request(f"/repos/{owner}/{repo}/issues/{issue_number}")
        if payload.get("pull_request"):
            raise GitHubAPIError(f"Issue #{issue_number} is a pull request and cannot be assigned as issue.")
        return self._to_issue(owner, repo, payload)

    def list_issue_pages(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        max_pages: int = 2,
        per_page: int = 100,
    ) -> list[GitHubIssue]:
        issues: list[GitHubIssue] = []
        for page in range(1, max_pages + 1):
            payload = self._request(
                f"/repos/{owner}/{repo}/issues",
                params={"state": state, "page": page, "per_page": per_page},
            )
            if not payload:
                break
            for item in payload:
                if item.get("pull_request"):
                    continue
                issues.append(self._to_issue(owner, repo, item))
        return issues

    def fetch_random_issue(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        max_pages: int = 2,
        per_page: int = 100,
    ) -> GitHubIssue:
        issues = self.list_issue_pages(owner, repo, state=state, max_pages=max_pages, per_page=per_page)
        if not issues:
            raise GitHubAPIError("No issues found for the repository with the given filters.")
        return random.choice(issues)

    def list_commit_pages(
        self,
        owner: str,
        repo: str,
        max_pages: int = 5,
        per_page: int = 100,
        recent_n_commits: int | None = None,
    ) -> list[GitHubCommit]:
        commits: list[GitHubCommit] = []
        for page in range(1, max_pages + 1):
            payload = self._request(
                f"/repos/{owner}/{repo}/commits",
                params={"page": page, "per_page": per_page},
            )
            if not payload:
                break
            for item in payload:
                commits.append(self._to_commit(owner, repo, item))
                if recent_n_commits is not None and len(commits) >= recent_n_commits:
                    return commits[:recent_n_commits]
        return commits

    def _to_commit(self, owner: str, repo: str, item: dict[str, Any]) -> GitHubCommit:
        commit = item.get("commit", {})
        author = item.get("author") or {}
        commit_author = commit.get("author", {})
        sha = item["sha"]
        github_login = author.get("login")
        author_name = commit_author.get("name")
        author_email = commit_author.get("email")
        contributor_key = self._build_contributor_key(github_login, author_email, author_name, sha)

        return GitHubCommit(
            repository_full_name=f"{owner}/{repo}",
            sha=sha,
            contributor_key=contributor_key,
            github_login=github_login,
            author_name=author_name,
            author_email=author_email,
            message=(commit.get("message") or "").split("\n", 1)[0].strip(),
            html_url=item.get("html_url"),
            authored_at=self._parse_datetime(commit_author.get("date")),
            committed_at=self._parse_datetime(commit.get("committer", {}).get("date")),
        )

    def _to_issue(self, owner: str, repo: str, item: dict[str, Any]) -> GitHubIssue:
        labels = [label.get("name", "") for label in item.get("labels", []) if label.get("name")]
        return GitHubIssue(
            repository_full_name=f"{owner}/{repo}",
            issue_number=item["number"],
            title=item.get("title", ""),
            body=item.get("body"),
            state=item.get("state", "open"),
            labels=labels,
            html_url=item.get("html_url"),
            author_login=(item.get("user") or {}).get("login"),
            created_at=self._parse_datetime(item.get("created_at")),
            updated_at=self._parse_datetime(item.get("updated_at")),
        )

    @staticmethod
    def _build_contributor_key(
        github_login: str | None,
        author_email: str | None,
        author_name: str | None,
        sha: str,
    ) -> str:
        if github_login:
            return f"login:{github_login.lower()}"
        if author_email:
            return f"email:{author_email.lower()}"
        if author_name:
            return f"name:{author_name.lower()}"
        return f"sha:{sha}"

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
