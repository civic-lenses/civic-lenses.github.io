# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""
Deep Learning Model: Hybrid Neural Ranker
==========================================
Two-stage recommender combining semantic retrieval with a trained
neural ranking network.

Stage 1 — Candidate Retrieval:
  Encode contract descriptions and user queries into dense 384-dim
  embeddings via a pretrained Sentence Transformer (all-MiniLM-L6-v2).
  Cosine similarity retrieves a pool of candidate contracts.

Stage 2 — Neural Ranking:
  A feedforward network ingests multiple signals per candidate
  (embedding similarity, topic match, DOGE scrutiny, transparency,
  GDELT popularity, citizen impact, contract value, description
  length) and outputs a learned relevance score.

Key difference from the classical TF-IDF model:
  The classical model combines signals with a fixed formula
  (alpha * relevance + (1-alpha) * impact).  This model *learns*
  the combination — and can discover non-linear interactions
  (e.g. high scrutiny + low transparency together may matter more
  than either alone).

Training data is synthetic: we simulate diverse user profiles
and derive relevance labels from topic alignment and contract
characteristics.
"""

from __future__ import annotations

import logging
import os
import random
import sys
from typing import Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger(__name__)

PROCESSED_PATH = os.path.join("data", "processed", "unified_contracts.csv")
MODELS_DIR = os.path.join("models")

# ---------------------------------------------------------------------------
# Topic -> seed keywords  (kept in sync with classical.py)
# ---------------------------------------------------------------------------
TOPIC_KEYWORDS: dict[str, str] = {
    "healthcare":             "healthcare health medical hospital patient clinical disease nursing",
    "education":              "education school training learning curriculum workforce student",
    "defense":                "defense military army navy air force security weapon combat",
    "infrastructure":         "infrastructure road bridge construction transportation highway",
    "foreign_aid":            "foreign aid international development overseas assistance usaid",
    "research":               "research science technology innovation laboratory grant study",
    "energy":                 "energy oil gas renewable solar wind nuclear power grid",
    "agriculture":            "agriculture farming food crop livestock rural nutrition",
    "finance":                "finance treasury tax revenue budget fiscal economic",
    "government_efficiency":  "government efficiency management reform administrative consulting",
    "general_spending":       "government federal spending program agency budget allocation",
    "doge_scrutiny":          "waste fraud abuse oversight transparency accountability doge",
}

ALL_TOPICS = list(TOPIC_KEYWORDS.keys())

# Feature columns consumed by the ranker network
RANKER_FEATURES = [
    "embedding_similarity",
    "topic_match",
    "doge_scrutiny_score",
    "transparency_score",
    "gdelt_popularity_score",
    "citizen_impact_score",
    "log_value",
    "norm_description_length",
]


# ===========================================================================
# Stage 2 — Neural Ranker Network
# ===========================================================================

class ContractRanker(nn.Module):
    """Small feedforward net that scores (user, contract) feature vectors."""

    def __init__(self, n_features: int = 8):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(n_features, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x).squeeze(-1)


# ===========================================================================
# Synthetic Training Data
# ===========================================================================

class SyntheticDataGenerator:
    """Create (user, contract) training pairs from simulated user profiles.

    For each synthetic user we:
      1. Pick 1-3 random topic preferences
      2. Encode those topics into a query embedding
      3. Compute cosine similarity with every contract
      4. Sample positives (topic match) and negatives
      5. Assign graded relevance labels
    """

    def __init__(
        self,
        contracts: pd.DataFrame,
        embeddings: np.ndarray,
        encoder: SentenceTransformer,
    ):
        self.contracts = contracts.reset_index(drop=True)
        self.embeddings = embeddings
        self.encoder = encoder

    def generate(
        self,
        n_users: int = 300,
        neg_ratio: float = 1.0,
        seed: int = 42,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return feature matrix X and label vector y.

        Args:
            n_users:   Number of synthetic user profiles.
            neg_ratio: Negative-to-positive sample ratio per user.
            seed:      Random seed for reproducibility.

        Returns:
            (X, y) — shapes (n_samples, 8) and (n_samples,).
        """
        rng = random.Random(seed)
        np_rng = np.random.RandomState(seed)

        # --- precompute contract-level arrays once ---
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        normed = self.embeddings / norms

        max_log_val = np.log1p(self.contracts["value"].max()) or 1.0
        log_vals = np.log1p(self.contracts["value"].values) / max_log_val

        max_dlen = self.contracts["description_length"].max() or 1
        norm_dlens = self.contracts["description_length"].values / max_dlen

        topics   = self.contracts["topic"].values
        scrutiny = self.contracts["doge_scrutiny_score"].fillna(0).values
        transp   = self.contracts["transparency_score"].fillna(0).values
        gdelt    = self.contracts["gdelt_popularity_score"].fillna(0).values
        impact   = self.contracts["citizen_impact_score"].fillna(0).values

        X_parts: list[np.ndarray] = []
        y_parts: list[np.ndarray] = []

        logger.info("Generating synthetic data for %d users...", n_users)

        for _ in range(n_users):
            n_topics = rng.randint(1, 3)
            user_topics = rng.sample(ALL_TOPICS, n_topics)

            # query embedding
            query_text = " ".join(TOPIC_KEYWORDS[t] for t in user_topics)
            q_emb = self.encoder.encode(query_text, normalize_embeddings=True)
            sims = normed @ q_emb                       # (n_contracts,)

            topic_match = np.array(
                [1.0 if t in user_topics else 0.0 for t in topics],
                dtype=np.float32,
            )

            # positive / negative indices
            pos_idx = np.where(topic_match == 1.0)[0]
            neg_idx = np.where(topic_match == 0.0)[0]
            n_neg = min(int(len(pos_idx) * neg_ratio), len(neg_idx))
            if n_neg > 0:
                neg_idx = np_rng.choice(neg_idx, size=n_neg, replace=False)
            idx = np.concatenate([pos_idx, neg_idx])

            # feature matrix
            feats = np.column_stack([
                sims[idx],
                topic_match[idx],
                scrutiny[idx],
                transp[idx],
                gdelt[idx],
                impact[idx],
                log_vals[idx],
                norm_dlens[idx],
            ])

            # graded labels — topic match dominates, structured signals add nuance
            labels = (
                0.50 * topic_match[idx]
                + 0.15 * np.clip(sims[idx], 0, 1)
                + 0.10 * scrutiny[idx]
                + 0.10 * (1.0 - transp[idx])
                + 0.10 * gdelt[idx]
                + 0.05 * log_vals[idx]
            )
            labels += np_rng.normal(0, 0.03, size=labels.shape)
            labels = np.clip(labels, 0.0, 1.0)

            X_parts.append(feats)
            y_parts.append(labels)

        X = np.vstack(X_parts).astype(np.float32)
        y = np.concatenate(y_parts).astype(np.float32)

        logger.info(
            "Generated %d samples  (%.0f%% positive)",
            len(y), 100 * (y > 0.5).mean(),
        )
        return X, y


# ===========================================================================
# Main Recommender
# ===========================================================================

class HybridNeuralRecommender:
    """Two-stage recommender: semantic retrieval -> learned neural ranking."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None,
        candidate_pool: int = 200,
    ):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.model_name = model_name
        self.candidate_pool = candidate_pool

        self.encoder = SentenceTransformer(model_name, device=device)
        self.ranker = ContractRanker(n_features=len(RANKER_FEATURES))
        self.ranker.to(device)
        self.scaler = StandardScaler()

        self._contracts: Optional[pd.DataFrame] = None
        self._embeddings: Optional[np.ndarray] = None
        self._fitted = False
        self._trained = False
        self.train_history: list[dict] = []

    # ------------------------------------------------------------------
    # fit — encode contracts + train ranker
    # ------------------------------------------------------------------

    def fit(
        self,
        contracts: pd.DataFrame,
        n_users: int = 300,
        epochs: int = 80,
        lr: float = 1e-3,
        batch_size: int = 256,
        val_split: float = 0.2,
        patience: int = 10,
        seed: int = 42,
    ) -> "HybridNeuralRecommender":
        """Encode all contracts and train the neural ranker.

        Args:
            contracts:  unified_contracts DataFrame.
            n_users:    Synthetic user count for training data.
            epochs:     Max training epochs.
            lr:         Learning rate for Adam.
            batch_size: Mini-batch size.
            val_split:  Fraction held out for validation.
            patience:   Early-stopping patience (epochs w/o improvement).
            seed:       Random seed.
        """
        self._contracts = contracts.copy().reset_index(drop=True)

        # --- Stage 1: encode descriptions ---
        logger.info(
            "Encoding %d descriptions with %s on %s...",
            len(contracts), self.model_name, self.device,
        )
        corpus = (
            self._contracts["description"].fillna("")
            + " " + self._contracts["agency"].fillna("")
        ).tolist()

        self._embeddings = self.encoder.encode(
            corpus,
            show_progress_bar=True,
            batch_size=64,
            normalize_embeddings=True,
        )
        self._fitted = True
        logger.info("Embeddings: %s", self._embeddings.shape)

        # --- Generate synthetic training data ---
        gen = SyntheticDataGenerator(
            self._contracts, self._embeddings, self.encoder,
        )
        X, y = gen.generate(n_users=n_users, seed=seed)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Train / val split
        torch.manual_seed(seed)
        n_val = int(len(X_scaled) * val_split)
        perm = torch.randperm(len(X_scaled))

        X_train = torch.tensor(X_scaled[perm[n_val:]], dtype=torch.float32, device=self.device)
        y_train = torch.tensor(y[perm[n_val:]],        dtype=torch.float32, device=self.device)
        X_val   = torch.tensor(X_scaled[perm[:n_val]],  dtype=torch.float32, device=self.device)
        y_val   = torch.tensor(y[perm[:n_val]],          dtype=torch.float32, device=self.device)

        logger.info("Train: %d  |  Val: %d", len(X_train), len(X_val))

        # --- Training loop ---
        optimizer = torch.optim.Adam(self.ranker.parameters(), lr=lr)
        criterion = nn.BCELoss()

        best_val_loss = float("inf")
        best_state = None
        stale = 0
        self.train_history = []

        self.ranker.train()
        for epoch in range(epochs):
            # shuffle
            idx = torch.randperm(len(X_train), device=self.device)
            X_train, y_train = X_train[idx], y_train[idx]

            epoch_loss = 0.0
            n_batches = 0
            for lo in range(0, len(X_train), batch_size):
                hi = min(lo + batch_size, len(X_train))
                optimizer.zero_grad()
                loss = criterion(self.ranker(X_train[lo:hi]), y_train[lo:hi])
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
                n_batches += 1

            train_loss = epoch_loss / n_batches

            self.ranker.eval()
            with torch.no_grad():
                val_loss = criterion(self.ranker(X_val), y_val).item()
            self.ranker.train()

            self.train_history.append({
                "epoch": epoch + 1,
                "train_loss": round(train_loss, 5),
                "val_loss": round(val_loss, 5),
            })

            if (epoch + 1) % 10 == 0 or epoch == 0:
                logger.info(
                    "Epoch %3d  train=%.4f  val=%.4f", epoch + 1, train_loss, val_loss,
                )

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_state = {k: v.clone() for k, v in self.ranker.state_dict().items()}
                stale = 0
            else:
                stale += 1
                if stale >= patience:
                    logger.info(
                        "Early stop at epoch %d  (best val=%.4f)", epoch + 1, best_val_loss,
                    )
                    break

        if best_state is not None:
            self.ranker.load_state_dict(best_state)
        self.ranker.eval()
        self._trained = True
        logger.info("Training complete — best val_loss=%.4f", best_val_loss)
        return self

    # ------------------------------------------------------------------
    # recommend
    # ------------------------------------------------------------------

    def recommend(
        self,
        user_topics: list[str],
        top_n: int = 10,
        pool_size: Optional[int] = None,
    ) -> pd.DataFrame:
        """Produce top-N recommendations for a set of user topic preferences.

        Args:
            user_topics: e.g. ["healthcare", "defense"]
            top_n:       How many results to return.
            pool_size:   Candidate count from retrieval stage.

        Returns:
            DataFrame with one row per recommendation, scored and annotated.
        """
        if not self._trained:
            raise RuntimeError("Call fit() before recommend()")

        pool = pool_size or self.candidate_pool

        # encode user query
        query_text = " ".join(TOPIC_KEYWORDS.get(t, t) for t in user_topics)
        q_emb = self.encoder.encode(query_text, normalize_embeddings=True)

        # Stage 1 — cosine retrieval
        sims = self._embeddings @ q_emb
        n_cands = min(pool, len(self._contracts))
        cand_idx = np.argsort(sims)[::-1][:n_cands]

        # build feature vectors for candidates
        df = self._contracts.iloc[cand_idx].copy()
        df["embedding_similarity"] = sims[cand_idx]
        df["topic_match"] = df["topic"].apply(lambda t: 1.0 if t in user_topics else 0.0)

        max_log_val = np.log1p(self._contracts["value"].max()) or 1.0
        df["log_value"] = np.log1p(df["value"].values) / max_log_val

        max_dlen = self._contracts["description_length"].max() or 1
        df["norm_description_length"] = df["description_length"].values / max_dlen

        for col in RANKER_FEATURES:
            df[col] = df[col].fillna(0)

        # Stage 2 — neural ranking
        feats = df[RANKER_FEATURES].values.astype(np.float32)
        feats_scaled = self.scaler.transform(feats)

        with torch.no_grad():
            scores = self.ranker(
                torch.tensor(feats_scaled, dtype=torch.float32, device=self.device)
            ).cpu().numpy()

        df["relevance_score"] = scores
        df["final_score"] = scores
        df = df.sort_values("final_score", ascending=False).head(top_n)

        # annotations
        df["matched_topics"] = df["topic"].apply(
            lambda t: [t] if t in user_topics else []
        )
        df["flags"] = df.apply(_flags, axis=1)
        df["reason"] = df.apply(lambda r: _reason(r, user_topics), axis=1)

        out_cols = [
            "contract_id", "item_type", "agency", "vendor_recipient",
            "description", "topic", "value", "savings",
            "relevance_score", "citizen_impact_score", "final_score",
            "embedding_similarity",
            "doge_scrutiny_score", "gdelt_popularity_score", "transparency_score",
            "matched_topics", "flags", "reason",
        ]
        return df[[c for c in out_cols if c in df.columns]].reset_index(drop=True)

    # ------------------------------------------------------------------
    # evaluate
    # ------------------------------------------------------------------

    def evaluate(
        self,
        results: pd.DataFrame,
        relevant_topics: list[str],
        k_values: Optional[list[int]] = None,
    ) -> dict:
        """Compute precision@k, topic coverage, and mean score.

        Args:
            results:         Output of recommend().
            relevant_topics: Ground-truth topics the user cares about.
            k_values:        List of k cutoffs (default [5, 10, 20]).

        Returns:
            Dict of metric_name -> value.
        """
        if k_values is None:
            k_values = [5, 10, 20]
        metrics: dict[str, float] = {}
        for k in k_values:
            top = results.head(k)
            hits = int(top["topic"].isin(relevant_topics).sum())
            precision = hits / k if k else 0
            covered = set(top["topic"]) & set(relevant_topics)
            coverage = len(covered) / len(relevant_topics) if relevant_topics else 0

            metrics[f"precision@{k}"] = round(precision, 4)
            metrics[f"topic_coverage@{k}"] = round(coverage, 4)
            metrics[f"hits@{k}"] = hits
            metrics[f"mean_score@{k}"] = round(float(top["final_score"].mean()), 4)
        return metrics

    # ------------------------------------------------------------------
    # save / load artifacts
    # ------------------------------------------------------------------

    def save_artifacts(self, path: Optional[str] = None) -> str:
        """Persist everything needed for inference without retraining.

        Saved files:
          embeddings.npy   — contract embedding matrix
          ranker.pt        — trained ranker weights
          scaler.npz       — StandardScaler mean + scale
          metadata.npz     — contract_ids and topics (for alignment check)
        """
        if not self._trained:
            raise RuntimeError("Train the model before saving")
        d = path or MODELS_DIR
        os.makedirs(d, exist_ok=True)

        np.save(os.path.join(d, "embeddings.npy"), self._embeddings)
        torch.save(self.ranker.state_dict(), os.path.join(d, "ranker.pt"))
        np.savez(
            os.path.join(d, "scaler.npz"),
            mean=self.scaler.mean_,
            scale=self.scaler.scale_,
        )
        np.savez(
            os.path.join(d, "metadata.npz"),
            contract_ids=self._contracts["contract_id"].values,
            topics=self._contracts["topic"].values,
        )
        logger.info("Artifacts saved -> %s", d)
        return d

    def load_artifacts(
        self,
        path: Optional[str] = None,
        contracts: Optional[pd.DataFrame] = None,
    ) -> "HybridNeuralRecommender":
        """Load previously saved artifacts for inference.

        Args:
            path:      Directory with saved files.
            contracts: The contracts DataFrame (needed for recommend()).
        """
        d = path or MODELS_DIR
        self._embeddings = np.load(os.path.join(d, "embeddings.npy"))
        self.ranker.load_state_dict(
            torch.load(os.path.join(d, "ranker.pt"), map_location=self.device, weights_only=True),
        )
        self.ranker.eval()

        sc = np.load(os.path.join(d, "scaler.npz"))
        self.scaler.mean_ = sc["mean"]
        self.scaler.scale_ = sc["scale"]
        self.scaler.n_features_in_ = len(sc["mean"])

        if contracts is not None:
            self._contracts = contracts.reset_index(drop=True)

        self._fitted = True
        self._trained = True
        logger.info("Artifacts loaded <- %s", d)
        return self


# ---------------------------------------------------------------------------
# Helpers (module-level to keep the class lean)
# ---------------------------------------------------------------------------

def _flags(row: pd.Series) -> list[str]:
    """Derive human-readable flag labels for a contract."""
    f: list[str] = []
    if row.get("doge_flag", 0) == 1:
        f.append("doge_flag")
    if row.get("transparency_score", 1) < 0.3:
        f.append("vague_description")
    if row.get("value", 0) > 1_000_000_000:
        f.append("high_value")
    if row.get("doge_scrutiny_score", 0) > 0.7:
        f.append("high_scrutiny")
    if row.get("gdelt_popularity_score", 0) > 0.2:
        f.append("trending")
    return f


def _reason(row: pd.Series, user_topics: list[str]) -> str:
    """Build a plain-English explanation for why a contract was recommended."""
    parts: list[str] = []
    if row.get("topic", "") in user_topics:
        parts.append(f"Matches your interest in {row['topic']}")
    sim = row.get("embedding_similarity", 0)
    if sim > 0.3:
        parts.append(f"Semantically relevant (sim {sim:.2f})")
    scr = row.get("doge_scrutiny_score", 0)
    if scr > 0.5:
        parts.append(f"High DOGE scrutiny ({scr:.0%} of value cut)")
    val = row.get("value", 0)
    if val > 1_000_000:
        parts.append(f"${val:,.0f} contract")
    return "; ".join(parts) if parts else "Ranked by neural model"


# ===========================================================================
# Smoke test
# ===========================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    # 1. Load data
    logger.info("Loading %s", PROCESSED_PATH)
    df = pd.read_csv(PROCESSED_PATH)
    logger.info("Loaded %d contracts", len(df))

    # 2. Fit (encode + train)
    model = HybridNeuralRecommender()
    model.fit(df, n_users=300, epochs=80, patience=10)

    # 3. Recommend
    topics = ["healthcare", "defense"]
    results = model.recommend(topics, top_n=10)

    print(f"\n{'='*70}")
    print(f"  Top 10 for {topics}")
    print(f"{'='*70}")
    for i, row in results.iterrows():
        print(f"\n  #{i+1}  [{row['topic']}]  {row['agency']}")
        desc = row["description"][:80] if isinstance(row["description"], str) else ""
        print(f"      {desc}...")
        print(f"      score={row['final_score']:.4f}  sim={row.get('embedding_similarity',0):.3f}")
        if row["flags"]:
            print(f"      flags: {', '.join(row['flags'])}")
        print(f"      -> {row['reason']}")

    # 4. Evaluate
    metrics = model.evaluate(results, relevant_topics=topics)
    print(f"\n{'='*70}")
    print("  Metrics")
    print(f"{'='*70}")
    for k, v in metrics.items():
        print(f"    {k:25s}  {v}")

    # 5. Save
    out = model.save_artifacts()
    print(f"\n  Saved to {out}/")

    # 6. Training curve summary
    hist = model.train_history
    print(f"\n  Training: {len(hist)} epochs")
    print(f"    start  train={hist[0]['train_loss']:.4f}  val={hist[0]['val_loss']:.4f}")
    print(f"    end    train={hist[-1]['train_loss']:.4f}  val={hist[-1]['val_loss']:.4f}")
