from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, UpdateOne


class DatabaseInitializer:
    def __init__(self, db) -> None:
        self.db = db

    def ensure_indexes(self) -> None:
        self.db.repositories.create_index([("full_name", ASCENDING)], unique=True)
        self.db.contributors.create_index(
            [("repository_full_name", ASCENDING), ("contributor_key", ASCENDING)],
            unique=True,
        )
        self.db.commits.create_index(
            [("repository_full_name", ASCENDING), ("sha", ASCENDING)],
            unique=True,
        )
        self.db.sync_runs.create_index(
            [("repository_full_name", ASCENDING), ("started_at", DESCENDING)]
        )
        self.db.issues.create_index(
            [("repository_full_name", ASCENDING), ("issue_number", ASCENDING)],
            unique=True,
        )
        self.db.assignments.create_index(
            [("repository_full_name", ASCENDING), ("issue_number", ASCENDING)],
            unique=True,
        )
        self.db.assignments.create_index(
            [("repository_full_name", ASCENDING), ("generated_at", DESCENDING)]
        )


class RepositoryStore:
    def __init__(self, db) -> None:
        self.collection = db.repositories

    def upsert_repository(self, document: dict[str, Any]) -> None:
        self.collection.update_one(
            {"full_name": document["full_name"]},
            {"$set": document},
            upsert=True,
        )

    def get_repository(self, full_name: str) -> dict[str, Any] | None:
        return self.collection.find_one({"full_name": full_name}, {"_id": 0})

    def update_sync_state(self, full_name: str, status: str, error: str | None = None) -> None:
        update = {
            "sync_status": status,
            "last_synced_at": datetime.now(timezone.utc),
        }
        if error is not None:
            update["sync_error"] = error
        self.collection.update_one({"full_name": full_name}, {"$set": update}, upsert=True)

    def set_statistics(self, full_name: str, commit_count: int, contributor_count: int) -> None:
        self.collection.update_one(
            {"full_name": full_name},
            {
                "$set": {
                    "commit_count": commit_count,
                    "contributor_count": contributor_count,
                    "last_synced_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )


class CommitStore:
    def __init__(self, db) -> None:
        self.collection = db.commits

    def upsert_commits(self, commits: list[dict[str, Any]]) -> int:
        if not commits:
            return 0
        operations = []
        for commit in commits:
            operations.append(
                UpdateOne(
                    {"repository_full_name": commit["repository_full_name"], "sha": commit["sha"]},
                    {"$set": commit},
                    upsert=True,
                )
            )
        result = self.collection.bulk_write(operations, ordered=False)
        return result.upserted_count + result.modified_count

    def list_commits(
        self,
        repository_full_name: str,
        contributor_key: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"repository_full_name": repository_full_name}
        if contributor_key:
            query["contributor_key"] = contributor_key
        return list(self.collection.find(query, {"_id": 0}).sort("authored_at", DESCENDING).limit(limit))

    def list_contributor_keys(self, repository_full_name: str) -> list[str]:
        return list(self.collection.distinct("contributor_key", {"repository_full_name": repository_full_name}))


class ContributorStore:
    def __init__(self, db) -> None:
        self.collection = db.contributors

    def upsert_profile(self, document: dict[str, Any]) -> None:
        self.collection.update_one(
            {
                "repository_full_name": document["repository_full_name"],
                "contributor_key": document["contributor_key"],
            },
            {"$set": document},
            upsert=True,
        )

    def get_profile(self, repository_full_name: str, contributor_key: str) -> dict[str, Any] | None:
        return self.collection.find_one(
            {"repository_full_name": repository_full_name, "contributor_key": contributor_key},
            {"_id": 0},
        )

    def list_profiles(self, repository_full_name: str) -> list[dict[str, Any]]:
        return list(
            self.collection.find({"repository_full_name": repository_full_name}, {"_id": 0}).sort(
                [("commit_count", DESCENDING), ("last_commit_at", DESCENDING)]
            )
        )

    def clear_summaries(self, repository_full_name: str | None = None) -> int:
        query: dict[str, Any] = {}
        if repository_full_name:
            query["repository_full_name"] = repository_full_name

        result = self.collection.update_many(
            query,
            {
                "$set": {
                    "summary": "",
                    "strengths": [],
                    "collaboration_style": "",
                    "evidence": [],
                    "keywords": [],
                    "focus_areas": [],
                    "work_area_analysis": "",
                    "confidence": "low",
                    "generated_with": "",
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.modified_count


class SyncRunStore:
    def __init__(self, db) -> None:
        self.collection = db.sync_runs

    def create_run(self, repository_full_name: str, triggered_by: str = "api") -> ObjectId:
        document = {
            "repository_full_name": repository_full_name,
            "triggered_by": triggered_by,
            "status": "running",
            "started_at": datetime.now(timezone.utc),
            "finished_at": None,
            "message": None,
        }
        return self.collection.insert_one(document).inserted_id

    def finish_run(self, run_id: ObjectId, status: str, message: str) -> None:
        self.collection.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "status": status,
                    "finished_at": datetime.now(timezone.utc),
                    "message": message,
                }
            },
        )


class IssueStore:
    def __init__(self, db) -> None:
        self.collection = db.issues

    def upsert_issue(self, document: dict[str, Any]) -> None:
        self.collection.update_one(
            {
                "repository_full_name": document["repository_full_name"],
                "issue_number": document["issue_number"],
            },
            {"$set": document},
            upsert=True,
        )

    def get_issue(self, repository_full_name: str, issue_number: int) -> dict[str, Any] | None:
        return self.collection.find_one(
            {"repository_full_name": repository_full_name, "issue_number": issue_number},
            {"_id": 0},
        )

    def list_issues(self, repository_full_name: str, limit: int = 50) -> list[dict[str, Any]]:
        return list(
            self.collection.find({"repository_full_name": repository_full_name}, {"_id": 0})
            .sort("updated_at", DESCENDING)
            .limit(limit)
        )


class AssignmentStore:
    def __init__(self, db) -> None:
        self.collection = db.assignments

    def upsert_assignment(self, document: dict[str, Any]) -> None:
        self.collection.update_one(
            {
                "repository_full_name": document["repository_full_name"],
                "issue_number": document["issue_number"],
            },
            {"$set": document},
            upsert=True,
        )

    def get_assignment(self, repository_full_name: str, issue_number: int) -> dict[str, Any] | None:
        return self.collection.find_one(
            {"repository_full_name": repository_full_name, "issue_number": issue_number},
            {"_id": 0},
        )

    def list_assignments(self, repository_full_name: str, limit: int = 50) -> list[dict[str, Any]]:
        return list(
            self.collection.find({"repository_full_name": repository_full_name}, {"_id": 0})
            .sort("generated_at", DESCENDING)
            .limit(limit)
        )
