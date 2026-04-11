# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""
Classical ML Model: TF-IDF + Cosine Similarity Recommender
===========================================================
Recommends contracts by matching a citizen's topic preferences
against contract descriptions using TF-IDF vectorization and
cosine similarity.

Improvement over naive baseline:
  - Scores each contract INDIVIDUALLY based on its text
  - Two contracts in the same topic get different scores
  - Produces interpretable matched terms for reason snippets
  - Re-ranks using citizen_impact_score as a secondary signal

Output schema per recommendation:
  contract_id, item_type, agency, description, topic,
  relevance_score, citizen_impact_score, final_score,
  matched_topics, flags, reason, value, savings
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)

PROCESSED_PATH = os.path.join(PROCESSED_DATA_DIR, "unified_contracts.csv")

# ---------------------------------------------------------------------------
# Topic → seed keywords
# Used to build the user query string from topic selections
# ---------------------------------------------------------------------------
# Seed keywords for building TF-IDF user queries from topic selections.
# Each entry should contain terms likely to appear in federal contract
# descriptions or agency names from SAM.gov, DOGE.gov, and USAspending.
# Expanded per PR #1 review to reduce coverage gaps.
TOPIC_KEYWORDS: dict[str, str] = {
    "healthcare":             "healthcare health medical hospital patient clinical disease nursing medicaid medicare veterans",
    "education":              "education school training learning curriculum workforce student university college",
    "defense":                "defense military army navy air force security weapon combat veteran",
    "infrastructure":         "infrastructure road bridge construction transportation highway transit water broadband",
    "foreign_aid":            "foreign aid international development overseas assistance humanitarian",
    "research":               "research science technology innovation laboratory grant study clinical trial",
    "energy":                 "energy oil gas renewable solar wind nuclear power grid pipeline",
    "agriculture":            "agriculture farming food crop livestock rural nutrition subsidy",
    "finance":                "finance treasury tax revenue budget fiscal economic debt",
    "government_efficiency":  "efficiency management consulting administrative reform modernization audit",
    "general_spending":       "government federal spending contract services program support procurement",
    "doge_scrutiny":          "doge department government efficiency waste fraud abuse oversight accountability transparency elimination reduction",
}

# ---------------------------------------------------------------------------
# Flag thresholds — set by calibrate_flags() from actual data distributions.
# Must be calibrated before flags are evaluated.
# ---------------------------------------------------------------------------
_flag_thresholds: dict[str, float] = {}


def calibrate_flags(df: pd.DataFrame) -> None:
    """Set flag thresholds from data percentiles. Must be called before recommend()."""
    _flag_thresholds["vague_cutoff"] = float(df["transparency_score"].quantile(0.25))
    _flag_thresholds["high_value_cutoff"] = float(df["value"].quantile(0.95))
    _flag_thresholds["high_scrutiny_cutoff"] = float(df["doge_scrutiny_score"].quantile(0.90))
    _flag_thresholds["trending_cutoff"] = float(df["gdelt_popularity_score"].quantile(0.75))
    logger.info("Calibrated flag thresholds: %s", _flag_thresholds)


FLAG_THRESHOLDS = {
    "doge_flag":          lambda r: r.get("doge_flag", 0) == 1,
    "vague_description":  lambda r: r.get("transparency_score", 1) < _flag_thresholds["vague_cutoff"],
    "high_value":         lambda r: r.get("value", 0) > _flag_thresholds["high_value_cutoff"],
    "high_scrutiny":      lambda r: r.get("doge_flag", 0) == 1 and r.get("doge_scrutiny_score", 0) > _flag_thresholds["high_scrutiny_cutoff"],
    "trending":           lambda r: r.get("gdelt_popularity_score", 0) > _flag_thresholds["trending_cutoff"],
}


# ===========================================================================
# TF-IDF Recommender
# ===========================================================================

class TFIDFRecommender:
    """
    Content-based recommender using TF-IDF + cosine similarity.

    Usage:
        model = TFIDFRecommender()
        model.fit(contracts_df)
        results = model.recommend(
            user_topics=["healthcare", "education"],
            top_n=10,
            alpha=0.7   # weight for relevance vs citizen_impact
        )
    """

    def __init__(
        self,
        min_df: int = 2,
        max_df: float = 0.95,
        ngram_range: tuple = (1, 2),
        max_features: int = 15_000,
    ) -> None:
        self.vectorizer = TfidfVectorizer(
            min_df=min_df,
            max_df=max_df,
            ngram_range=ngram_range,
            max_features=max_features,
            stop_words="english",
            strip_accents="unicode",
            lowercase=True,
        )
        self._contracts: Optional[pd.DataFrame] = None
        self._tfidf_matrix = None   # shape: (n_contracts, n_features)
        self._feature_names: list[str] = []
        self._fitted = False

    # ------------------------------------------------------------------
    def fit(self, contracts: pd.DataFrame) -> "TFIDFRecommender":
        """
        Fit the TF-IDF vectorizer on the contract corpus.

        Args:
            contracts: unified_contracts DataFrame — needs 'description' column
        """
        self._contracts = contracts.copy().reset_index(drop=True)

        calibrate_flags(self._contracts)

        # Build text corpus — combine description + agency for richer signal
        corpus = (
            self._contracts["description"].fillna("") + " "
            + self._contracts["agency"].fillna("") + " "
            + self._contracts["topic"].fillna("")
        ).tolist()

        self._tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self._feature_names = self.vectorizer.get_feature_names_out().tolist()
        self._fitted = True

        logger.info(
            "TF-IDF fitted: %d contracts × %d features",
            self._tfidf_matrix.shape[0],
            self._tfidf_matrix.shape[1],
        )
        return self

    # ------------------------------------------------------------------
    def recommend(
        self,
        user_topics: list[str],
        top_n: int = 10,
        alpha: float = 0.7,
        item_type_filter: Optional[str] = None,
        min_relevance: float = 0.01,
    ) -> pd.DataFrame:
        """
        Recommend top-N contracts for a user's topic preferences.

        Args:
            user_topics:       List of topic strings from user onboarding
                               e.g. ["healthcare", "education", "defense"]
            top_n:             Number of contracts to return
            alpha:             Weight for relevance_score vs citizen_impact_score
                               final_score = alpha*relevance + (1-alpha)*impact
                               0.7 = relevance-heavy (good default)
            item_type_filter:  Optional — restrict to 'contract','grant','lease'
            min_relevance:     Minimum cosine similarity to include in results

        Returns:
            DataFrame with recommendation output schema
        """
        if not self._fitted:
            raise RuntimeError("Call .fit() before .recommend()")

        # Build user query from topic keywords
        user_query = self._build_user_query(user_topics)
        logger.info("User query built from topics %s", user_topics)

        # Vectorize the user query using the fitted vocabulary
        query_vector = self.vectorizer.transform([user_query])

        # Cosine similarity: query vs all contracts
        similarities = cosine_similarity(query_vector, self._tfidf_matrix).flatten()

        # Build results DataFrame
        results = self._contracts.copy()
        results["relevance_score"] = similarities.round(4)

        # Filter by minimum relevance
        results = results[results["relevance_score"] >= min_relevance].copy()

        # Optional item type filter
        if item_type_filter:
            results = results[results["item_type"] == item_type_filter]

        if results.empty:
            logger.warning("No contracts above min_relevance=%.3f", min_relevance)
            return pd.DataFrame()

        # Final score: weighted combination of relevance + citizen impact
        results["final_score"] = (
            alpha * results["relevance_score"]
            + (1 - alpha) * results["citizen_impact_score"]
        ).round(4)

        # Sort by final_score
        results = results.sort_values("final_score", ascending=False).head(top_n)

        # Add interpretability columns
        results["matched_topics"] = results.apply(
            lambda r: self._matched_topics(r, user_topics), axis=1
        )
        results["flags"] = results.apply(_compute_flags, axis=1)
        results["reason"] = results.apply(
            lambda r: self._build_reason(r, user_topics), axis=1
        )

        # Return clean output schema
        output_cols = [
            "contract_id", "item_type", "agency", "vendor_recipient",
            "description", "topic", "value", "savings",
            "relevance_score", "citizen_impact_score", "final_score",
            "doge_scrutiny_score", "gdelt_popularity_score", "transparency_score",
            "matched_topics", "flags", "reason",
        ]
        return results[[c for c in output_cols if c in results.columns]].reset_index(drop=True)

    # ------------------------------------------------------------------
    def get_top_terms(self, contract_idx: int, top_k: int = 5) -> list[str]:
        """Return the top TF-IDF terms for a specific contract by index."""
        if not self._fitted:
            raise RuntimeError("Call .fit() first")
        row = self._tfidf_matrix[contract_idx]
        scores = zip(self._feature_names, row.toarray().flatten())
        return [term for term, score in sorted(scores, key=lambda x: x[1], reverse=True)
                if score > 0][:top_k]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_user_query(self, user_topics: list[str]) -> str:
        """Expand user topic selections into a keyword query string."""
        parts = []
        for topic in user_topics:
            keywords = TOPIC_KEYWORDS.get(topic.lower(), topic)
            parts.append(keywords)
        return " ".join(parts)

    def _matched_topics(self, row: pd.Series, user_topics: list[str]) -> list[str]:
        """Return which user topics matched this contract."""
        matched = []
        desc_text = f"{row.get('description','')} {row.get('agency','')}".lower()
        for topic in user_topics:
            keywords = TOPIC_KEYWORDS.get(topic.lower(), topic).split()
            if any(kw in desc_text for kw in keywords[:3]):  # top 3 seed words
                matched.append(topic)
        return matched if matched else [row.get("topic", "general")]

    def _build_reason(self, row: pd.Series, user_topics: list[str]) -> str:
        """Build a plain-English reason snippet for the card UI."""
        parts = []

        # Topic match
        matched = self._matched_topics(row, user_topics)
        if matched:
            parts.append(f"Matches your {', '.join(matched)} interest(s)")

        # DOGE flag
        if row.get("doge_flag", 0) == 1:
            savings = row.get("savings", 0)
            if savings > 0:
                parts.append(f"DOGE terminated — ${savings:,.0f} claimed savings")
            else:
                parts.append("DOGE flagged for termination")

        # Transparency — tiered wording based on severity
        t_score = row.get("transparency_score", 1)
        if t_score == 0.0:
            parts.append("No description on record")
        elif t_score < 0.15:
            parts.append("Extremely vague — no measurable deliverables")
        elif t_score < 0.3:
            parts.append("Description lacks specificity")
        elif t_score > 0.7:
            parts.append("Description is detailed and specific")

        # GDELT signal
        articles = int(row.get("gdelt_article_count", 0))
        if articles > 0:
            parts.append(f"{articles} news articles in last 30 days")

        # Value signal
        value = row.get("value", 0)
        if value > 1_000_000_000:
            parts.append(f"Large contract: ${value/1e9:.1f}B")

        return ". ".join(parts) + "." if parts else "No specific signals flagged."


# ===========================================================================
# Flag computation
# ===========================================================================

def _compute_flags(row: pd.Series) -> list[str]:
    """Compute flag list for a contract row."""
    return [
        flag_name
        for flag_name, condition in FLAG_THRESHOLDS.items()
        if condition(dict(row))
    ]


# ===========================================================================
# Evaluation
# ===========================================================================

def evaluate(
    results: pd.DataFrame,
    relevant_topics: list[str],
    k_values: list[int] | None = None,
) -> pd.DataFrame:
    """
    Evaluate recommendation quality at multiple k values.

    Metrics:
        precision@k     — fraction of top-k matching a relevant topic
        topic_coverage  — fraction of relevant topics in top-k
        mean_relevance  — average cosine similarity score
        mean_final      — average final_score
    """
    if k_values is None:
        k_values = [5, 10, 20]
    rows = []
    for k in k_values:
        top_k = results.head(k)
        if top_k.empty:
            continue
        hits = top_k["topic"].isin(relevant_topics).sum()
        covered = set(top_k["topic"]) & set(relevant_topics)
        rows.append({
            "k":               k,
            "precision_at_k":  round(hits / k, 4),
            "topic_coverage":  round(len(covered) / max(len(relevant_topics), 1), 4),
            "hits":            int(hits),
            "mean_relevance":  round(top_k["relevance_score"].mean(), 4),
            "mean_final_score":round(top_k["final_score"].mean(), 4),
        })
    return pd.DataFrame(rows)


def compare_with_baseline(
    tfidf_results: pd.DataFrame,
    baseline_results: pd.DataFrame,
    relevant_topics: list[str],
    k: int = 10,
) -> pd.DataFrame:
    """
    Side-by-side comparison of TF-IDF vs naive baseline at k.
    Returns a summary DataFrame for the write-up table.
    """
    rows = []
    for name, results in [("Naive baseline", baseline_results),
                           ("TF-IDF + cosine", tfidf_results)]:
        top_k = results.head(k)
        hits = top_k["topic"].isin(relevant_topics).sum() if not top_k.empty else 0
        covered = set(top_k.get("topic", [])) & set(relevant_topics)
        rows.append({
            "model":           name,
            "precision_at_k":  round(hits / k, 4) if k else 0,
            "topic_coverage":  round(len(covered) / max(len(relevant_topics), 1), 4),
            "unique_agencies": top_k["agency"].nunique() if not top_k.empty else 0,
            "mean_value_$M":   round(top_k["value"].mean() / 1e6, 1) if not top_k.empty else 0,
        })
    return pd.DataFrame(rows)


# ===========================================================================
# Main — demo on real data
# ===========================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    # --- Load unified contracts ---
    contracts = pd.read_csv(PROCESSED_PATH)
    logger.info("Loaded %d contracts", len(contracts))

    # --- Fit model ---
    model = TFIDFRecommender(ngram_range=(1, 2), max_features=15_000)
    model.fit(contracts)

    # --- Simulate three citizen personas from the app design ---
    personas = [
        {
            "name":   "NC Healthcare + Education citizen",
            "topics": ["healthcare", "education", "defense"],
        },
        {
            "name":   "Foreign aid critic",
            "topics": ["foreign_aid", "government_efficiency"],
        },
        {
            "name":   "General citizen",
            "topics": ["general_spending", "government_efficiency"],
        },
    ]

    all_eval_rows = []

    for persona in personas:
        print(f"\n{'='*60}")
        print(f"  Persona: {persona['name']}")
        print(f"  Topics:  {persona['topics']}")
        print(f"{'='*60}")

        results = model.recommend(
            user_topics=persona["topics"],
            top_n=10,
            alpha=0.7,
        )

        if results.empty:
            print("  No results returned.")
            continue

        # Show top 5 cards
        print(f"\nTop 5 recommendations:")
        for i, row in results.head(5).iterrows():
            print(f"\n  [{i+1}] {row['agency']}")
            desc = str(row['description'])[:100] + "..." if len(str(row['description'])) > 100 else str(row['description'])
            print(f"      {desc}")
            print(f"      Value: ${row['value']:,.0f}  |  Final score: {row['final_score']:.4f}")
            print(f"      Flags: {row['flags']}")
            print(f"      Reason: {row['reason'][:120]}...")

        # Evaluate
        eval_df = evaluate(results, relevant_topics=persona["topics"])
        print(f"\nEvaluation:")
        print(eval_df.to_string(index=False))

        for _, erow in eval_df.iterrows():
            all_eval_rows.append({"persona": persona["name"], **erow})

    # --- Overall comparison table ---
    print(f"\n{'='*60}")
    print("  Full Evaluation Summary")
    print(f"{'='*60}")
    print(pd.DataFrame(all_eval_rows).to_string(index=False))

    # --- Alpha sensitivity: how much does re-ranking matter? ---
    print(f"\n{'='*60}")
    print("  Alpha Sensitivity (relevance weight vs citizen impact weight)")
    print(f"{'='*60}")
    test_topics = ["healthcare", "education", "defense"]
    alpha_rows = []
    for alpha in [1.0, 0.7, 0.5, 0.3, 0.0]:
        res = model.recommend(test_topics, top_n=10, alpha=alpha)
        if res.empty:
            continue
        hits = res["topic"].isin(test_topics).sum()
        alpha_rows.append({
            "alpha": alpha,
            "label": f"{'relevance only' if alpha==1.0 else 'impact only' if alpha==0.0 else f'{int(alpha*100)}% relevance'}",
            "precision_at_10": round(hits / 10, 3),
            "mean_final_score": round(res["final_score"].mean(), 4),
            "mean_citizen_impact": round(res["citizen_impact_score"].mean(), 4),
        })
    print(pd.DataFrame(alpha_rows).to_string(index=False))
    print("\nNote: alpha=0.7 is the recommended default.")
    print("This sensitivity analysis can serve as your focused experiment.")
