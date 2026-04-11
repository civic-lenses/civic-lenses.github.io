# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""
Naive Baseline: GDELT Popularity Recommender
=============================================
Recommends contracts based purely on which topic categories are
trending in the news right now — zero user personalization.

Logic:
  1. Parse raw GDELT articles (data/raw/gdelt_articles.csv)
  2. Filter to US/English sources for citizen relevance
  3. Compute a popularity score per query/topic:
       score = article_count (volume) weighted by recency
  4. Map GDELT queries → contract topic categories
  5. Rank contracts by their category's popularity score
  6. Return top-N — same ranked list for every user (no personalization)

This is the floor baseline. Every downstream model should beat it
by incorporating user location, topic preferences, and behaviour.
"""

from __future__ import annotations

import logging
import math
import os
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import RAW_DATA_DIR, PROCESSED_DATA_DIR, QUERY_TO_TOPIC

logger = logging.getLogger(__name__)

# NAICS prefix → topic category
# Used to map contract NAICS codes to the same topic labels.
NAICS_TO_TOPIC: dict[str, str] = {
    "11": "agriculture",
    "21": "energy",
    "23": "infrastructure",
    "31": "manufacturing",
    "32": "manufacturing",
    "33": "manufacturing",
    "42": "trade",
    "44": "trade",
    "45": "trade",
    "48": "infrastructure",
    "49": "infrastructure",
    "51": "technology",
    "52": "finance",
    "53": "general_spending",
    "54": "research",
    "55": "government_efficiency",
    "56": "government_efficiency",
    "61": "education",
    "62": "healthcare",
    "71": "general_spending",
    "72": "general_spending",
    "81": "general_spending",
    "92": "federal_contracts",
}


# ---------------------------------------------------------------------------
# 2. GDELT popularity scorer
# ---------------------------------------------------------------------------

class GDELTPopularityScorer:
    """
    Computes a recency-weighted popularity score for each topic category
    using raw GDELT article data.

    Score formula per topic:
        raw_score = Σ recency_weight(article_i)
        where recency_weight = exp(-decay * hours_since_published)

    This means articles from the last few hours score highest,
    articles from yesterday score lower, week-old articles near zero.
    Normalised to [0, 1] across all topics.
    """

    def __init__(
        self,
        gdelt_path: str,
        decay_rate: float = 0.01,          # hourly decay — tune this
        min_us_fraction: float = 0.0,      # set >0 to require US source mix
        english_only: bool = True,
    ) -> None:
        self.gdelt_path = gdelt_path
        self.decay_rate = decay_rate
        self.min_us_fraction = min_us_fraction
        self.english_only = english_only
        self._scores: dict[str, float] = {}  # topic → normalised score
        self._article_counts: dict[str, int] = {}  # topic → raw count

    # ------------------------------------------------------------------
    def fit(self) -> "GDELTPopularityScorer":
        """Load GDELT CSV and compute topic popularity scores."""
        df = self._load()
        df = self._clean(df)
        self._scores, self._article_counts = self._score(df)
        logger.info(
            "GDELTPopularityScorer fitted on %d articles across %d topics",
            len(df), len(self._scores),
        )
        return self

    # ------------------------------------------------------------------
    def topic_scores(self) -> pd.DataFrame:
        """Return a tidy DataFrame of topic → score, sorted descending."""
        if not self._scores:
            raise RuntimeError("Call .fit() before .topic_scores()")
        rows = [
            {
                "topic":         topic,
                "popularity_score": score,
                "article_count": self._article_counts.get(topic, 0),
            }
            for topic, score in sorted(
                self._scores.items(), key=lambda x: x[1], reverse=True
            )
        ]
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    def score_contracts(self, contracts: pd.DataFrame) -> pd.DataFrame:
        """
        Add a `popularity_score` column to a contracts DataFrame.

        Expects contracts to have at least one of:
          - `naics_code`  (str/int, first 2 digits used)
          - `topic`       (str, already mapped to our topic labels)

        Contracts whose topic cannot be resolved get score = 0.
        Returns contracts sorted by popularity_score descending.
        """
        if not self._scores:
            raise RuntimeError("Call .fit() before .score_contracts()")

        df = contracts.copy()
        df["topic"] = df.apply(self._resolve_topic, axis=1)
        df["popularity_score"] = df["topic"].map(self._scores).fillna(0.0)
        df["article_count"] = df["topic"].map(self._article_counts).fillna(0)
        return df.sort_values("popularity_score", ascending=False).reset_index(drop=True)

    # ------------------------------------------------------------------
    def recommend(
        self,
        contracts: pd.DataFrame,
        top_n: int = 10,
        topic_filter: str | None = None,
    ) -> pd.DataFrame:
        """
        Return the top-N most popular contracts.

        Args:
            contracts:    DataFrame of contracts (needs naics_code or topic)
            top_n:        Number of contracts to return
            topic_filter: Optional — restrict to a single topic category
                          (e.g. 'healthcare'). Mimics the most basic
                          user preference without any learned model.
        """
        scored = self.score_contracts(contracts)
        if topic_filter:
            scored = scored[scored["topic"] == topic_filter]
        return scored.head(top_n)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> pd.DataFrame:
        if not os.path.exists(self.gdelt_path):
            raise FileNotFoundError(f"GDELT file not found: {self.gdelt_path}")
        df = pd.read_csv(self.gdelt_path)
        logger.info("Loaded %d GDELT articles from %s", len(df), self.gdelt_path)
        return df

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Parse dates, optionally filter to English / US sources."""
        # Parse seendate: '20260410T151500Z' → datetime
        df = df.copy()
        df["parsed_date"] = pd.to_datetime(
            df["seendate"], format="%Y%m%dT%H%M%SZ", utc=True, errors="coerce"
        )
        df = df.dropna(subset=["parsed_date"])

        # Map query → topic
        df["topic"] = df["query"].map(QUERY_TO_TOPIC).fillna(df["query"])

        # Optional: English only
        if self.english_only:
            before = len(df)
            df = df[df["language"].str.lower() == "english"]
            logger.info(
                "English filter: %d → %d articles", before, len(df)
            )

        # Optional: require a minimum fraction from US sources
        if self.min_us_fraction > 0:
            us_mask = df["sourcecountry"].str.lower() == "united states"
            us_frac = us_mask.mean()
            if us_frac < self.min_us_fraction:
                logger.warning(
                    "US source fraction %.2f below threshold %.2f — "
                    "keeping all sources", us_frac, self.min_us_fraction
                )
            else:
                df = df[us_mask]

        return df

    def _score(
        self, df: pd.DataFrame
    ) -> tuple[dict[str, float], dict[str, int]]:
        """
        Compute recency-weighted article counts per topic.
        Returns (normalised_scores, raw_counts).
        """
        now = datetime.now(tz=timezone.utc)

        # Hours since publication → recency weight
        df = df.copy()
        df["hours_ago"] = (
            (now - df["parsed_date"]).dt.total_seconds() / 3600
        ).clip(lower=0)
        df["recency_weight"] = (-self.decay_rate * df["hours_ago"]).apply(
            lambda x: math.exp(x)
        )

        # Aggregate per topic
        grouped = df.groupby("topic").agg(
            raw_score=("recency_weight", "sum"),
            article_count=("url", "count"),
        )

        raw_scores = grouped["raw_score"].to_dict()
        article_counts = grouped["article_count"].to_dict()

        # Normalise to [0, 1]
        max_score = max(raw_scores.values()) if raw_scores else 1.0
        normalised = {
            topic: score / max_score
            for topic, score in raw_scores.items()
        }

        return normalised, article_counts

    def _resolve_topic(self, row: pd.Series) -> str:
        """Map a contract row to a topic label via NAICS or existing topic."""
        # If contract already has a topic column
        if "topic" in row and pd.notna(row["topic"]):
            return str(row["topic"])

        # Derive from NAICS code
        if "naics_code" in row and pd.notna(row["naics_code"]):
            prefix = str(row["naics_code"])[:2]
            return NAICS_TO_TOPIC.get(prefix, "general_spending")

        return "general_spending"


# ---------------------------------------------------------------------------
# 3. Evaluation helpers
# ---------------------------------------------------------------------------

def evaluate_baseline(
    recommended: pd.DataFrame,
    relevant_topics: list[str],
) -> dict[str, float]:
    """
    Lightweight evaluation for the naive baseline.

    Metrics:
        precision@k  — fraction of top-k that match a relevant topic
        topic_coverage — fraction of relevant topics represented in top-k

    Args:
        recommended:     Output of .recommend() — must have 'topic' column
        relevant_topics: Ground-truth topics the user cares about
    """
    if recommended.empty or not relevant_topics:
        return {"precision_at_k": 0.0, "topic_coverage": 0.0}

    k = len(recommended)
    hits = recommended["topic"].isin(relevant_topics).sum()
    precision = hits / k

    covered = set(recommended["topic"]) & set(relevant_topics)
    coverage = len(covered) / len(relevant_topics)

    return {
        "precision_at_k": round(precision, 4),
        "topic_coverage": round(coverage, 4),
        "k": k,
        "hits": int(hits),
    }


# ---------------------------------------------------------------------------
# 4. Quick demo / smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    GDELT_PATH     = os.path.join(RAW_DATA_DIR, "gdelt_articles.csv")
    CONTRACTS_PATH = os.path.join(PROCESSED_DATA_DIR, "unified_contracts.csv")

    # --- Fit scorer on real GDELT data ---
    scorer = GDELTPopularityScorer(
        gdelt_path=GDELT_PATH,
        decay_rate=0.01,
        english_only=True,
    )
    scorer.fit()

    # --- Topic popularity scores ---
    print("\n=== Topic Popularity Scores (GDELT, 30-day window) ===")
    print(scorer.topic_scores().to_string(index=False))

    # --- Load real unified contracts ---
    contracts = pd.read_csv(CONTRACTS_PATH)
    print(f"\nLoaded {len(contracts):,} contracts from unified_contracts.csv")

    # --- Top 10 overall (same list for every user) ---
    top10 = scorer.recommend(contracts, top_n=10)
    print("\n=== Top 10 Contracts — No Personalization (everyone sees this) ===")
    print(top10[[
        "contract_id", "item_type", "agency",
        "topic", "popularity_score", "value", "savings"
    ]].to_string(index=False))

    # --- Per-topic top 3 ---
    for topic in ["healthcare", "foreign_aid", "defense", "education"]:
        results = scorer.recommend(contracts, top_n=3, topic_filter=topic)
        print(f"\n=== Top 3 [{topic}] ===")
        if results.empty:
            print("  No contracts found for this topic.")
        else:
            print(results[[
                "contract_id", "agency", "description",
                "popularity_score", "value"
            ]].to_string(index=False))

    # --- Evaluation across simulated user personas ---
    print("\n=== Baseline Evaluation Across User Personas ===")
    personas = [
        {"name": "Healthcare citizen",  "topics": ["healthcare", "research"]},
        {"name": "Defense watcher",     "topics": ["defense", "government_efficiency"]},
        {"name": "Foreign aid critic",  "topics": ["foreign_aid", "general_spending"]},
        {"name": "Education advocate",  "topics": ["education", "general_spending"]},
        {"name": "General citizen",     "topics": ["general_spending", "government_efficiency"]},
    ]
    top20 = scorer.recommend(contracts, top_n=20)
    rows = []
    for p in personas:
        m = evaluate_baseline(top20, relevant_topics=p["topics"])
        rows.append({"persona": p["name"], **m})
    print(pd.DataFrame(rows).to_string(index=False))

    # --- Summary stats ---
    topic_scores_df = scorer.topic_scores()
    covered = topic_scores_df[topic_scores_df["popularity_score"] > 0].shape[0]
    total_topics = contracts["topic"].nunique()
    print("\n=== Baseline Summary ===")
    print(f"Total items in corpus:        {len(contracts):,}")
    print(f"Topics covered by GDELT:      {covered}")
    print(f"Topics with zero score:       {total_topics - covered} / {total_topics} unique topics")
    print(f"Items with non-zero score:    {(contracts['topic'].isin(topic_scores_df[topic_scores_df['popularity_score']>0]['topic'])).sum():,}")
    print("\nKey limitation: all contracts in the same topic share identical scores.")
    print("The classical ML model fixes this by scoring each contract individually.")
