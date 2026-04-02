"""Load and validate environment configuration."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    notion_api_key: str
    anthropic_api_key: str
    notion_root_page_id: str | None
    chroma_persist_dir: str
    log_level: str


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = _load()
    return _settings


def _load() -> Settings:
    notion_api_key = os.environ.get("NOTION_API_KEY", "")
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not notion_api_key:
        raise ValueError("NOTION_API_KEY is required")
    if not anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is required")

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

    return Settings(
        notion_api_key=notion_api_key,
        anthropic_api_key=anthropic_api_key,
        notion_root_page_id=os.environ.get("NOTION_ROOT_PAGE_ID") or None,
        chroma_persist_dir=os.environ.get("CHROMA_PERSIST_DIR", "./.chroma"),
        log_level=log_level,
    )
