from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    mongodb_db_name: str = os.getenv("MONGODB_DB_NAME", "intelligent_bug_management")
    github_token: str | None = os.getenv("GITHUB_TOKEN")
    github_api_base_url: str = os.getenv("GITHUB_API_BASE_URL", "https://api.github.com")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemma-3-27b-it")
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")
    llm_prompt_char_budget: int = int(os.getenv("LLM_PROMPT_CHAR_BUDGET", "12000"))
    llm_max_evidence_items: int = int(os.getenv("LLM_MAX_EVIDENCE_ITEMS", "20"))
    llm_recent_messages_limit: int = int(os.getenv("LLM_RECENT_MESSAGES_LIMIT", "25"))
    default_sync_pages: int = int(os.getenv("DEFAULT_SYNC_PAGES", "5"))
    default_page_size: int = int(os.getenv("DEFAULT_PAGE_SIZE", "100"))
    github_webhook_secret: str | None = os.getenv("GITHUB_WEBHOOK_SECRET")


settings = Settings()
