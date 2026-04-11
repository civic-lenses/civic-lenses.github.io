# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""Client for the SAM.gov API (requires free API key)."""

import logging
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import requests

from config import SAM_API_KEY, SAM_ENTITIES_URL, SAM_OPPORTUNITIES_URL

logger = logging.getLogger(__name__)


class SAMClient:
    """Fetch entity registrations and contract opportunities from SAM.gov."""

    def __init__(self, api_key: str = SAM_API_KEY):
        if not api_key:
            raise ValueError(
                "SAM.gov API key is required. Set SAM_GOV_API_KEY in your .env file. "
                "Register at https://sam.gov/content/home"
            )
        self.api_key = api_key
        self.session = requests.Session()

    # ----- Entity Information ------------------------------------------------

    def search_entities(
        self,
        keyword: Optional[str] = None,
        naics_code: Optional[str] = None,
        state: Optional[str] = None,
        page: int = 0,
        size: int = 100,
    ) -> pd.DataFrame:
        """Search SAM.gov entity registrations.

        Args:
            keyword: Free-text search.
            naics_code: NAICS industry code filter.
            state: Two-letter state abbreviation.
            page: Page number (0-indexed).
            size: Results per page (max 100).

        Returns:
            DataFrame of matching entities.
        """
        params = {
            "api_key": self.api_key,
            "page": page,
            "size": size,
        }
        if keyword:
            params["q"] = keyword
        if naics_code:
            params["naicsCode"] = naics_code
        if state:
            params["physicalAddressProvinceOrStateCode"] = state

        resp = self.session.get(SAM_ENTITIES_URL, params=params, timeout=60)
        resp.raise_for_status()

        data = resp.json()
        entities = data.get("entityData", [])
        if not entities:
            logger.warning("No entities returned for keyword=%s", keyword)
            return pd.DataFrame()

        return pd.json_normalize(entities)

    # ----- Contract Opportunities -------------------------------------------

    def search_opportunities(
        self,
        keyword: Optional[str] = None,
        posted_from: Optional[str] = None,
        posted_to: Optional[str] = None,
        page: int = 0,
        size: int = 100,
    ) -> pd.DataFrame:
        """Search SAM.gov contract opportunities.

        Args:
            keyword: Free-text search.
            posted_from: Start date (MM/dd/yyyy).
            posted_to: End date (MM/dd/yyyy).
            page: Page number (0-indexed).
            size: Results per page.

        Returns:
            DataFrame of opportunities.
        """
        params = {
            "api_key": self.api_key,
            "limit": size,
            "offset": page * size,
        }
        if keyword:
            params["q"] = keyword
        if posted_from:
            params["postedFrom"] = posted_from
        if posted_to:
            params["postedTo"] = posted_to

        resp = self.session.get(SAM_OPPORTUNITIES_URL, params=params, timeout=60)
        resp.raise_for_status()

        data = resp.json()
        opps = data.get("opportunitiesData", [])
        if not opps:
            logger.warning("No opportunities for keyword=%s", keyword)
            return pd.DataFrame()

        return pd.json_normalize(opps)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = SAMClient()
    df = client.search_opportunities(keyword="data analytics", size=5)
    print(f"Fetched {len(df)} opportunities")
    print(df.head())
