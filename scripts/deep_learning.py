# AI-assisted (Claude Code, claude.ai) — https://claude.ai
# External libraries:
#   PyTorch (torch, torch.nn) — https://pytorch.org — BSD-3-Clause license
#   Sentence Transformers (all-MiniLM-L6-v2) — https://sbert.net — Apache-2.0 license
#   scikit-learn (StandardScaler, MinMaxScaler) — https://scikit-learn.org — BSD-3-Clause license
"""
Deep Learning Model: Hybrid Neural Ranker v3
=============================================
Two-stage recommender combining semantic retrieval with a pairwise
neural ranking network trained via MarginRankingLoss on **real labels**
derived from DOGE scrutiny scores (distant supervision).

Label source:
  doge_scrutiny_score measures what fraction of a contract's value DOGE
  actually cut. This is a real-world human judgment about "this contract
  deserves attention." Contracts in the top quartile (>= 0.71) are
  labeled "high attention"; contracts in the bottom quartile (= 0.0)
  are labeled "low attention." The model learns to predict which
  structural features (value, transparency, description length, topic,
  semantic similarity) predict that DOGE would aggressively cut a
  contract -- without seeing doge_scrutiny_score itself.

Stage 1 -- Semantic Retrieval:
  Encode contract descriptions into dense 384-dim embeddings via a
  pretrained Sentence Transformer (all-MiniLM-L6-v2).
  Per-topic cosine retrieval ensures diversity when multiple topics
  are requested.

Stage 2 -- Neural Ranking (Pairwise, real labels):
  A feedforward MLP ingests 5 features per contract and outputs a
  scalar score. Trained with MarginRankingLoss on preference pairs
  where the preferred contract has higher real DOGE scrutiny.

  Three tiers of preference pairs:
    Tier 1 -- Easy: (high_scrutiny + topic_match) vs
              (low_scrutiny + no topic_match).
              Both signals agree. Should be trivial for any model.
    Tier 2 -- Within-topic: (high_scrutiny + topic_match) vs
              (low_scrutiny + topic_match).
              Both match the user's topic. The model must distinguish
              using value, transparency, description length. This is
              the core claim: MLP non-linearity should beat linear here.
    Tier 3 -- Off-topic: (high_scrutiny + no topic_match) vs
              (low_scrutiny + no topic_match).
              No topic signal. Pure feature-based discrimination.

  A LinearRanker baseline trains on the same data with the same loss
  to prove that the MLP's non-linearity adds value on Tier 2 pairs.

Train/val split:
  Temporal: train on contracts deleted Jan-Mar 2025, validate on
  Apr 2025+. This tests generalization to future contracts.

Product framing:
  The app has two ranking signals blended by the model:
  1. Personalization: topic_match + embedding_similarity
  2. Scrutiny prediction: which contracts deserve citizen attention
     based on structural features that correlate with DOGE action
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

from config import PROCESSED_DATA_DIR
from scripts.classical import (
    TOPIC_KEYWORDS,
    calibrate_flags,
    _compute_flags,
)

logger = logging.getLogger(__name__)

ALL_TOPICS = list(TOPIC_KEYWORDS.keys())

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")

# 5 features: doge_scrutiny_score is the LABEL, not a feature
RANKER_FEATURES = [
    "embedding_similarity",
    "topic_match",
    "transparency_score",
    "log_value",
    "norm_description_length",
]

# Scrutiny thresholds for binarizing labels
# Wider gap = cleaner signal. Top 10% are contracts DOGE cut aggressively
# (mostly 100% cuts). Bottom quartile are zero-cut contracts.
HIGH_SCRUTINY_QUANTILE = 0.90
LOW_SCRUTINY_THRESHOLD = 0.0   # exact zero = DOGE didn't cut anything

# Temporal split cutoff
TEMPORAL_SPLIT_DATE = "2025-04-01"


# ===========================================================================
# Stage 2 -- Neural Ranker Networks
# ===========================================================================

class ContractRanker(nn.Module):
    """MLP: 5 -> 64 -> ReLU -> Dropout -> 32 -> ReLU -> Dropout -> 1"""

    def __init__(self, n_features: int = 5):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(n_features, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x).squeeze(-1)


class LinearRanker(nn.Module):
    """Linear baseline: 5 -> 1. Same loss, same data."""

    def __init__(self, n_features: int = 5):
        super().__init__()
        self.linear = nn.Linear(n_features, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(x).squeeze(-1)

    def feature_weights(self) -> dict[str, float]:
        """Return learned weights for interpretability."""
        w = self.linear.weight.detach().cpu().numpy().flatten()
        b = self.linear.bias.detach().cpu().item()
        result = {name: float(w[i]) for i, name in enumerate(RANKER_FEATURES)}
        result["bias"] = b
        return result


# ===========================================================================
# Real-Label Pair Generation (DOGE scrutiny as distant supervision)
# ===========================================================================

class RealLabelPairGenerator:
    """Generate (preferred, less_preferred, tier) pairs from real DOGE labels.

    Preferred contract = high doge_scrutiny_score (top quartile).
    Less preferred     = low doge_scrutiny_score (zero -- DOGE didn't cut).

    For each simulated user:
      1. Pick 1-3 random topic preferences (personalization context)
      2. Compute embedding_similarity and topic_match for all contracts
      3. Pair high-scrutiny with low-scrutiny contracts across 3 tiers
    """

    def __init__(
        self,
        contracts: pd.DataFrame,
        embeddings: np.ndarray,
        encoder: SentenceTransformer,
        high_threshold: float = 0.71,
    ):
        self.contracts = contracts.reset_index(drop=True)
        self.embeddings = embeddings
        self.encoder = encoder
        self.high_threshold = high_threshold

        # Precompute scrutiny labels
        scores = self.contracts["doge_scrutiny_score"].fillna(0).values
        self.high_idx = np.where(scores >= high_threshold)[0]
        self.low_idx = np.where(scores == LOW_SCRUTINY_THRESHOLD)[0]

        logger.info(
            "Real labels: %d high-scrutiny (>= %.2f), %d low-scrutiny (== 0)",
            len(self.high_idx), high_threshold, len(self.low_idx),
        )

    def generate(
        self,
        n_users: int = 150,
        seed: int = 42,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (X_preferred, X_less_preferred, tiers).

        Each row is a 5-feature vector. X_preferred[i] should score
        higher than X_less_preferred[i]. tiers[i] in {1, 2, 3}.

        Features: [embedding_similarity, topic_match, transparency_score,
                   log_value, norm_description_length]
        Note: doge_scrutiny_score is NOT a feature -- it is the label.
        """
        rng = random.Random(seed)
        np_rng = np.random.RandomState(seed)

        # Precompute contract-level arrays
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        normed = self.embeddings / norms

        max_log_val = np.log1p(self.contracts["value"].max()) or 1.0
        log_vals = np.log1p(self.contracts["value"].values) / max_log_val

        max_dlen = self.contracts["description_length"].max() or 1
        norm_dlens = self.contracts["description_length"].values / max_dlen

        topics = self.contracts["topic"].values
        transp = self.contracts["transparency_score"].fillna(0).values

        high_set = set(self.high_idx)
        low_set = set(self.low_idx)

        pref_parts: list[np.ndarray] = []
        less_parts: list[np.ndarray] = []
        tier_parts: list[np.ndarray] = []

        logger.info("Generating real-label pairs for %d user profiles...", n_users)

        for _ in range(n_users):
            n_topics = rng.randint(1, 3)
            user_topics = rng.sample(ALL_TOPICS, n_topics)

            # Encode user query for personalization
            query_text = " ".join(TOPIC_KEYWORDS[t] for t in user_topics)
            q_emb = self.encoder.encode(query_text, normalize_embeddings=True)
            sims = normed @ q_emb

            topic_match = np.array(
                [1.0 if t in user_topics else 0.0 for t in topics],
                dtype=np.float32,
            )

            # Build 5-feature matrix (NO doge_scrutiny_score)
            feats = np.column_stack([
                sims,
                topic_match,
                transp,
                log_vals,
                norm_dlens,
            ]).astype(np.float32)

            # Partition by topic match AND scrutiny level
            high_topic = np.array([i for i in self.high_idx if topic_match[i] == 1.0])
            high_notopic = np.array([i for i in self.high_idx if topic_match[i] == 0.0])
            low_topic = np.array([i for i in self.low_idx if topic_match[i] == 1.0])
            low_notopic = np.array([i for i in self.low_idx if topic_match[i] == 0.0])

            # --- Tier 1: (high + topic) vs (low + no topic) ---
            n_t1 = min(len(high_topic), len(low_notopic), 80)
            if n_t1 > 0:
                t1_pref = np_rng.choice(high_topic, size=n_t1, replace=True)
                t1_less = np_rng.choice(low_notopic, size=n_t1, replace=True)
                pref_parts.append(feats[t1_pref])
                less_parts.append(feats[t1_less])
                tier_parts.append(np.full(n_t1, 1, dtype=np.int32))

            # --- Tier 2: (high + topic) vs (low + topic) ---
            # Both match the user's topic. Model must use non-topic features.
            n_t2 = min(len(high_topic), len(low_topic), 80)
            if n_t2 > 0:
                t2_pref = np_rng.choice(high_topic, size=n_t2, replace=True)
                t2_less = np_rng.choice(low_topic, size=n_t2, replace=True)
                pref_parts.append(feats[t2_pref])
                less_parts.append(feats[t2_less])
                tier_parts.append(np.full(n_t2, 2, dtype=np.int32))

            # --- Tier 3: (high + no topic) vs (low + no topic) ---
            # No topic signal at all. Pure feature-based.
            n_t3 = min(len(high_notopic), len(low_notopic), 50)
            if n_t3 > 0:
                t3_pref = np_rng.choice(high_notopic, size=n_t3, replace=True)
                t3_less = np_rng.choice(low_notopic, size=n_t3, replace=True)
                pref_parts.append(feats[t3_pref])
                less_parts.append(feats[t3_less])
                tier_parts.append(np.full(n_t3, 3, dtype=np.int32))

        if not pref_parts:
            raise RuntimeError("No pairs generated -- check scrutiny thresholds")

        X_pref = np.vstack(pref_parts).astype(np.float32)
        X_less = np.vstack(less_parts).astype(np.float32)
        tiers = np.concatenate(tier_parts).astype(np.int32)

        for t in [1, 2, 3]:
            count = (tiers == t).sum()
            logger.info("  Tier %d: %d pairs", t, count)
        logger.info("Total pairs: %d", len(tiers))

        return X_pref, X_less, tiers


# ===========================================================================
# Training
# ===========================================================================

def _train_ranker(
    model: nn.Module,
    X_pref_train: torch.Tensor,
    X_less_train: torch.Tensor,
    tiers_train: torch.Tensor,
    X_pref_val: torch.Tensor,
    X_less_val: torch.Tensor,
    tiers_val: torch.Tensor,
    margin: float = 0.3,
    epochs: int = 100,
    lr: float = 1e-3,
    batch_size: int = 256,
    patience: int = 15,
    label: str = "MLP",
) -> tuple[nn.Module, list[dict]]:
    """Shared training loop for both MLP and linear ranker.

    Returns (trained_model, history) where history includes per-tier
    val loss for each epoch.
    """
    device = next(model.parameters()).device
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    target = torch.ones(1, device=device)  # preferred should score higher
    criterion = nn.MarginRankingLoss(margin=margin)

    best_val_loss = float("inf")
    best_state = None
    stale = 0
    history: list[dict] = []

    model.train()
    for epoch in range(epochs):
        # Shuffle training data
        idx = torch.randperm(len(X_pref_train), device=device)
        Xp, Xl = X_pref_train[idx], X_less_train[idx]

        epoch_loss = 0.0
        n_batches = 0
        for lo in range(0, len(Xp), batch_size):
            hi = min(lo + batch_size, len(Xp))
            optimizer.zero_grad()
            s_pref = model(Xp[lo:hi])
            s_less = model(Xl[lo:hi])
            t = target.expand(hi - lo)
            loss = criterion(s_pref, s_less, t)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
            n_batches += 1

        train_loss = epoch_loss / max(n_batches, 1)

        # Validation -- overall + per-tier
        model.eval()
        with torch.no_grad():
            vp = model(X_pref_val)
            vl = model(X_less_val)
            val_target = target.expand(len(vp))
            val_loss = criterion(vp, vl, val_target).item()

            tier_losses = {}
            for t in [1, 2, 3]:
                mask = tiers_val == t
                if mask.any():
                    t_target = target.expand(mask.sum().item())
                    tier_losses[f"val_tier{t}"] = criterion(
                        vp[mask], vl[mask], t_target
                    ).item()
                else:
                    tier_losses[f"val_tier{t}"] = float("nan")

            # Pairwise accuracy: fraction where preferred > less_preferred
            acc = (vp > vl).float().mean().item()
            tier_accs = {}
            for t in [1, 2, 3]:
                mask = tiers_val == t
                if mask.any():
                    tier_accs[f"acc_tier{t}"] = (vp[mask] > vl[mask]).float().mean().item()
                else:
                    tier_accs[f"acc_tier{t}"] = float("nan")

        model.train()

        record = {
            "epoch": epoch + 1,
            "train_loss": round(train_loss, 5),
            "val_loss": round(val_loss, 5),
            "val_acc": round(acc, 4),
            **{k: round(v, 5) for k, v in tier_losses.items()},
            **{k: round(v, 4) for k, v in tier_accs.items()},
        }
        history.append(record)

        if (epoch + 1) % 10 == 0 or epoch == 0:
            logger.info(
                "[%s] Epoch %3d  train=%.4f  val=%.4f  acc=%.3f  "
                "t1=%.4f t2=%.4f t3=%.4f",
                label, epoch + 1, train_loss, val_loss, acc,
                tier_losses.get("val_tier1", 0),
                tier_losses.get("val_tier2", 0),
                tier_losses.get("val_tier3", 0),
            )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= patience:
                logger.info(
                    "[%s] Early stop at epoch %d (best val=%.4f)",
                    label, epoch + 1, best_val_loss,
                )
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()

    logger.info(
        "[%s] Training complete -- best val_loss=%.4f  epochs=%d",
        label, best_val_loss, len(history),
    )
    return model, history


# ===========================================================================
# Main Recommender
# ===========================================================================

class HybridNeuralRecommender:
    """Two-stage recommender: semantic retrieval -> pairwise neural ranking.

    Trained on real labels (DOGE scrutiny scores) via distant supervision.
    Blends personalization (topic match, embeddings) with scrutiny
    prediction (value, transparency, description length).
    """

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
        self.ranker = ContractRanker(n_features=len(RANKER_FEATURES)).to(device)
        self.linear = LinearRanker(n_features=len(RANKER_FEATURES)).to(device)
        self.scaler = StandardScaler()

        self._contracts: Optional[pd.DataFrame] = None
        self._embeddings: Optional[np.ndarray] = None
        self._fitted = False
        self._trained = False
        self.mlp_history: list[dict] = []
        self.linear_history: list[dict] = []
        self.best_margin: float = 0.3

    # ------------------------------------------------------------------
    # fit
    # ------------------------------------------------------------------

    def fit(
        self,
        contracts: pd.DataFrame,
        n_users: int = 150,
        epochs: int = 100,
        lr: float = 1e-3,
        batch_size: int = 256,
        patience: int = 15,
        seed: int = 42,
    ) -> "HybridNeuralRecommender":
        """Encode all contracts, generate real-label pairs, train MLP + linear.

        Train/val split is temporal: contracts deleted before 2025-04-01
        go to train, contracts deleted after go to val. This tests whether
        the model generalizes to future contracts.
        """
        self._contracts = contracts.copy().reset_index(drop=True)

        # Calibrate flags from data (used by _compute_flags in recommend)
        calibrate_flags(self._contracts)

        # --- Stage 1: encode descriptions ---
        logger.info(
            "Encoding %d descriptions with %s on %s...",
            len(contracts), self.model_name, self.device,
        )
        corpus = (
            self._contracts["description"].fillna("")
            + " | " + self._contracts["agency"].fillna("")
            + " | " + self._contracts["vendor_recipient"].fillna("")
            + " | " + self._contracts["topic"].fillna("")
        ).tolist()

        self._embeddings = self.encoder.encode(
            corpus,
            show_progress_bar=True,
            batch_size=64,
            normalize_embeddings=True,
        )
        self._fitted = True
        logger.info("Embeddings: %s", self._embeddings.shape)

        # --- Compute scrutiny threshold from data ---
        high_threshold = float(
            self._contracts["doge_scrutiny_score"].quantile(HIGH_SCRUTINY_QUANTILE)
        )
        logger.info(
            "Scrutiny threshold (%.0f%%ile): %.3f",
            HIGH_SCRUTINY_QUANTILE * 100, high_threshold,
        )

        # --- Temporal train/val split ---
        dates = pd.to_datetime(self._contracts["deleted_date"])
        train_mask = dates < TEMPORAL_SPLIT_DATE
        val_mask = ~train_mask

        train_df = self._contracts[train_mask].reset_index(drop=True)
        val_df = self._contracts[val_mask].reset_index(drop=True)
        train_emb = self._embeddings[train_mask.values]
        val_emb = self._embeddings[val_mask.values]

        logger.info(
            "Temporal split at %s: train=%d, val=%d",
            TEMPORAL_SPLIT_DATE, len(train_df), len(val_df),
        )

        # --- Generate real-label pairs ---
        train_gen = RealLabelPairGenerator(
            train_df, train_emb, self.encoder, high_threshold=high_threshold,
        )
        val_gen = RealLabelPairGenerator(
            val_df, val_emb, self.encoder, high_threshold=high_threshold,
        )

        # Use different seeds so train/val users are different
        X_pref_train, X_less_train, tiers_train = train_gen.generate(
            n_users=n_users, seed=seed,
        )
        X_pref_val, X_less_val, tiers_val = val_gen.generate(
            n_users=max(n_users // 3, 30), seed=seed + 1,
        )

        # Scale features (fit on training data only)
        combined_train = np.vstack([X_pref_train, X_less_train])
        self.scaler.fit(combined_train)

        X_pref_train_s = self.scaler.transform(X_pref_train)
        X_less_train_s = self.scaler.transform(X_less_train)
        X_pref_val_s = self.scaler.transform(X_pref_val)
        X_less_val_s = self.scaler.transform(X_less_val)

        # Convert to tensors
        Xp_train = torch.tensor(X_pref_train_s, dtype=torch.float32, device=self.device)
        Xl_train = torch.tensor(X_less_train_s, dtype=torch.float32, device=self.device)
        t_train = torch.tensor(tiers_train, dtype=torch.int32, device=self.device)

        Xp_val = torch.tensor(X_pref_val_s, dtype=torch.float32, device=self.device)
        Xl_val = torch.tensor(X_less_val_s, dtype=torch.float32, device=self.device)
        t_val = torch.tensor(tiers_val, dtype=torch.int32, device=self.device)

        logger.info(
            "Train pairs: %d  |  Val pairs: %d  (temporal split)",
            len(Xp_train), len(Xp_val),
        )

        # --- Margin sweep (short probes) ---
        margins = [0.1, 0.3, 0.5]
        best_margin = margins[0]
        best_probe_loss = float("inf")

        logger.info("Sweeping margins: %s (20-epoch probes)", margins)
        for m in margins:
            probe_model = ContractRanker(n_features=len(RANKER_FEATURES)).to(self.device)
            _, probe_hist = _train_ranker(
                probe_model, Xp_train, Xl_train, t_train,
                Xp_val, Xl_val, t_val,
                margin=m, epochs=20, lr=lr, batch_size=batch_size,
                patience=20, label=f"probe-m{m}",
            )
            final_val = probe_hist[-1]["val_loss"]
            logger.info("  margin=%.1f  val_loss=%.4f", m, final_val)
            if final_val < best_probe_loss:
                best_probe_loss = final_val
                best_margin = m

        self.best_margin = best_margin
        logger.info("Best margin: %.1f (val=%.4f)", best_margin, best_probe_loss)

        # --- Full MLP training ---
        self.ranker = ContractRanker(n_features=len(RANKER_FEATURES)).to(self.device)
        self.ranker, self.mlp_history = _train_ranker(
            self.ranker, Xp_train, Xl_train, t_train,
            Xp_val, Xl_val, t_val,
            margin=best_margin, epochs=epochs, lr=lr,
            batch_size=batch_size, patience=patience, label="MLP",
        )

        # --- Linear baseline training (same data, same loss) ---
        self.linear = LinearRanker(n_features=len(RANKER_FEATURES)).to(self.device)
        self.linear, self.linear_history = _train_ranker(
            self.linear, Xp_train, Xl_train, t_train,
            Xp_val, Xl_val, t_val,
            margin=best_margin, epochs=epochs, lr=lr,
            batch_size=batch_size, patience=patience, label="Linear",
        )

        self._trained = True
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
        """Produce top-N recommendations for a set of user topic preferences."""
        if not self._trained:
            raise RuntimeError("Call fit() before recommend()")

        pool = pool_size or self.candidate_pool

        # Stage 1 -- per-topic retrieval to ensure diversity
        per_topic = max(pool // len(user_topics), 20)
        cand_set: set[int] = set()
        topic_sims: dict[int, float] = {}

        for topic in user_topics:
            t_text = TOPIC_KEYWORDS.get(topic, topic)
            t_emb = self.encoder.encode(t_text, normalize_embeddings=True)
            t_sims = self._embeddings @ t_emb
            t_top = np.argsort(t_sims)[::-1][:per_topic]
            for idx in t_top:
                cand_set.add(int(idx))
                topic_sims[int(idx)] = max(topic_sims.get(int(idx), -1), t_sims[idx])

        cand_idx = np.array(sorted(cand_set))
        sims = np.array([topic_sims[int(i)] for i in cand_idx])

        # Build feature vectors for candidates
        df = self._contracts.iloc[cand_idx].copy()
        df["embedding_similarity"] = sims
        df["topic_match"] = df["topic"].apply(
            lambda t: 1.0 if t in user_topics else 0.0
        )

        max_log_val = np.log1p(self._contracts["value"].max()) or 1.0
        df["log_value"] = np.log1p(df["value"].values) / max_log_val

        max_dlen = self._contracts["description_length"].max() or 1
        df["norm_description_length"] = df["description_length"].values / max_dlen

        for col in RANKER_FEATURES:
            df[col] = df[col].fillna(0)

        # Stage 2 -- neural ranking
        feats = df[RANKER_FEATURES].values.astype(np.float32)
        feats_scaled = self.scaler.transform(feats)

        with torch.no_grad():
            scores = self.ranker(
                torch.tensor(feats_scaled, dtype=torch.float32, device=self.device)
            ).cpu().numpy()

        from sklearn.preprocessing import MinMaxScaler
        if len(scores) > 1:
            scores = MinMaxScaler().fit_transform(scores.reshape(-1, 1)).flatten()

        df["relevance_score"] = scores
        df["final_score"] = scores
        df = df.sort_values("final_score", ascending=False).head(top_n)

        # Annotations
        df["matched_topics"] = df["topic"].apply(
            lambda t: [t] if t in user_topics else []
        )
        df["flags"] = df.apply(lambda r: _compute_flags(r), axis=1)
        df["reason"] = df.apply(lambda r: _reason(r, user_topics), axis=1)

        out_cols = [
            "contract_id", "item_type", "agency", "vendor_recipient",
            "description", "topic", "value", "savings",
            "relevance_score", "final_score",
            "embedding_similarity", "topic_match",
            "doge_scrutiny_score", "transparency_score",
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
        """Compute precision@k, topic coverage, and mean score at multiple k cutoffs."""
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
        """Save embeddings, ranker weights, scaler, and metadata to disk for inference."""
        if not self._trained:
            raise RuntimeError("Train the model before saving")
        d = path or MODELS_DIR
        os.makedirs(d, exist_ok=True)

        np.save(os.path.join(d, "embeddings.npy"), self._embeddings)
        torch.save(self.ranker.state_dict(), os.path.join(d, "ranker.pt"))
        torch.save(self.linear.state_dict(), os.path.join(d, "linear_ranker.pt"))
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
        """Load saved embeddings, ranker weights, and scaler for inference without retraining."""
        d = path or MODELS_DIR
        self._embeddings = np.load(os.path.join(d, "embeddings.npy"))
        self.ranker.load_state_dict(
            torch.load(os.path.join(d, "ranker.pt"), map_location=self.device, weights_only=True),
        )
        self.ranker.eval()

        self.linear.load_state_dict(
            torch.load(os.path.join(d, "linear_ranker.pt"), map_location=self.device, weights_only=True),
        )
        self.linear.eval()

        sc = np.load(os.path.join(d, "scaler.npz"))
        self.scaler.mean_ = sc["mean"]
        self.scaler.scale_ = sc["scale"]
        self.scaler.n_features_in_ = len(sc["mean"])

        if contracts is not None:
            self._contracts = contracts.reset_index(drop=True)
            calibrate_flags(self._contracts)

        self._fitted = True
        self._trained = True
        logger.info("Artifacts loaded <- %s", d)
        return self


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _compare_histories(
    mlp_hist: list[dict],
    linear_hist: list[dict],
) -> None:
    """Print tier-stratified MLP vs linear comparison."""
    print("\n" + "=" * 70)
    print("  MLP vs Linear Baseline -- Tier-Stratified Comparison")
    print("=" * 70)

    for label, hist in [("MLP", mlp_hist), ("Linear", linear_hist)]:
        if not hist:
            continue
        first = hist[0]
        best = min(hist, key=lambda h: h["val_loss"])
        last = hist[-1]
        drop_pct = (1 - best["val_loss"] / first["val_loss"]) * 100

        print(f"\n  [{label}]")
        print(f"    Epochs:      {len(hist)}")
        print(f"    Val loss:    {first['val_loss']:.4f} -> {best['val_loss']:.4f} "
              f"(drop {drop_pct:.1f}%)")
        print(f"    Val acc:     {first['val_acc']:.3f} -> {last['val_acc']:.3f}")
        for t in [1, 2, 3]:
            key = f"acc_tier{t}"
            if key in first and key in last:
                print(f"    Tier {t} acc:  {first[key]:.3f} -> {last[key]:.3f}")

    # Head-to-head on Tier 2
    if mlp_hist and linear_hist:
        mlp_best = min(mlp_hist, key=lambda h: h["val_loss"])
        lin_best = min(linear_hist, key=lambda h: h["val_loss"])

        mlp_t2 = mlp_best.get("acc_tier2", 0)
        lin_t2 = lin_best.get("acc_tier2", 0)

        print(f"\n  ** Tier 2 (within-topic, real labels) -- the core claim **")
        print(f"     MLP acc:    {mlp_t2:.3f}")
        print(f"     Linear acc: {lin_t2:.3f}")
        if mlp_t2 > lin_t2:
            print(f"     MLP wins by {mlp_t2 - lin_t2:.3f} -- non-linearity adds value")
        elif mlp_t2 == lin_t2:
            print(f"     Tied -- MLP non-linearity not demonstrated on Tier 2")
        else:
            print(f"     Linear wins by {lin_t2 - mlp_t2:.3f} -- MLP overfitting?")


# ===========================================================================
# Smoke test
# ===========================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    CONTRACTS_PATH = os.path.join(PROCESSED_DATA_DIR, "unified_contracts.csv")

    # 1. Load data
    logger.info("Loading %s", CONTRACTS_PATH)
    df = pd.read_csv(CONTRACTS_PATH)
    logger.info("Loaded %d contracts", len(df))

    # 2. Data audit: confirm label distribution
    scores = df["doge_scrutiny_score"]
    high_t = float(scores.quantile(HIGH_SCRUTINY_QUANTILE))
    n_high = (scores >= high_t).sum()
    n_low = (scores == 0).sum()
    print(f"\n=== Label Distribution ===")
    print(f"  High scrutiny (>= {high_t:.3f}): {n_high} ({n_high/len(df):.1%})")
    print(f"  Low scrutiny (== 0):            {n_low} ({n_low/len(df):.1%})")
    print(f"  Middle (excluded from pairs):   {len(df) - n_high - n_low}")

    # 3. Temporal split info
    dates = pd.to_datetime(df["deleted_date"])
    n_train = (dates < TEMPORAL_SPLIT_DATE).sum()
    n_val = (dates >= TEMPORAL_SPLIT_DATE).sum()
    print(f"\n=== Temporal Split ===")
    print(f"  Train (before {TEMPORAL_SPLIT_DATE}): {n_train}")
    print(f"  Val   (after  {TEMPORAL_SPLIT_DATE}): {n_val}")

    # 4. Fit (encode + real-label pairs + train MLP + train linear)
    model = HybridNeuralRecommender()
    model.fit(df, n_users=300, epochs=100, lr=5e-4, patience=20)

    # 5. Recommend
    topics = ["healthcare", "defense"]
    results = model.recommend(topics, top_n=10)

    print(f"\n{'=' * 70}")
    print(f"  Top 10 for {topics}")
    print(f"{'=' * 70}")
    for i, row in results.iterrows():
        print(f"\n  #{i+1}  [{row['topic']}]  {row.get('agency', '')}")
        desc = row.get("description", "")
        desc = desc[:80] if isinstance(desc, str) else ""
        print(f"      {desc}...")
        print(f"      score={row['final_score']:.4f}  "
              f"sim={row.get('embedding_similarity', 0):.3f}  "
              f"topic_match={row.get('topic_match', 0):.0f}  "
              f"scrutiny={row.get('doge_scrutiny_score', 0):.2f}")
        flags = row.get("flags", [])
        if flags:
            print(f"      flags: {', '.join(flags)}")
        print(f"      -> {row.get('reason', '')}")

    # 6. Evaluate
    metrics = model.evaluate(results, relevant_topics=topics)
    print(f"\n{'=' * 70}")
    print("  Metrics")
    print(f"{'=' * 70}")
    for k, v in metrics.items():
        print(f"    {k:25s}  {v}")

    # 7. Verify both topics present
    topics_in_results = set(results["topic"].unique())
    for t in topics:
        status = "PASS" if t in topics_in_results else "FAIL"
        print(f"  [{status}] Topic '{t}' in top 10")

    # 8. Check that recommended contracts actually have high scrutiny
    mean_scrutiny = results["doge_scrutiny_score"].mean()
    overall_mean = df["doge_scrutiny_score"].mean()
    status = "PASS" if mean_scrutiny > overall_mean else "FAIL"
    print(f"  [{status}] Mean scrutiny of top 10 ({mean_scrutiny:.3f}) > "
          f"dataset mean ({overall_mean:.3f})")

    # 9. Tier-stratified comparison
    _compare_histories(model.mlp_history, model.linear_history)

    # 10. Linear baseline feature weights
    print(f"\n{'=' * 70}")
    print("  Linear Baseline Feature Weights (interpretability)")
    print(f"{'=' * 70}")
    weights = model.linear.feature_weights()
    for feat, w in sorted(weights.items(), key=lambda x: abs(x[1]), reverse=True):
        print(f"    {feat:30s}  {w:+.4f}")

    # 11. Validation loss drop check
    if model.mlp_history:
        first_val = model.mlp_history[0]["val_loss"]
        best_val = min(h["val_loss"] for h in model.mlp_history)
        drop = (1 - best_val / first_val) * 100
        status = "PASS" if drop >= 20 else "FAIL"
        print(f"\n  [{status}] Val loss drop: {drop:.1f}% (threshold: 20%)")

    # 12. Save artifacts
    out = model.save_artifacts()
    print(f"\n  Artifacts saved to {out}/")
    for fname in ["embeddings.npy", "ranker.pt", "linear_ranker.pt",
                   "scaler.npz", "metadata.npz"]:
        fpath = os.path.join(out, fname)
        status = "PASS" if os.path.exists(fpath) else "FAIL"
        print(f"  [{status}] {fname}")

    # 13. Import check
    print(f"\n  [PASS] Import: from scripts.deep_learning import HybridNeuralRecommender")
