"""Orchestrator — pull raw data from all four sources and save to data/raw/."""

import argparse
import logging
import os
import sys

import pandas as pd

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import RAW_DATA_DIR
from scripts.gdelt_client import GDELTClient
from scripts.sam_client import SAMClient
from scripts.usaspending_client import USASpendingClient
from scripts.doge_client import DOGEClient

logger = logging.getLogger(__name__)


def _save(df: pd.DataFrame, name: str) -> None:
    """Save a DataFrame to data/raw/ as CSV."""
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    path = os.path.join(RAW_DATA_DIR, f"{name}.csv")
    df.to_csv(path, index=False)
    logger.info("Saved %d rows -> %s", len(df), path)


def fetch_gdelt(queries: list[str] | None = None) -> None:
    """Pull GDELT news articles for government-spending-related queries."""
    if queries is None:
        queries = [
            "government spending",
            "federal contracts",
            "government efficiency",
            "DOGE savings",
        ]
    client = GDELTClient()
    df = client.search_multiple_queries(queries, max_records=250)
    if not df.empty:
        _save(df, "gdelt_articles")


def fetch_sam() -> None:
    """Pull contract opportunities from SAM.gov."""
    client = SAMClient()
    df = client.search_opportunities(keyword="data", size=100)
    if not df.empty:
        _save(df, "sam_opportunities")


def fetch_usaspending() -> None:
    """Pull agency list and sample awards from USAspending."""
    client = USASpendingClient()

    agencies = client.list_agencies()
    if not agencies.empty:
        _save(agencies, "usaspending_agencies")

    awards = client.search_awards(keywords=["technology"], limit=100)
    if not awards.empty:
        _save(awards, "usaspending_awards")


def fetch_doge() -> None:
    """Pull all DOGE savings data (grants, contracts, leases) and payments."""
    client = DOGEClient()

    grants = client.get_cancelled_grants()
    if not grants.empty:
        _save(grants, "doge_cancelled_grants")

    contracts = client.get_cancelled_contracts()
    if not contracts.empty:
        _save(contracts, "doge_cancelled_contracts")

    leases = client.get_cancelled_leases()
    if not leases.empty:
        _save(leases, "doge_cancelled_leases")

    stats = client.get_payment_statistics()
    if stats:
        pd.json_normalize(stats).to_csv(
            os.path.join(RAW_DATA_DIR, "doge_payment_stats.csv"), index=False
        )


SOURCES = {
    "gdelt": fetch_gdelt,
    "sam": fetch_sam,
    "usaspending": fetch_usaspending,
    "doge": fetch_doge,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull raw data from all sources.")
    parser.add_argument(
        "--sources",
        nargs="*",
        choices=list(SOURCES.keys()),
        default=list(SOURCES.keys()),
        help="Which sources to fetch (default: all).",
    )
    args = parser.parse_args()

    for name in args.sources:
        logger.info("=== Fetching %s ===", name)
        try:
            SOURCES[name]()
        except Exception:
            logger.exception("Failed to fetch %s", name)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    main()
