"""Client for the DOGE.gov API (no auth required, beta v0.0.2)."""

import logging
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import requests
from tqdm import tqdm

from config import DOGE_BASE_URL

logger = logging.getLogger(__name__)


class DOGEClient:
    """Fetch savings and payment data from api.doge.gov."""

    MAX_PER_PAGE = 500

    def __init__(self, base_url: str = DOGE_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()

    @staticmethod
    def _extract_records(data: dict) -> list[dict]:
        """Extract the record list from a DOGE API response.

        The API wraps results like {"result": {"leases": [...]}} so we need
        to unwrap the inner list.
        """
        result = data.get("result", data.get("results", []))
        if isinstance(result, dict):
            for v in result.values():
                if isinstance(v, list):
                    return v
            return []
        return result

    def _get_paginated(
        self,
        endpoint: str,
        total_hint: int,
        sort_by: str = "savings",
        sort_order: str = "desc",
        per_page: int = 500,
    ) -> list[dict]:
        """Fetch all pages from a paginated DOGE endpoint.

        Args:
            endpoint: API path (e.g. "/savings/grants").
            total_hint: Approximate total records (used for progress bar).
            sort_by: Sort field.
            sort_order: "asc" or "desc".
            per_page: Records per page (max 500).

        Returns:
            List of record dicts.
        """
        all_records = []
        page = 1
        total_pages = max(1, math.ceil(total_hint / per_page))

        with tqdm(total=total_hint, desc=endpoint) as pbar:
            while True:
                resp = self.session.get(
                    f"{self.base_url}{endpoint}",
                    params={
                        "sort_by": sort_by,
                        "sort_order": sort_order,
                        "page": page,
                        "per_page": per_page,
                    },
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()

                records = self._extract_records(data)
                if not records:
                    break

                all_records.extend(records)
                pbar.update(len(records))

                if len(records) < per_page:
                    break
                page += 1

        return all_records

    # ----- Savings ----------------------------------------------------------

    def get_cancelled_grants(self) -> pd.DataFrame:
        """Fetch all cancelled grants (~15,887 records)."""
        records = self._get_paginated("/savings/grants", total_hint=16000)
        return pd.DataFrame(records)

    def get_cancelled_contracts(self) -> pd.DataFrame:
        """Fetch all cancelled contracts (~13,440 records)."""
        records = self._get_paginated(
            "/savings/contracts", total_hint=13500, sort_by="savings"
        )
        return pd.DataFrame(records)

    def get_cancelled_leases(self) -> pd.DataFrame:
        """Fetch all cancelled leases (~264 records)."""
        records = self._get_paginated("/savings/leases", total_hint=300)
        return pd.DataFrame(records)

    # ----- Payments ---------------------------------------------------------

    def get_payments(
        self,
        filter_field: str | None = None,
        filter_value: str | None = None,
        max_pages: int = 50,
    ) -> pd.DataFrame:
        """Fetch payment line items (~107,497 records).

        Args:
            filter_field: Optional filter — "agency_name", "date", or "org_name".
            filter_value: Value for the filter.
            max_pages: Safety cap on pages to fetch.

        Returns:
            DataFrame of payments.
        """
        all_records: list[dict] = []
        page = 1
        per_page = self.MAX_PER_PAGE

        with tqdm(desc="/payments") as pbar:
            while page <= max_pages:
                params = {
                    "sort_by": "date",
                    "sort_order": "desc",
                    "page": page,
                    "per_page": per_page,
                }
                if filter_field and filter_value:
                    params["filter"] = filter_field
                    params["filter_value"] = filter_value

                resp = self.session.get(
                    f"{self.base_url}/payments", params=params, timeout=60
                )
                resp.raise_for_status()
                data = resp.json()

                records = self._extract_records(data)
                if not records:
                    break

                all_records.extend(records)
                pbar.update(len(records))

                if len(records) < per_page:
                    break
                page += 1

        return pd.DataFrame(all_records)

    def get_payment_statistics(self) -> dict:
        """Fetch aggregated payment statistics."""
        resp = self.session.get(
            f"{self.base_url}/payments/statistics", timeout=60
        )
        resp.raise_for_status()
        return resp.json()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = DOGEClient()
    df = client.get_cancelled_leases()
    print(f"Fetched {len(df)} cancelled leases")
    print(df.head())
