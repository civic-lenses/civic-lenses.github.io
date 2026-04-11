# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""
Preprocessing & Join Pipeline
==============================
Merges all four raw data sources into one unified contract dataset
ready for model training and inference.

Output: data/processed/unified_contracts.csv

Schema of unified_contracts.csv:
  contract_id        - unique identifier
  item_type          - 'contract', 'grant', or 'lease'
  agency             - awarding agency (normalized)
  vendor_recipient   - vendor (contracts) or recipient (grants)
  description        - plain-text description
  value              - total contract/grant value ($)
  savings            - DOGE claimed savings ($)
  deleted_date       - date DOGE terminated it
  doge_flag          - 1 if terminated by DOGE, 0 otherwise
  doge_scrutiny_score - normalized savings/value ratio (0-1)
  agency_obligated_amount - from USASpending agencies
  agency_outlay_amount    - from USASpending agencies
  gdelt_popularity_score  - recency-weighted news score (0-1)
  gdelt_article_count     - raw article count for topic
  topic              - mapped topic category
  description_length - character count of description
  transparency_score - readability proxy (0-1, higher = clearer)
"""

from __future__ import annotations

import logging
import math
import os
import re
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RAW_DIR       = os.path.join("data", "raw")
PROCESSED_DIR = os.path.join("data", "processed")

RAW_FILES = {
    "contracts": os.path.join(RAW_DIR, "doge_cancelled_contracts.csv"),
    "grants":    os.path.join(RAW_DIR, "doge_cancelled_grants.csv"),
    "leases":    os.path.join(RAW_DIR, "doge_cancelled_leases.csv"),
    "agencies":  os.path.join(RAW_DIR, "usaspending_agencies.csv"),
    "gdelt":     os.path.join(RAW_DIR, "gdelt_articles.csv"),
}

OUTPUT_PATH = os.path.join(PROCESSED_DIR, "unified_contracts.csv")

# ---------------------------------------------------------------------------
# Topic mapping (GDELT query → topic label)
# ---------------------------------------------------------------------------
QUERY_TO_TOPIC = {
    "government spending":   "general_spending",
    "federal contracts":     "federal_contracts",
    "government efficiency": "government_efficiency",
    "DOGE savings":          "doge_scrutiny",
    "federal budget cuts":   "government_efficiency",
    "government waste":      "government_efficiency",
    "healthcare spending":   "healthcare",
    "defense contracts":     "defense",
    "education funding":     "education",
    "infrastructure":        "infrastructure",
    "foreign aid":           "foreign_aid",
    "scientific research":   "research",
}

# Agency name keywords → topic
AGENCY_TO_TOPIC = {
    "health":         "healthcare",
    "hhs":            "healthcare",
    "medicare":       "healthcare",
    "medicaid":       "healthcare",
    "defense":        "defense",
    "military":       "defense",
    "army":           "defense",
    "navy":           "defense",
    "air force":      "defense",
    "education":      "education",
    "transportation": "infrastructure",
    "energy":         "energy",
    "agriculture":    "agriculture",
    "usaid":          "foreign_aid",
    "interior":       "general_spending",
    "treasury":       "finance",
    "homeland":       "defense",
    "veterans":       "healthcare",
    "commerce":       "general_spending",
    "labor":          "general_spending",
    "justice":        "general_spending",
    "state":          "foreign_aid",
    "nasa":           "research",
    "epa":            "general_spending",
    "housing":        "general_spending",
}

# Jargon words that hurt transparency score
JARGON_WORDS = {
    "synergize", "leverage", "stakeholder", "deliverable", "paradigm",
    "bandwidth", "ecosystem", "holistic", "actionable", "robust",
    "scalable", "streamline", "optimize", "facilitate", "utilize",
    "strategic", "alignment", "cross-functional", "best practices",
    "value-added", "proactive", "initiative", "framework", "innovative",
    "solution", "empower", "dynamic", "cutting-edge", "mission-critical",
}


# ===========================================================================
# Step 1 — Load raw files
# ===========================================================================

def load_raw() -> dict[str, pd.DataFrame]:
    dfs = {}
    for name, path in RAW_FILES.items():
        if not os.path.exists(path):
            logger.warning("Missing raw file: %s — skipping", path)
            dfs[name] = pd.DataFrame()
            continue
        dfs[name] = pd.read_csv(path)
        logger.info("Loaded %s: %d rows", name, len(dfs[name]))
    return dfs


# ===========================================================================
# Step 2 — Normalize each DOGE source into a common schema
# ===========================================================================

def normalize_contracts(df: pd.DataFrame) -> pd.DataFrame:
    """DOGE cancelled contracts → unified schema."""
    if df.empty:
        return df
    out = pd.DataFrame()
    out["contract_id"]      = "DOGE_C_" + df.index.astype(str).str.zfill(6)
    out["item_type"]        = "contract"
    out["agency"]           = df["agency"].fillna("Unknown").str.strip()
    out["vendor_recipient"] = df["vendor"].fillna("Unknown").str.strip()
    out["description"]      = df["description"].fillna("").str.strip()
    out["value"]            = pd.to_numeric(df["value"], errors="coerce").fillna(0)
    out["savings"]          = pd.to_numeric(df["savings"], errors="coerce").fillna(0)
    out["deleted_date"]     = pd.to_datetime(df["deleted_date"], errors="coerce")
    out["doge_flag"]        = 1
    out["piid"]             = df.get("piid", pd.Series(dtype=str))
    return out


def normalize_grants(df: pd.DataFrame) -> pd.DataFrame:
    """DOGE cancelled grants → unified schema."""
    if df.empty:
        return df
    out = pd.DataFrame()
    out["contract_id"]      = "DOGE_G_" + df.index.astype(str).str.zfill(6)
    out["item_type"]        = "grant"
    out["agency"]           = df["agency"].fillna("Unknown").str.strip()
    out["vendor_recipient"] = df["recipient"].fillna("Unknown").str.strip()
    out["description"]      = df["description"].fillna("").str.strip()
    out["value"]            = pd.to_numeric(df["value"], errors="coerce").fillna(0)
    out["savings"]          = pd.to_numeric(df["savings"], errors="coerce").fillna(0)
    out["deleted_date"]     = pd.to_datetime(df["date"], errors="coerce")
    out["doge_flag"]        = 1
    out["piid"]             = None
    return out


def normalize_leases(df: pd.DataFrame) -> pd.DataFrame:
    """DOGE cancelled leases → unified schema."""
    if df.empty:
        return df
    out = pd.DataFrame()
    out["contract_id"]      = "DOGE_L_" + df.index.astype(str).str.zfill(6)
    out["item_type"]        = "lease"
    out["agency"]           = df["agency"].fillna("Unknown").str.strip()
    out["vendor_recipient"] = df["location"].fillna("Unknown").str.strip()
    out["description"]      = df["description"].fillna("").str.strip()
    out["value"]            = pd.to_numeric(df["value"], errors="coerce").fillna(0)
    out["savings"]          = pd.to_numeric(df["savings"], errors="coerce").fillna(0)
    out["deleted_date"]     = pd.to_datetime(df["date"], errors="coerce")
    out["doge_flag"]        = 1
    out["piid"]             = None
    return out


def combine_items(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Stack contracts + grants + leases into one DataFrame."""
    frames = []
    for key, fn in [
        ("contracts", normalize_contracts),
        ("grants",    normalize_grants),
        ("leases",    normalize_leases),
    ]:
        if not dfs[key].empty:
            frames.append(fn(dfs[key]))

    if not frames:
        raise ValueError("No item data loaded — check raw files exist.")

    combined = pd.concat(frames, ignore_index=True)
    logger.info("Combined item corpus: %d rows", len(combined))
    return combined


# ===========================================================================
# Step 3 — Assign topic labels
# ===========================================================================

def assign_topic(agency: str, description: str) -> str:
    """Map an item to a topic category via agency name keywords."""
    text = f"{agency} {description}".lower()
    for keyword, topic in AGENCY_TO_TOPIC.items():
        if keyword in text:
            return topic
    return "general_spending"


def add_topics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["topic"] = df.apply(
        lambda r: assign_topic(r["agency"], r["description"]), axis=1
    )
    return df


# ===========================================================================
# Step 4 — DOGE scrutiny score
# ===========================================================================

def add_doge_scrutiny(df: pd.DataFrame) -> pd.DataFrame:
    """
    scrutiny_score = savings / value  (capped at 1)
    High score = DOGE claimed to save most of the contract's value.
    Items with value = 0 get score = 0.
    """
    df = df.copy()
    df["doge_scrutiny_score"] = (
        df["savings"] / df["value"].replace(0, float("nan"))
    ).clip(upper=1.0).fillna(0.0)
    return df


# ===========================================================================
# Step 5 — Join USASpending agency budget data
# ===========================================================================

def _normalize_agency_name(name: str) -> str:
    """Lowercase, strip common suffixes for fuzzy matching."""
    name = str(name).lower().strip()
    for suffix in ["department of ", "dept. of ", "dept of ", "u.s. ", "us "]:
        name = name.replace(suffix, "")
    return name


def join_usaspending_agencies(
    items: pd.DataFrame, agencies: pd.DataFrame
) -> pd.DataFrame:
    """
    Left-join agency budget figures onto the item corpus.
    Matching is done on normalized agency name (lowercase, suffix-stripped).
    Unmatched items get NaN for budget columns.
    """
    if agencies.empty:
        items["agency_obligated_amount"] = None
        items["agency_outlay_amount"]    = None
        return items

    agencies = agencies.copy()
    agencies["agency_key"] = agencies["agency_name"].apply(_normalize_agency_name)

    # Keep only the columns we need
    agency_lookup = agencies[[
        "agency_key", "obligated_amount", "outlay_amount"
    ]].rename(columns={
        "obligated_amount": "agency_obligated_amount",
        "outlay_amount":    "agency_outlay_amount",
    })

    items = items.copy()
    items["agency_key"] = items["agency"].apply(_normalize_agency_name)

    merged = items.merge(agency_lookup, on="agency_key", how="left")
    merged = merged.drop(columns=["agency_key"])

    matched = merged["agency_obligated_amount"].notna().sum()
    logger.info(
        "Agency join: %d/%d items matched to USASpending budget data",
        matched, len(merged),
    )
    return merged


# ===========================================================================
# Step 6 — Join GDELT popularity scores
# ===========================================================================

def compute_gdelt_scores(gdelt: pd.DataFrame, decay_rate: float = 0.01) -> dict:
    """
    Returns {topic: (normalised_score, article_count)} from GDELT articles.
    Reuses the same recency-weighted logic as gdelt_baseline.py.
    """
    if gdelt.empty:
        return {}

    df = gdelt.copy()

    # Always re-parse from raw seendate (CSV stores seendate_parsed as string)
    df["seendate_parsed"] = pd.to_datetime(
        df["seendate"], format="%Y%m%dT%H%M%SZ", utc=True, errors="coerce"
    )
    df = df.dropna(subset=["seendate_parsed"])

    # English only
    df = df[df["language"].str.lower() == "english"]

    # Map query → topic
    df["topic"] = df["query"].map(QUERY_TO_TOPIC).fillna(df["query"])

    now = datetime.now(tz=timezone.utc)
    df["hours_ago"] = (
        (now - df["seendate_parsed"]).dt.total_seconds() / 3600
    ).clip(lower=0)
    df["recency_weight"] = df["hours_ago"].apply(
        lambda h: math.exp(-decay_rate * h)
    )

    grouped = df.groupby("topic").agg(
        raw_score=("recency_weight", "sum"),
        article_count=("url", "count"),
    )

    max_score = grouped["raw_score"].max() or 1.0
    result = {
        topic: (row["raw_score"] / max_score, int(row["article_count"]))
        for topic, row in grouped.iterrows()
    }
    return result


def join_gdelt_scores(
    items: pd.DataFrame, gdelt: pd.DataFrame
) -> pd.DataFrame:
    """Add gdelt_popularity_score and gdelt_article_count columns."""
    scores = compute_gdelt_scores(gdelt)

    items = items.copy()
    items["gdelt_popularity_score"] = items["topic"].map(
        lambda t: scores.get(t, (0.0, 0))[0]
    )
    items["gdelt_article_count"] = items["topic"].map(
        lambda t: scores.get(t, (0.0, 0))[1]
    )

    logger.info(
        "GDELT scores joined. Topics with non-zero score: %d/%d unique topics",
        (items["gdelt_popularity_score"] > 0).sum(),
        items["topic"].nunique(),
    )
    return items


# ===========================================================================
# Step 7 — Transparency score
# ===========================================================================

def transparency_score(description: str) -> float:
    """
    Proxy for how clear/specific a contract description is.

    Score is based on:
      - Length (longer = more specific, up to a point)
      - Jargon word count (more jargon = less transparent)
      - Presence of numbers/dollar amounts (specific = good)

    Returns a value in [0, 1] where 1 = very transparent.
    """
    if not description or len(description.strip()) < 10:
        return 0.0

    text = description.lower()
    words = text.split()
    word_count = len(words)

    # Length score: peaks at ~50 words, diminishing returns beyond
    length_score = min(word_count / 50.0, 1.0)

    # Jargon penalty: each jargon word reduces score
    jargon_count = sum(1 for w in words if w in JARGON_WORDS)
    jargon_penalty = min(jargon_count / max(word_count, 1) * 5, 0.5)

    # Specificity bonus: numbers, dollar amounts, dates
    has_numbers = bool(re.search(r'\d+', description))
    specificity_bonus = 0.2 if has_numbers else 0.0

    score = length_score - jargon_penalty + specificity_bonus
    return round(max(0.0, min(score, 1.0)), 4)


def add_transparency(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["description_length"] = df["description"].str.len().fillna(0).astype(int)
    df["transparency_score"] = df["description"].apply(transparency_score)
    return df


# ===========================================================================
# Step 8 — Citizen impact score (composite)
# ===========================================================================

def add_citizen_impact_score(
    df: pd.DataFrame,
    w_gdelt: float = 0.30,
    w_scrutiny: float = 0.30,
    w_transparency: float = 0.20,
    w_value: float = 0.20,
) -> pd.DataFrame:
    """
    Composite citizen impact score: how much should a citizen care?

    Components (all normalized to [0,1]):
      gdelt_popularity_score   — how much news attention this topic is getting
      doge_scrutiny_score      — how aggressively DOGE cut this
      1 - transparency_score   — lower transparency = more citizen scrutiny needed
      normalized_value         — bigger contracts matter more

    Weights sum to 1.0 and are tunable — ablation study opportunity.
    """
    df = df.copy()

    # Normalize value to [0, 1] using log scale (dollar amounts span many orders)
    max_log_value = math.log1p(df["value"].max()) or 1.0
    df["normalized_value"] = df["value"].apply(
        lambda v: math.log1p(v) / max_log_value
    )

    df["citizen_impact_score"] = (
        w_gdelt         * df["gdelt_popularity_score"]
        + w_scrutiny    * df["doge_scrutiny_score"]
        + w_transparency * (1 - df["transparency_score"])
        + w_value       * df["normalized_value"]
    ).round(4)

    df = df.drop(columns=["normalized_value"])
    return df


# ===========================================================================
# Main pipeline
# ===========================================================================

def run_pipeline() -> pd.DataFrame:
    """Execute all steps and save unified_contracts.csv."""

    logger.info("=== Starting preprocessing pipeline ===")

    # 1. Load
    dfs = load_raw()

    # 2. Combine DOGE items
    items = combine_items(dfs)

    # 3. Topic labels
    items = add_topics(items)

    # 4. DOGE scrutiny score
    items = add_doge_scrutiny(items)

    # 5. Join USASpending agency budgets
    items = join_usaspending_agencies(items, dfs["agencies"])

    # 6. Join GDELT popularity scores
    items = join_gdelt_scores(items, dfs["gdelt"])

    # 7. Transparency score
    items = add_transparency(items)

    # 8. Citizen impact score
    items = add_citizen_impact_score(items)

    # 9. Final column ordering
    final_cols = [
        "contract_id", "item_type", "agency", "vendor_recipient",
        "description", "value", "savings", "deleted_date",
        "doge_flag", "doge_scrutiny_score",
        "agency_obligated_amount", "agency_outlay_amount",
        "gdelt_popularity_score", "gdelt_article_count",
        "topic", "description_length", "transparency_score",
        "citizen_impact_score",
    ]
    items = items[[c for c in final_cols if c in items.columns]]
    items = items.drop_duplicates(subset=["description", "agency", "value"])

    # 10. Save
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    items.to_csv(OUTPUT_PATH, index=False)
    logger.info("Saved %d unified items → %s", len(items), OUTPUT_PATH)

    return items


# ===========================================================================
# Quick summary stats
# ===========================================================================

def print_summary(df: pd.DataFrame) -> None:
    print(f"\n{'='*55}")
    print(f"  Unified contract dataset: {len(df):,} items")
    print(f"{'='*55}")
    print(f"\nItem types:\n{df['item_type'].value_counts().to_string()}")
    print(f"\nTop topics:\n{df['topic'].value_counts().head(8).to_string()}")
    print(f"\nTop agencies:\n{df['agency'].value_counts().head(6).to_string()}")
    print(f"\nGDELT coverage (non-zero score): "
          f"{(df['gdelt_popularity_score']>0).sum():,} / {len(df):,} items")
    print(f"\nScore distributions:")
    for col in ["doge_scrutiny_score", "gdelt_popularity_score",
                "transparency_score", "citizen_impact_score"]:
        if col in df.columns:
            print(f"  {col:30s}  "
                  f"mean={df[col].mean():.3f}  "
                  f"std={df[col].std():.3f}  "
                  f"max={df[col].max():.3f}")
    print(f"\nValue range: "
          f"${df['value'].min():,.0f} — ${df['value'].max():,.0f}")
    print(f"Savings range: "
          f"${df['savings'].min():,.0f} — ${df['savings'].max():,.0f}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    df = run_pipeline()
    print_summary(df)
