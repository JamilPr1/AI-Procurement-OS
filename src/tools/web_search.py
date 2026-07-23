"""Fast parallel web search."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ddgs import DDGS


class WebSearch:
    def __init__(self, pause_seconds: float = 0.2, workers: int = 6, region: str = "us-en") -> None:
        self.pause_seconds = pause_seconds
        self.workers = workers
        self.region = region

    def search(self, query: str, max_results: int = 6) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            with DDGS() as ddgs:
                for item in ddgs.text(query, max_results=max_results, region=self.region):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("href", ""),
                        "snippet": item.get("body", ""),
                        "source_query": query,
                    })
        except Exception as e:
            results.append({"error": str(e), "source_query": query})
        if self.pause_seconds:
            time.sleep(self.pause_seconds)
        return results

    def search_parallel(self, queries: list[str], max_results: int = 5) -> list[dict[str, Any]]:
        all_results: list[dict[str, Any]] = []
        seen: set[str] = set()
        with ThreadPoolExecutor(max_workers=min(self.workers, len(queries) or 1)) as pool:
            futures = {pool.submit(self.search, q, max_results): q for q in queries}
            for fut in as_completed(futures):
                for r in fut.result():
                    url = r.get("url", "")
                    if url and url not in seen and "error" not in r:
                        seen.add(url)
                        all_results.append(r)
        return all_results

    search_many = search_parallel
