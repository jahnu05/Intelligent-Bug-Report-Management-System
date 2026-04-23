from __future__ import annotations

from abc import ABC, abstractmethod
import json
from dataclasses import dataclass
from typing import Any

from .config import settings


@dataclass(frozen=True)
class SummaryPayload:
    summary: str
    strengths: list[str]
    collaboration_style: str
    evidence: list[str]
    keywords: list[str]
    focus_areas: list[str]
    work_area_analysis: str
    confidence: str


@dataclass(frozen=True)
class AssignmentPayload:
    assigned_contributor_key: str
    assigned_github_login: str | None
    rationale: str
    confidence: str
    alternatives: list[dict[str, Any]]


class LLMProviderStrategy(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def summarize_contributor(self, payload: dict[str, Any]) -> SummaryPayload:
        raise NotImplementedError

    @abstractmethod
    def assign_issue(self, payload: dict[str, Any]) -> AssignmentPayload:
        raise NotImplementedError


class GeminiProviderStrategy(LLMProviderStrategy):
    def __init__(self, api_key: str | None = None, model_name: str | None = None) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self._model_name = model_name or settings.gemini_model
        self._model = None

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    def _ensure_model(self):
        if not self.api_key:
            return None
        if self._model is None:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel(self.model_name)
        return self._model

    def summarize_contributor(self, payload: dict[str, Any]) -> SummaryPayload:
        model = self._ensure_model()
        if model is None:
            return self._fallback_summary(payload)

        prompt = self._build_prompt(payload)
        response = model.generate_content(prompt)
        text = (getattr(response, "text", "") or "").strip()
        parsed = self._parse_json(text)
        if parsed is None:
            return self._fallback_summary(payload, raw_text=text)
        return SummaryPayload(
            summary=parsed.get("summary", ""),
            strengths=list(parsed.get("strengths", [])),
            collaboration_style=parsed.get("collaboration_style", ""),
            evidence=list(parsed.get("evidence", [])),
            keywords=list(parsed.get("keywords", [])),
            focus_areas=list(parsed.get("focus_areas", payload.get("focus_areas", []))),
            work_area_analysis=parsed.get("work_area_analysis", ""),
            confidence=parsed.get("confidence", "medium"),
        )

    def assign_issue(self, payload: dict[str, Any]) -> AssignmentPayload:
        model = self._ensure_model()
        if model is None:
            return self._fallback_assignment(payload)

        prompt = self._build_assignment_prompt(payload)
        response = model.generate_content(prompt)
        text = (getattr(response, "text", "") or "").strip()
        parsed = self._parse_json(text)
        if parsed is None:
            return self._fallback_assignment(payload)

        assigned_key = parsed.get("assigned_contributor_key")
        assigned_login = parsed.get("assigned_github_login")
        if not assigned_key and not assigned_login:
            return self._fallback_assignment(payload)
        resolved_key, resolved_login = self._resolve_candidate(payload, assigned_key, assigned_login)

        return AssignmentPayload(
            assigned_contributor_key=resolved_key,
            assigned_github_login=resolved_login,
            rationale=parsed.get("rationale", ""),
            confidence=parsed.get("confidence", "medium"),
            alternatives=list(parsed.get("alternatives", [])),
        )

    def _build_prompt(self, payload: dict[str, Any]) -> str:
        return (
            "You are generating a detailed contributor profile for an engineering analytics system.\n"
            "Use only the evidence provided. Do not invent facts or speculate.\n"
            "Return STRICT JSON only with these keys: summary, strengths, collaboration_style, evidence, keywords, focus_areas, work_area_analysis, confidence.\n"
            "- summary: 5-8 sentences with explicit mention of systems/components they work on\n"
            "- strengths: array of specific engineering strengths tied to evidence\n"
            "- collaboration_style: one short paragraph\n"
            "- evidence: array of commit-based evidence strings\n"
            "- keywords: array of technical keywords\n"
            "- focus_areas: array with 3-6 concrete parts of the codebase/domain they work in\n"
            "- work_area_analysis: detailed paragraph describing contributor ownership zones and recurring technical themes\n"
            "- confidence: one of low, medium, high\n\n"
            f"Contributor payload:\n{json.dumps(payload, indent=2, default=str)}"
        )

    def _build_assignment_prompt(self, payload: dict[str, Any]) -> str:
        return (
            "You are assigning a GitHub issue to the best contributor candidate based on contributor summaries.\n"
            "Use only the given issue details and contributor context.\n"
            "Return STRICT JSON with keys: assigned_contributor_key, assigned_github_login, rationale, confidence, alternatives.\n"
            "- assigned_contributor_key: one key from the provided candidates\n"
            "- assigned_github_login: github login if available for selected candidate\n"
            "- rationale: 4-7 sentences connecting issue scope to contributor strengths/focus areas\n"
            "- confidence: one of low, medium, high\n"
            "- alternatives: array of up to 3 objects {contributor_key, github_login, reason}\n\n"
            f"Assignment payload:\n{json.dumps(payload, indent=2, default=str)}"
        )

    def _parse_json(self, text: str) -> dict[str, Any] | None:
        if not text:
            return None
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json\n", "", 1).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None

    def _fallback_summary(self, payload: dict[str, Any], raw_text: str | None = None) -> SummaryPayload:
        contributor = payload.get("display_name") or payload.get("github_login") or payload.get("contributor_key")
        commit_count = payload.get("commit_count", 0)
        repo = payload.get("repository_full_name", "the repository")
        top_messages = payload.get("recent_commit_messages", [])[:3]
        summary = (
            f"{contributor} contributed {commit_count} commit(s) to {repo}. "
            f"Recent work includes: {', '.join(top_messages) if top_messages else 'commit activity was present but no messages were available'}."
        )
        if raw_text:
            summary = f"{summary} Gemini output could not be parsed, so a deterministic fallback was used."
        return SummaryPayload(
            summary=summary,
            strengths=["Commit activity captured from GitHub history"],
            collaboration_style="Derived from commit metadata only.",
            evidence=[f"{sha}: {msg}" for sha, msg in payload.get("source_commit_pairs", [])][:5],
            keywords=payload.get("keywords", []),
            focus_areas=list(payload.get("focus_areas", []))[:5],
            work_area_analysis=(
                "Work areas were inferred from commit message patterns and may be incomplete because file-level"
                " commit details were not expanded in this fallback mode."
            ),
            confidence="low",
        )

    def _fallback_assignment(self, payload: dict[str, Any]) -> AssignmentPayload:
        contributors = payload.get("contributors", [])
        if not contributors:
            return AssignmentPayload(
                assigned_contributor_key="",
                assigned_github_login=None,
                rationale="No contributor data is available to generate an assignment.",
                confidence="low",
                alternatives=[],
            )

        best = sorted(contributors, key=lambda c: c.get("commit_count", 0), reverse=True)[0]
        return AssignmentPayload(
            assigned_contributor_key=best.get("contributor_key", ""),
            assigned_github_login=best.get("github_login"),
            rationale=(
                "Fallback assignment selected the highest-activity contributor because LLM output was unavailable "
                "or not parseable."
            ),
            confidence="low",
            alternatives=[
                {
                    "contributor_key": c.get("contributor_key"),
                    "github_login": c.get("github_login"),
                    "reason": "High commit activity fallback ranking",
                }
                for c in sorted(contributors, key=lambda item: item.get("commit_count", 0), reverse=True)[1:4]
            ],
        )

    def _resolve_candidate(
        self,
        payload: dict[str, Any],
        assigned_key: str | None,
        assigned_login: str | None,
    ) -> tuple[str, str | None]:
        contributors = payload.get("contributors", [])
        by_key = {item.get("contributor_key"): item for item in contributors}
        by_login = {
            item.get("github_login", "").lower(): item
            for item in contributors
            if item.get("github_login")
        }
        if assigned_key and assigned_key in by_key:
            contributor = by_key[assigned_key]
            return contributor.get("contributor_key", ""), contributor.get("github_login")
        if assigned_login and assigned_login.lower() in by_login:
            contributor = by_login[assigned_login.lower()]
            return contributor.get("contributor_key", ""), contributor.get("github_login")

        if contributors:
            top = sorted(contributors, key=lambda c: c.get("commit_count", 0), reverse=True)[0]
            return top.get("contributor_key", ""), top.get("github_login")
        return "", None


class DeterministicProviderStrategy(LLMProviderStrategy):
    """Backup strategy for environments where LLM credentials are unavailable."""

    @property
    def provider_name(self) -> str:
        return "deterministic"

    @property
    def model_name(self) -> str:
        return "deterministic-v1"

    def summarize_contributor(self, payload: dict[str, Any]) -> SummaryPayload:
        contributor = payload.get("display_name") or payload.get("github_login") or payload.get("contributor_key")
        commit_count = payload.get("commit_count", 0)
        repo = payload.get("repository_full_name", "the repository")
        messages = payload.get("sampled_messages", [])[:3]
        summary = (
            f"{contributor} contributed {commit_count} commit(s) to {repo}. "
            f"Representative commits include: {', '.join(messages) if messages else 'no commit message samples available'}."
        )
        return SummaryPayload(
            summary=summary,
            strengths=["Consistent commit activity captured by pipeline"],
            collaboration_style="Derived deterministically from commit metadata.",
            evidence=list(payload.get("evidence_lines", []))[:5],
            keywords=list(payload.get("keywords", []))[:8],
            focus_areas=list(payload.get("focus_areas", []))[:5],
            work_area_analysis=(
                f"Likely work areas include {', '.join(payload.get('focus_areas', [])[:5]) or 'general maintenance'} "
                "based on recurring terms in commit messages and evidence lines."
            ),
            confidence="low",
        )

    def assign_issue(self, payload: dict[str, Any]) -> AssignmentPayload:
        contributors = payload.get("contributors", [])
        issue_text = f"{payload.get('issue_title', '')} {payload.get('issue_body', '')}".lower()
        if not contributors:
            return AssignmentPayload(
                assigned_contributor_key="",
                assigned_github_login=None,
                rationale="No contributors available for deterministic assignment.",
                confidence="low",
                alternatives=[],
            )

        def score(contributor: dict[str, Any]) -> int:
            points = int(contributor.get("commit_count", 0))
            for area in contributor.get("focus_areas", []):
                if area.lower() in issue_text:
                    points += 10
            for keyword in contributor.get("keywords", []):
                if str(keyword).lower() in issue_text:
                    points += 5
            return points

        ranked = sorted(contributors, key=score, reverse=True)
        selected = ranked[0]
        alternatives = [
            {
                "contributor_key": item.get("contributor_key"),
                "github_login": item.get("github_login"),
                "reason": "Secondary deterministic match by commit and keyword overlap",
            }
            for item in ranked[1:4]
        ]
        return AssignmentPayload(
            assigned_contributor_key=selected.get("contributor_key", ""),
            assigned_github_login=selected.get("github_login"),
            rationale=(
                "Deterministic assignment selected the contributor with the strongest overlap between issue text "
                "and contributor focus areas/keywords, weighted by commit activity."
            ),
            confidence="low",
            alternatives=alternatives,
        )


class ProviderFactory:
    """Simple strategy selector for LLM providers."""

    @staticmethod
    def create(provider_name: str) -> LLMProviderStrategy:
        normalized = (provider_name or "").strip().lower()
        if normalized == "gemini":
            if settings.gemini_api_key:
                return GeminiProviderStrategy(settings.gemini_api_key, settings.gemini_model)
            return DeterministicProviderStrategy()
        if normalized == "deterministic":
            return DeterministicProviderStrategy()
        raise ValueError(f"Unsupported LLM_PROVIDER '{provider_name}'. Use 'gemini' or 'deterministic'.")
