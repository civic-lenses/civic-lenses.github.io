# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""
Generate pre-computed recommendation data for the static app.

Runs the classical model for each topic and exports a JSON file
that the frontend loads at runtime. This is the "inference" step
for the GitHub Pages deployment.

Usage:
    python scripts/generate_app_data.py
"""

import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import PROCESSED_DATA_DIR
from scripts.classical import TFIDFRecommender, TOPIC_KEYWORDS


def main():
    contracts_path = os.path.join(PROCESSED_DATA_DIR, "unified_contracts.csv")
    df = pd.read_csv(contracts_path)
    print(f"Loaded {len(df)} contracts")

    model = TFIDFRecommender()
    model.fit(df)

    topics = list(TOPIC_KEYWORDS.keys())
    app_data = {"topics": topics, "recommendations": {}, "stats": {}}

    # Per-topic recommendations
    for topic in topics:
        recs = model.recommend([topic], top_n=20, alpha=0.7)
        records = []
        for _, row in recs.iterrows():
            def clean(val, fallback=""):
                s = str(val) if pd.notna(val) else fallback
                return fallback if s.lower() == "nan" else s

            records.append({
                "contract_id": clean(row.get("contract_id")),
                "agency": clean(row.get("agency"), "Unknown Agency"),
                "vendor": clean(row.get("vendor_recipient"), "Unknown Vendor"),
                "description": clean(row.get("description"), "No description available")[:200],
                "topic": clean(row.get("topic"), "general_spending"),
                "value": float(row.get("value", 0)),
                "savings": float(row.get("savings", 0)),
                "scrutiny": float(row.get("doge_scrutiny_score", 0)),
                "transparency": float(row.get("transparency_score", 0)),
                "relevance": round(float(row.get("relevance_score", 0)), 4),
                "final_score": round(float(row.get("final_score", 0)), 4),
                "flags": row.get("flags", []) if isinstance(row.get("flags"), list) else [],
                "reason": str(row.get("reason", "")),
            })
        app_data["recommendations"][topic] = records

    # Global stats
    app_data["stats"] = {
        "total_contracts": len(df),
        "total_value": float(df["value"].sum()),
        "flagged": int((df["doge_scrutiny_score"] >= df["doge_scrutiny_score"].quantile(0.90)).sum()),
        "mean_scrutiny": round(float(df["doge_scrutiny_score"].mean()), 3),
        "topics": {
            t: int((df["topic"] == t).sum()) for t in topics
        },
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "app", "data.json")
    with open(out_path, "w") as f:
        json.dump(app_data, f, indent=None)

    size_kb = os.path.getsize(out_path) / 1024
    print(f"Wrote {out_path} ({size_kb:.0f} KB)")
    print(f"Topics: {len(topics)}, Contracts per topic: 20")


if __name__ == "__main__":
    main()
