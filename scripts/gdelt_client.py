# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""Client for the GDELT Project API v2 (no auth required)."""

import logging
import os
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import requests

from config import GDELT_DOC_URL

logger = logging.getLogger(__name__)


class GDELTClient:
    """Fetch articles and events from GDELT's DOC API."""

    def __init__(self, base_url: str = GDELT_DOC_URL):
        self.base_url = base_url
        self.session = requests.Session()

    def search_articles(
        self,
        query: str,
        mode: str = "ArtList",
        max_records: int = 250,
        timespan: str = "3months",
        format: str = "json",
    ) -> pd.DataFrame:
        """Search GDELT for news articles matching a query.

        Args:
            query: Search keywords (e.g. "government spending").
            mode: One of ArtList, TimelineVol, TimelineSourceCountry, etc.
            max_records: Maximum articles to return (up to 250 per call).
            timespan: Lookback window, e.g. "3months", "1year", "30days".
            format: Response format — "json" or "csv".

        Returns:
            DataFrame of matching articles.
        """
        params = {
            "query": query,
            "mode": mode,
            "maxrecords": max_records,
            "timespan": timespan,
            "format": format,
        }
        for attempt in range(3):
            resp = self.session.get(self.base_url, params=params, timeout=60)
            if resp.status_code == 429:
                wait = 2 ** attempt * 5
                logger.warning("GDELT rate limited, retrying in %ds...", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        else:
            resp.raise_for_status()

        data = resp.json()
        articles = data.get("articles", [])
        if not articles:
            logger.warning("No articles returned for query=%s", query)
            return pd.DataFrame()

        return pd.DataFrame(articles)

    def search_multiple_queries(
        self,
        queries: list[str],
        delay: float = 1.0,
        **kwargs,
    ) -> pd.DataFrame:
        """Run multiple queries and concatenate results.

        Args:
            queries: List of search terms.
            delay: Seconds to wait between requests (be polite).
            **kwargs: Forwarded to search_articles.
        """
        frames = []
        for q in queries:
            logger.info("GDELT query: %s", q)
            df = self.search_articles(q, **kwargs)
            if not df.empty:
                df["query"] = q
                frames.append(df)
            time.sleep(delay)

        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = GDELTClient()
    df = client.search_articles("government spending", max_records=10)
    print(f"Fetched {len(df)} articles")
    print(df.head())
