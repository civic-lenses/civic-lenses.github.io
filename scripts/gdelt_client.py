# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""Client for the GDELT Project API v2 (no auth required)."""

import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import requests

from config import GDELT_DOC_URL

logger = logging.getLogger(__name__)

# GDELT DOC API supports these timespan shorthand values
# We default to 30 days — enough for sustained trend detection
DEFAULT_TIMESPAN = "30days"


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
        timespan: Optional[str] = DEFAULT_TIMESPAN,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        format: str = "json",
    ) -> pd.DataFrame:
        """Search GDELT for news articles matching a query.

        Args:
            query:       Search keywords (e.g. "government spending").
            mode:        One of ArtList, TimelineVol, TimelineSourceCountry.
            max_records: Maximum articles to return (up to 250 per call).
            timespan:    Shorthand window e.g. "7days", "30days", "3months".
                         Ignored if start_date/end_date are provided.
            start_date:  Explicit start in "YYYY-MM-DD" format (optional).
                         If provided, end_date must also be provided.
            end_date:    Explicit end in "YYYY-MM-DD" format (optional).
            format:      Response format — "json" or "csv".

        Returns:
            DataFrame of matching articles with a parsed `seendate` column.

        Note:
            GDELT DOC API officially supports the most recent 3 months.
            Requests beyond that may return partial or no data.
        """
        params = {
            "query":      query,
            "mode":       mode,
            "maxrecords": max_records,
            "format":     format,
        }

        # Explicit date range takes priority over timespan shorthand
        if start_date and end_date:
            # GDELT expects: YYYYMMDDHHMMSS
            params["startdatetime"] = _to_gdelt_dt(start_date)
            params["enddatetime"]   = _to_gdelt_dt(end_date, end_of_day=True)
            logger.info(
                "GDELT query '%s' | window: %s → %s", query, start_date, end_date
            )
        else:
            params["timespan"] = timespan or DEFAULT_TIMESPAN
            logger.info(
                "GDELT query '%s' | timespan: %s", query, params["timespan"]
            )

        max_retries = 8
        for attempt in range(max_retries):
            resp = self.session.get(self.base_url, params=params, timeout=60)
            if resp.status_code == 429:
                wait = min(2 ** attempt * 15, 600)  # 15, 30, 60, 120, 240, 480, 600, 600
                logger.warning("GDELT rate limited, retrying in %ds...", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        else:
            logger.error(
                "GDELT rate limit not resolved after %d retries for query='%s'; skipping.",
                max_retries, query,
            )
            return pd.DataFrame()

        data = resp.json()
        articles = data.get("articles", [])
        if not articles:
            logger.warning("No articles returned for query='%s'", query)
            return pd.DataFrame()

        df = pd.DataFrame(articles)

        # Parse seendate → proper datetime for downstream scoring
        if "seendate" in df.columns:
            df["seendate_parsed"] = pd.to_datetime(
                df["seendate"], format="%Y%m%dT%H%M%SZ", utc=True, errors="coerce"
            )

        return df

    def search_multiple_queries(
        self,
        queries: list[str],
        delay: float = 10.0,
        days: int = 30,
        **kwargs,
    ) -> pd.DataFrame:
        """Run multiple queries over a rolling window and concatenate results.

        Args:
            queries: List of search terms.
            delay:   Seconds to wait between requests (be polite to GDELT).
            days:    Rolling lookback window in days (default 30).
                     Overrides any `timespan` passed in kwargs.
            **kwargs: Forwarded to search_articles (except timespan).

        Returns:
            Combined DataFrame with a `query` column identifying the source.
        """
        # Build explicit date range from `days` parameter
        end_dt   = datetime.now(tz=timezone.utc)
        start_dt = end_dt - timedelta(days=days)
        start_date = start_dt.strftime("%Y-%m-%d")
        end_date   = end_dt.strftime("%Y-%m-%d")

        logger.info(
            "Fetching %d queries over %d-day window (%s → %s)",
            len(queries), days, start_date, end_date,
        )

        # Remove timespan from kwargs if caller passed it — date range wins
        kwargs.pop("timespan", None)

        frames = []
        for q in queries:
            df = self.search_articles(
                q,
                start_date=start_date,
                end_date=end_date,
                **kwargs,
            )
            if not df.empty:
                df["query"] = q
                frames.append(df)
            time.sleep(delay)

        if not frames:
            logger.warning("No articles fetched across all queries.")
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True)
        logger.info(
            "Fetched %d total articles across %d queries",
            len(combined), len(frames),
        )
        return combined


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _to_gdelt_dt(date_str: str, end_of_day: bool = False) -> str:
    """Convert 'YYYY-MM-DD' to GDELT's 'YYYYMMDDHHMMSS' format.

    Args:
        date_str:   Date string in YYYY-MM-DD format.
        end_of_day: If True, sets time to 23:59:59 (for end date).
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return dt.strftime("%Y%m%d%H%M%S")


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    client = GDELTClient()

    # Test 1: single query with 7-day window
    print("\n--- Single query, 7-day window ---")
    df = client.search_articles(
        "government spending",
        max_records=10,
        start_date=(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        end_date=datetime.now().strftime("%Y-%m-%d"),
    )
    print(f"Fetched {len(df)} articles")
    if not df.empty:
        print(df[["title", "seendate", "sourcecountry"]].head(3))

    # Test 2: multiple queries with 30-day window (what orchestrator calls)
    print("\n--- Multiple queries, 30-day window ---")
    queries = ["government spending", "federal contracts", "DOGE savings"]
    df2 = client.search_multiple_queries(queries, days=30, max_records=50)
    print(f"Fetched {len(df2)} total articles")
    if not df2.empty:
        print(df2.groupby("query")["url"].count().rename("article_count"))
