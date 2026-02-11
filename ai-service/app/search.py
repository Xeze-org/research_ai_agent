"""Web search via DuckDuckGo with retry logic."""

import logging
from typing import List, Dict

from duckduckgo_search import DDGS
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("ai_service.search")

MAX_RETRIES = 3


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _search_web(query: str, max_results: int) -> List[Dict]:
    results = DDGS().text(query, max_results=max_results)
    return results if results else []


def search_web(query: str, max_results: int = 5) -> List[Dict]:
    """Run a single search query with retries, return results or []."""
    try:
        return _search_web(query, max_results)
    except Exception as exc:
        logger.warning("Search failed after retries for '%s': %s", query, exc)
        return []


def multi_search(queries: List[str], results_per_query: int = 5) -> List[Dict]:
    """Run several search queries and de-duplicate by URL."""
    all_results: List[Dict] = []
    seen_urls: set = set()
    for q in queries:
        for r in search_web(q, max_results=results_per_query):
            url = r.get("href", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)
    return all_results
