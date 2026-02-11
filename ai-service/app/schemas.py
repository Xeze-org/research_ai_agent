"""Pydantic request/response models for the AI service."""

from pydantic import BaseModel
from typing import List


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class Source(BaseModel):
    title: str = "N/A"
    body: str = "N/A"
    href: str = ""


# ---------------------------------------------------------------------------
# /api/generate-queries
# ---------------------------------------------------------------------------

class GenerateQueriesRequest(BaseModel):
    topic: str
    model: str = "mistral-medium-latest"
    api_key: str


class GenerateQueriesResponse(BaseModel):
    queries: List[str]


# ---------------------------------------------------------------------------
# /api/search
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    queries: List[str]
    results_per_query: int = 5


class SearchResponse(BaseModel):
    results: List[Source]


# ---------------------------------------------------------------------------
# /api/generate-report
# ---------------------------------------------------------------------------

class GenerateReportRequest(BaseModel):
    topic: str
    model: str = "mistral-medium-latest"
    api_key: str
    context: str
    sources: List[Source]


class GenerateReportResponse(BaseModel):
    latex_body: str
