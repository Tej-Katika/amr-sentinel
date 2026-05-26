"""Shared per-request context for tool execution."""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx


@dataclass
class ToolContext:
    facility_id: str
    user_id: str
    intelligence_url: str = os.getenv("INTELLIGENCE_SERVICE_URL", "http://localhost:8002")

    def http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.intelligence_url, timeout=30.0)
