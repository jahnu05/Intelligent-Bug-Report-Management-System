from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .context_optimizer import CommitContextOptimizer
from .gemini_api import LLMProviderStrategy
from .github_api import GitHubClient, GitHubCommit, GitHubIssue
from .repositories import AssignmentStore, CommitStore, ContributorStore, IssueStore, RepositoryStore, SyncRunStore


class ContributorPipelineService:
    def __init__(
        self,
        github_client: GitHubClient,
        summarizer: LLMProviderStrategy,
        context_optimizer: CommitContextOptimizer,
        repository_store: RepositoryStore,
        commit_store: CommitStore,
        contributor_store: ContributorStore,
        issue_store: IssueStore,
        assignment_store: AssignmentStore,
        sync_run_store: SyncRunStore,
    ) -> None:
        self.github_client = github_client
        self.summarizer = summarizer
        self.context_optimizer = context_optimizer
        self.repository_store = repository_store
        self.commit_store = commit_store
        self.contributor_store = contributor_store
        self.issue_store = issue_store
        self.assignment_store = assignment_store
        self.sync_run_store = sync_run_store

    def sync_repository(
        self,
        owner: str,
        repo: str,
        max_pages: int,
        per_page: int,
        recent_n_commits: int | None = None,
    ) -> dict[str, Any]:
        repository_full_name = f"{owner}/{repo}"
        run_id = self.sync_run_store.create_run(repository_full_name)
        started_at = datetime.now(timezone.utc)

        try:
            repo_metadata = self.github_client.get_repository(owner, repo)
            self.repository_store.upsert_repository(self._repository_document(repo_metadata))

            commits = self.github_client.list_commit_pages(
                owner,
                repo,
                max_pages=max_pages,
                per_page=per_page,
                recent_n_commits=recent_n_commits,
            )
            commit_documents = [self._commit_document(commit) for commit in commits]
            ingested_count = self.commit_store.upsert_commits(commit_documents)

            contributor_groups = self._group_commits(commits)
            for contributor_key, group in contributor_groups.items():
                profile = self._build_contributor_profile(repository_full_name, contributor_key, group)
                self.contributor_store.upsert_profile(profile)

            self.repository_store.set_statistics(
                repository_full_name,
                commit_count=len(commit_documents),
                contributor_count=len(contributor_groups),
            )
            self.repository_store.update_sync_state(repository_full_name, "synced")
            finished_at = datetime.now(timezone.utc)
            self.sync_run_store.finish_run(run_id, "success", "Repository synced successfully")

            return {
                "repository_full_name": repository_full_name,
                "status": "success",
                "commits_ingested": ingested_count,
                "contributors_profiled": len(contributor_groups),
                "started_at": started_at,
                "finished_at": finished_at,
                "message": "Repository synced successfully",
            }
        except Exception as exc:
            self.repository_store.update_sync_state(repository_full_name, "failed", str(exc))
            self.sync_run_store.finish_run(run_id, "failed", str(exc))
            raise

    def get_repository_summary(self, owner: str, repo: str) -> dict[str, Any] | None:
        return self.repository_store.get_repository(f"{owner}/{repo}")

    def list_contributors(self, owner: str, repo: str) -> list[dict[str, Any]]:
        return self.contributor_store.list_profiles(f"{owner}/{repo}")

    def get_contributor_profile(self, owner: str, repo: str, contributor_key: str) -> dict[str, Any] | None:
        return self.contributor_store.get_profile(f"{owner}/{repo}", contributor_key)

    def list_commits(
        self,
        owner: str,
        repo: str,
        contributor_key: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.commit_store.list_commits(f"{owner}/{repo}", contributor_key=contributor_key, limit=limit)

    def refresh_contributor_profile(self, owner: str, repo: str, contributor_key: str) -> dict[str, Any] | None:
        repository_full_name = f"{owner}/{repo}"
        commit_documents = self.commit_store.list_commits(repository_full_name, contributor_key=contributor_key, limit=50)
        if not commit_documents:
            return None

        grouped = self._group_commit_documents(commit_documents)
        group = grouped[contributor_key]
        profile = self._build_contributor_profile(repository_full_name, contributor_key, group)
        self.contributor_store.upsert_profile(profile)
        return profile

    def force_refresh_all_summaries(self, owner: str, repo: str) -> dict[str, Any]:
        repository_full_name = f"{owner}/{repo}"
        contributor_keys = self.commit_store.list_contributor_keys(repository_full_name)
        if not contributor_keys:
            return {
                "repository_full_name": repository_full_name,
                "contributors_refreshed": 0,
                "contributors_failed": 0,
                "message": "No contributors found in commit history.",
            }

        refreshed = 0
        failed = 0
        for contributor_key in contributor_keys:
            commit_documents = self.commit_store.list_commits(
                repository_full_name,
                contributor_key=contributor_key,
                limit=200,
            )
            if not commit_documents:
                failed += 1
                continue

            grouped = self._group_commit_documents(commit_documents)
            group = grouped.get(contributor_key)
            if not group:
                failed += 1
                continue

            profile = self._build_contributor_profile(repository_full_name, contributor_key, group)
            self.contributor_store.upsert_profile(profile)
            refreshed += 1

        return {
            "repository_full_name": repository_full_name,
            "contributors_refreshed": refreshed,
            "contributors_failed": failed,
            "message": "Force refresh completed.",
        }

    def clear_repository_summaries(self, owner: str, repo: str) -> dict[str, Any]:
        repository_full_name = f"{owner}/{repo}"
        modified_count = self.contributor_store.clear_summaries(repository_full_name=repository_full_name)
        return {
            "scope": "repository",
            "repository_full_name": repository_full_name,
            "summaries_cleared": modified_count,
            "message": "Contributor summaries cleared for repository.",
        }

    def clear_all_summaries(self) -> dict[str, Any]:
        modified_count = self.contributor_store.clear_summaries(repository_full_name=None)
        return {
            "scope": "global",
            "summaries_cleared": modified_count,
            "message": "Contributor summaries cleared for all repositories.",
        }

    def fetch_random_issue(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        max_pages: int = 2,
        per_page: int = 100,
    ) -> dict[str, Any]:
        issue = self.github_client.fetch_random_issue(owner, repo, state=state, max_pages=max_pages, per_page=per_page)
        document = self._issue_document(issue)
        self.issue_store.upsert_issue(document)
        return document

    def list_issues(self, owner: str, repo: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.issue_store.list_issues(f"{owner}/{repo}", limit=limit)

    def get_issue(self, owner: str, repo: str, issue_number: int) -> dict[str, Any] | None:
        return self.issue_store.get_issue(f"{owner}/{repo}", issue_number)

    def generate_issue_assignment(
        self,
        owner: str,
        repo: str,
        issue_number: int | None = None,
        issue_state: str = "open",
        fetch_if_missing: bool = True,
    ) -> dict[str, Any]:
        repository_full_name = f"{owner}/{repo}"

        if issue_number is None:
            issue_doc = self.fetch_random_issue(owner, repo, state=issue_state)
        else:
            issue_doc = self.issue_store.get_issue(repository_full_name, issue_number)
            if not issue_doc and fetch_if_missing:
                issue = self.github_client.get_issue(owner, repo, issue_number)
                issue_doc = self._issue_document(issue)
                self.issue_store.upsert_issue(issue_doc)
            if not issue_doc:
                raise ValueError("Issue not found in DB. Fetch issue first or enable fetch_if_missing.")

        contributors = self.contributor_store.list_profiles(repository_full_name)
        if not contributors:
            raise ValueError("No contributor summaries found. Run contributor sync first.")

        assignment_input = {
            "repository_full_name": repository_full_name,
            "issue_number": issue_doc["issue_number"],
            "issue_title": issue_doc["title"],
            "issue_body": issue_doc.get("body", ""),
            "issue_labels": issue_doc.get("labels", []),
            "issue_state": issue_doc.get("state", "open"),
            "contributors": [
                {
                    "contributor_key": contributor.get("contributor_key"),
                    "github_login": contributor.get("github_login"),
                    "summary": contributor.get("summary"),
                    "focus_areas": contributor.get("focus_areas", []),
                    "strengths": contributor.get("strengths", []),
                    "keywords": contributor.get("keywords", []),
                    "commit_count": contributor.get("commit_count", 0),
                }
                for contributor in contributors
            ],
        }
        assignment = self.summarizer.assign_issue(assignment_input)

        assignment_document = {
            "repository_full_name": repository_full_name,
            "issue_number": issue_doc["issue_number"],
            "issue_title": issue_doc["title"],
            "issue_url": issue_doc.get("html_url"),
            "issue_state": issue_doc.get("state", "open"),
            "assigned_contributor_key": assignment.assigned_contributor_key,
            "assigned_github_login": assignment.assigned_github_login,
            "rationale": assignment.rationale,
            "confidence": assignment.confidence,
            "alternatives": assignment.alternatives,
            "source_contributor_count": len(contributors),
            "generated_with": f"{self.summarizer.provider_name}:{self.summarizer.model_name}",
            "generated_at": datetime.now(timezone.utc),
        }
        self.assignment_store.upsert_assignment(assignment_document)
        return assignment_document

    def list_assignments(self, owner: str, repo: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.assignment_store.list_assignments(f"{owner}/{repo}", limit=limit)

    def get_assignment(self, owner: str, repo: str, issue_number: int) -> dict[str, Any] | None:
        return self.assignment_store.get_assignment(f"{owner}/{repo}", issue_number)

    def _repository_document(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "owner": payload["owner"]["login"],
            "name": payload["name"],
            "full_name": payload["full_name"],
            "description": payload.get("description"),
            "default_branch": payload.get("default_branch"),
            "private": payload.get("private", False),
            "html_url": payload.get("html_url"),
            "language": payload.get("language"),
            "visibility": payload.get("visibility"),
            "sync_status": "running",
            "sync_error": None,
            "last_synced_at": datetime.now(timezone.utc),
        }

    def _commit_document(self, commit: GitHubCommit) -> dict[str, Any]:
        return {
            "repository_full_name": commit.repository_full_name,
            "sha": commit.sha,
            "contributor_key": commit.contributor_key,
            "github_login": commit.github_login,
            "author_name": commit.author_name,
            "author_email": commit.author_email,
            "message": commit.message,
            "html_url": commit.html_url,
            "authored_at": commit.authored_at,
            "committed_at": commit.committed_at,
            "additions": commit.additions,
            "deletions": commit.deletions,
            "files_changed": commit.files_changed,
            "total_changes": commit.total_changes,
        }

    def _issue_document(self, issue: GitHubIssue) -> dict[str, Any]:
        return {
            "repository_full_name": issue.repository_full_name,
            "issue_number": issue.issue_number,
            "title": issue.title,
            "body": issue.body,
            "state": issue.state,
            "labels": issue.labels,
            "html_url": issue.html_url,
            "author_login": issue.author_login,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "fetched_at": datetime.now(timezone.utc),
        }

    def _group_commits(self, commits: list[GitHubCommit]) -> dict[str, dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "commit_count": 0,
                "recent_commit_messages": [],
                "all_commit_messages": [],
                "source_commit_pairs": [],
                "source_commit_shas": [],
                "display_name": None,
                "github_login": None,
                "first_commit_at": None,
                "last_commit_at": None,
                "keywords": [],
            }
        )

        for commit in sorted(commits, key=lambda item: item.authored_at):
            group = groups[commit.contributor_key]
            group["commit_count"] += 1
            group["github_login"] = group["github_login"] or commit.github_login
            group["display_name"] = group["display_name"] or commit.author_name or commit.github_login
            group["first_commit_at"] = group["first_commit_at"] or commit.authored_at
            group["last_commit_at"] = commit.authored_at
            if commit.message:
                group["recent_commit_messages"].append(commit.message)
                group["all_commit_messages"].append(commit.message)
            group["source_commit_pairs"].append((commit.sha, commit.message))
            group["source_commit_shas"].append(commit.sha)

        for group in groups.values():
            group["recent_commit_messages"] = list(reversed(group["recent_commit_messages"]))[:10]
            group["source_commit_pairs"] = list(reversed(group["source_commit_pairs"]))[:10]
            group["source_commit_shas"] = list(reversed(group["source_commit_shas"]))[:10]
        return groups

    def _group_commit_documents(self, commit_documents: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "commit_count": 0,
                "recent_commit_messages": [],
                "all_commit_messages": [],
                "source_commit_pairs": [],
                "source_commit_shas": [],
                "display_name": None,
                "github_login": None,
                "first_commit_at": None,
                "last_commit_at": None,
                "keywords": [],
            }
        )
        for commit in sorted(commit_documents, key=lambda item: item["authored_at"]):
            group = groups[commit["contributor_key"]]
            group["commit_count"] += 1
            group["github_login"] = group["github_login"] or commit.get("github_login")
            group["display_name"] = group["display_name"] or commit.get("author_name") or commit.get("github_login")
            group["first_commit_at"] = group["first_commit_at"] or commit["authored_at"]
            group["last_commit_at"] = commit["authored_at"]
            if commit.get("message"):
                group["recent_commit_messages"].append(commit["message"])
                group["all_commit_messages"].append(commit["message"])
            group["source_commit_pairs"].append((commit["sha"], commit.get("message", "")))
            group["source_commit_shas"].append(commit["sha"])

        for group in groups.values():
            group["recent_commit_messages"] = list(reversed(group["recent_commit_messages"]))[:10]
            group["source_commit_pairs"] = list(reversed(group["source_commit_pairs"]))[:10]
            group["source_commit_shas"] = list(reversed(group["source_commit_shas"]))[:10]
        return groups

    def _build_contributor_profile(
        self,
        repository_full_name: str,
        contributor_key: str,
        group: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self.context_optimizer.build_payload(
            repository_full_name=repository_full_name,
            contributor_key=contributor_key,
            group=group,
        )
        summary = self.summarizer.summarize_contributor(payload)
        return {
            "repository_full_name": repository_full_name,
            "contributor_key": contributor_key,
            "github_login": group.get("github_login"),
            "display_name": group.get("display_name"),
            "commit_count": group.get("commit_count", 0),
            "first_commit_at": group.get("first_commit_at"),
            "last_commit_at": group.get("last_commit_at"),
            "recent_commit_messages": group.get("recent_commit_messages", []),
            "summary": summary.summary,
            "strengths": summary.strengths,
            "collaboration_style": summary.collaboration_style,
            "evidence": summary.evidence,
            "keywords": summary.keywords,
            "focus_areas": summary.focus_areas,
            "work_area_analysis": summary.work_area_analysis,
            "confidence": summary.confidence,
            "generated_with": f"{self.summarizer.provider_name}:{self.summarizer.model_name}",
            "source_commit_shas": group.get("source_commit_shas", []),
            "updated_at": datetime.now(timezone.utc),
        }
