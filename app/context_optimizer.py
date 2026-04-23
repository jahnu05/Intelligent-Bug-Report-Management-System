from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CompressedContributorPayload:
    repository_full_name: str
    contributor_key: str
    github_login: str | None
    display_name: str | None
    commit_count: int
    first_commit_at: datetime | None
    last_commit_at: datetime | None
    sampled_messages: list[str]
    evidence_lines: list[str]
    topical_keywords: list[str]
    focus_areas: list[str]
    work_area_signals: list[str]


class CommitContextOptimizer:
    """Builds a bounded contributor payload so LLM prompts stay within limits."""

    def __init__(
        self,
        char_budget: int = 12000,
        max_evidence_items: int = 20,
        recent_messages_limit: int = 25,
    ) -> None:
        self.char_budget = max(2000, char_budget)
        self.max_evidence_items = max(5, max_evidence_items)
        self.recent_messages_limit = max(5, recent_messages_limit)

    def build_payload(
        self,
        repository_full_name: str,
        contributor_key: str,
        group: dict[str, Any],
    ) -> dict[str, Any]:
        sampled_messages = self._sample_messages(group.get("all_commit_messages", []))
        evidence_lines = self._build_evidence(group.get("source_commit_pairs", []))
        keywords = self._extract_keywords(sampled_messages)
        focus_areas, work_area_signals = self._infer_focus_areas(sampled_messages)

        payload = CompressedContributorPayload(
            repository_full_name=repository_full_name,
            contributor_key=contributor_key,
            github_login=group.get("github_login"),
            display_name=group.get("display_name"),
            commit_count=group.get("commit_count", 0),
            first_commit_at=group.get("first_commit_at"),
            last_commit_at=group.get("last_commit_at"),
            sampled_messages=sampled_messages,
            evidence_lines=evidence_lines,
            topical_keywords=keywords,
            focus_areas=focus_areas,
            work_area_signals=work_area_signals,
        )
        return {
            "repository_full_name": payload.repository_full_name,
            "contributor_key": payload.contributor_key,
            "github_login": payload.github_login,
            "display_name": payload.display_name,
            "commit_count": payload.commit_count,
            "first_commit_at": payload.first_commit_at,
            "last_commit_at": payload.last_commit_at,
            "recent_commit_messages": sampled_messages[:10],
            "sampled_messages": payload.sampled_messages,
            "evidence_lines": payload.evidence_lines,
            "keywords": payload.topical_keywords,
            "focus_areas": payload.focus_areas,
            "work_area_signals": payload.work_area_signals,
            "source_commit_pairs": group.get("source_commit_pairs", []),
            "source_commit_shas": group.get("source_commit_shas", []),
        }

    def _sample_messages(self, all_messages: list[str]) -> list[str]:
        if not all_messages:
            return []

        clean_messages = [self._clean_message(message) for message in all_messages if message]
        if len(clean_messages) <= self.recent_messages_limit:
            return clean_messages

        head_size = min(12, self.recent_messages_limit // 2)
        tail_size = min(8, self.recent_messages_limit // 3)
        remaining = max(0, self.recent_messages_limit - head_size - tail_size)

        recent = clean_messages[:head_size]
        oldest = clean_messages[-tail_size:] if tail_size > 0 else []

        middle_pool = clean_messages[head_size : len(clean_messages) - tail_size]
        unique_middle: list[str] = []
        seen_fingerprints: set[str] = set()
        for message in middle_pool:
            fingerprint = self._message_fingerprint(message)
            if fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(fingerprint)
            unique_middle.append(message)
            if len(unique_middle) >= remaining:
                break

        sampled = recent + unique_middle + oldest
        return sampled[: self.recent_messages_limit]

    def _build_evidence(self, commit_pairs: list[tuple[str, str]]) -> list[str]:
        evidence: list[str] = []
        total_chars = 0
        for sha, message in commit_pairs[: self.max_evidence_items * 3]:
            line = f"{sha[:10]}: {self._clean_message(message)}"
            next_size = total_chars + len(line)
            if len(evidence) >= self.max_evidence_items or next_size > self.char_budget // 2:
                break
            evidence.append(line)
            total_chars = next_size
        return evidence

    def _extract_keywords(self, messages: list[str]) -> list[str]:
        stop_words = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "into",
            "this",
            "that",
            "fix",
            "bug",
            "issue",
            "update",
            "merge",
            "pull",
            "request",
            "refactor",
            "changes",
            "change",
        }
        counter: Counter[str] = Counter()
        for message in messages:
            for token in message.lower().replace("/", " ").replace("_", " ").split():
                token = "".join(ch for ch in token if ch.isalnum() or ch in {"-", "."})
                if len(token) < 3 or token in stop_words:
                    continue
                counter[token] += 1
        return [token for token, _ in counter.most_common(8)]

    def _infer_focus_areas(self, messages: list[str]) -> tuple[list[str], list[str]]:
        area_rules: list[tuple[str, tuple[str, ...]]] = [
            ("Authentication and security", ("auth", "oauth", "security", "csrf", "token", "login", "credential")),
            ("Database and persistence", ("db", "database", "mongo", "sql", "query", "migration", "schema", "persistence")),
            ("API and backend services", ("api", "endpoint", "controller", "service", "rest", "http", "handler")),
            ("UI and frontend", ("ui", "frontend", "css", "html", "jsx", "react", "component", "template")),
            ("Build and CI/CD", ("build", "gradle", "maven", "pipeline", "workflow", "ci", "docker", "release")),
            ("Testing and quality", ("test", "pytest", "unittest", "coverage", "lint", "quality", "validation")),
            ("Performance and scalability", ("performance", "latency", "optimize", "cache", "throughput", "memory")),
            ("Logging and observability", ("log", "metrics", "monitor", "trace", "observability", "alert")),
            ("Documentation and developer experience", ("docs", "readme", "documentation", "example", "guide", "tutorial")),
        ]

        matched_areas: Counter[str] = Counter()
        signals: list[str] = []
        for raw_message in messages:
            message = raw_message.lower()
            for area, tokens in area_rules:
                if any(token in message for token in tokens):
                    matched_areas[area] += 1
                    if len(signals) < 12:
                        signals.append(f"{area}: {self._clean_message(raw_message)}")

        focus_areas = [area for area, _ in matched_areas.most_common(5)]
        return focus_areas, signals

    @staticmethod
    def _message_fingerprint(message: str) -> str:
        words = message.lower().split()
        return " ".join(words[:6])

    @staticmethod
    def _clean_message(message: str) -> str:
        return " ".join((message or "").split())[:180]
