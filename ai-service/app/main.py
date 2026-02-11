"""FastAPI application for the AI research service."""

import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .schemas import (
    GenerateQueriesRequest, GenerateQueriesResponse,
    SearchRequest, SearchResponse, Source,
    GenerateReportRequest, GenerateReportResponse,
)
from .ai import generate_search_queries, generate_latex_report
from .search import multi_search

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="Research AI Service", version="1.0.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/generate-queries", response_model=GenerateQueriesResponse)
async def api_generate_queries(req: GenerateQueriesRequest):
    queries = generate_search_queries(
        api_key=req.api_key,
        model=req.model,
        topic=req.topic,
    )
    return GenerateQueriesResponse(queries=queries)


@app.post("/api/search", response_model=SearchResponse)
async def api_search(req: SearchRequest):
    raw = multi_search(req.queries, results_per_query=req.results_per_query)
    results = [
        Source(
            title=r.get("title", "N/A"),
            body=r.get("body", "N/A"),
            href=r.get("href", ""),
        )
        for r in raw
    ]
    return SearchResponse(results=results)


@app.post("/api/generate-report", response_model=GenerateReportResponse)
async def api_generate_report(req: GenerateReportRequest):
    sources_dicts = [s.model_dump() for s in req.sources]
    latex_body = generate_latex_report(
        api_key=req.api_key,
        model=req.model,
        topic=req.topic,
        context=req.context,
        sources=sources_dicts,
    )
    if latex_body is None:
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to generate report"},
        )
    return GenerateReportResponse(latex_body=latex_body)
