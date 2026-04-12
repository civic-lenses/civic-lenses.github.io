# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""Client for the USAspending.gov API v2 (no auth required)."""

import logging
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import requests

from config import USASPENDING_BASE_URL

logger = logging.getLogger(__name__)


class USASpendingClient:
    """Fetch federal spending data from USAspending.gov."""

    def __init__(self, base_url: str = USASPENDING_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()

    def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.base_url}/{endpoint}"
        resp = self.session.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()

    # ----- Award Search -----------------------------------------------------

    def search_awards(
        self,
        keywords: list[str],
        award_type: Optional[list[str]] = None,
        page: int = 1,
        limit: int = 100,
    ) -> pd.DataFrame:
        """Search for spending awards by keyword.

        Args:
            keywords: Search terms.
            award_type: Filter by type codes, e.g. ["A","B","C","D"] for contracts.
            page: Page number (1-indexed).
            limit: Results per page (max 100).

        Returns:
            DataFrame of awards.
        """
        if award_type is None:
            award_type = ["A", "B", "C", "D"]  # default to all contract types
        filters = {"keywords": keywords, "award_type_codes": award_type}

        payload = {
            "filters": filters,
            "fields": [
                "Award ID", "Recipient Name", "Award Amount",
                "Awarding Agency", "Awarding Sub Agency",
                "Award Type", "Description", "Start Date", "End Date",
            ],
            "page": page,
            "limit": limit,
            "sort": "Award Amount",
            "order": "desc",
        }
        data = self._post("search/spending_by_award/", payload)
        results = data.get("results", [])
        if not results:
            logger.warning("No awards for keywords=%s", keywords)
            return pd.DataFrame()

        return pd.json_normalize(results)

    # ----- Spending by Agency -----------------------------------------------

    def spending_by_agency(self, fiscal_year: int = 2025) -> pd.DataFrame:
        """Get total spending grouped by agency for a fiscal year.

        Args:
            fiscal_year: Federal fiscal year.

        Returns:
            DataFrame of agencies and their spending totals.
        """
        payload = {
            "filters": {"time_period": [{"start_date": f"{fiscal_year - 1}-10-01",
                                          "end_date": f"{fiscal_year}-09-30"}]},
            "category": "awarding_agency",
            "limit": 100,
            "page": 1,
        }
        data = self._post("search/spending_by_category/", payload)
        results = data.get("results", [])
        if not results:
            return pd.DataFrame()
        return pd.json_normalize(results)

    # ----- Agency List ------------------------------------------------------

    def list_agencies(self) -> pd.DataFrame:
        """Get reference list of all federal agencies."""
        url = f"{self.base_url}/references/toptier_agencies/"
        resp = self.session.get(url, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", data)
        return pd.json_normalize(results)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = USASpendingClient()
    df = client.list_agencies()
    print(f"Fetched {len(df)} agencies")
    print(df.head())
