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
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import PROCESSED_DATA_DIR
from scripts.classical import TFIDFRecommender, TOPIC_KEYWORDS

# Display labels for topic keys used in reason text
TOPIC_LABELS: dict[str, str] = {
    "healthcare": "Healthcare",
    "education": "Education",
    "defense": "Defense",
    "infrastructure": "Infrastructure",
    "foreign_aid": "Foreign Aid",
    "general_spending": "General Spending",
    "government_efficiency": "Gov. Efficiency",
    "research": "Research",
    "finance": "Finance",
    "agriculture": "Agriculture",
    "energy": "Energy",
    "doge_scrutiny": "DOGE Scrutiny",
}

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove HTML tags and collapse extra whitespace."""
    return _HTML_TAG_RE.sub(" ", text).strip()


def _humanize_reason(reason: str) -> str:
    """Replace raw topic keys with display labels in reason text."""
    for key, label in TOPIC_LABELS.items():
        reason = reason.replace(key, label)
    return reason


def main():
    contracts_path = os.path.join(PROCESSED_DATA_DIR, "unified_contracts.csv")
    df = pd.read_csv(contracts_path)
    print(f"Loaded {len(df)} contracts")

    model = TFIDFRecommender()
    model.fit(df)

    topics = list(TOPIC_KEYWORDS.keys())
    app_data = {"topics": topics, "recommendations": {}, "stats": {}}

    def clean(val, fallback=""):
        s = str(val) if pd.notna(val) else fallback
        return fallback if s.lower() == "nan" else s

    # Build lookup for enriched fields not in model output
    enriched_cols = {}
    for _, row in df.iterrows():
        cid = str(row.get("contract_id", ""))
        if cid:
            enriched_cols[cid] = {
                "deleted_date": clean(row.get("deleted_date"), ""),
                "state": clean(row.get("state"), ""),
                "location": clean(row.get("location"), ""),
            }

    # Per-topic recommendations
    for topic in topics:
        recs = model.recommend([topic], top_n=20, alpha=0.7)
        records = []
        for _, row in recs.iterrows():
            cid = clean(row.get("contract_id"))
            extra = enriched_cols.get(cid, {})

            records.append({
                "contract_id": cid,
                "agency": clean(row.get("agency"), "Unknown Agency"),
                "vendor": clean(row.get("vendor_recipient"), "Unknown Vendor"),
                "description": _strip_html(clean(row.get("description"), "No description available"))[:200],
                "topic": clean(row.get("topic"), "general_spending"),
                "value": float(row.get("value", 0)),
                "savings": float(row.get("savings", 0)),
                "scrutiny": float(row.get("doge_scrutiny_score", 0)),
                "transparency": float(row.get("transparency_score", 0)),
                "relevance": round(float(row.get("relevance_score", 0)), 4),
                "final_score": round(float(row.get("final_score", 0)), 4),
                "deleted_date": extra.get("deleted_date", ""),
                "state": extra.get("state", ""),
                "location": extra.get("location", ""),
                "flags": row.get("flags", []) if isinstance(row.get("flags"), list) else [],
                "reason": _humanize_reason(str(row.get("reason", ""))),
            })
        app_data["recommendations"][topic] = records

    # Global stats
    state_stats = {}
    for state in df["state"].dropna().unique():
        sdf = df[df["state"] == state]
        state_stats[state] = {
            "count": int(len(sdf)),
            "value": float(sdf["value"].sum()),
            "savings": float(sdf["savings"].sum()),
        }

    # Timeline: savings by month
    timeline = {}
    dates = pd.to_datetime(df["deleted_date"], errors="coerce")
    df_dated = df[dates.notna()].copy()
    df_dated["month"] = dates[dates.notna()].dt.to_period("M").astype(str)
    for month, group in df_dated.groupby("month"):
        timeline[month] = {
            "count": int(len(group)),
            "value": float(group["value"].sum()),
            "savings": float(group["savings"].sum()),
        }

    # Top agencies
    agency_stats = {}
    for agency, group in df.groupby("agency"):
        agency_stats[agency] = {
            "count": int(len(group)),
            "value": float(group["value"].sum()),
            "savings": float(group["savings"].sum()),
        }
    # Keep top 15 by value
    top_agencies = dict(sorted(agency_stats.items(), key=lambda x: x[1]["value"], reverse=True)[:15])

    app_data["stats"] = {
        "total_contracts": len(df),
        "total_value": float(df["value"].sum()),
        "total_savings": float(df["savings"].sum()),
        "flagged": int((df["doge_scrutiny_score"] >= df["doge_scrutiny_score"].quantile(0.90)).sum()),
        "mean_scrutiny": round(float(df["doge_scrutiny_score"].mean()), 3),
        "topics": {
            t: int((df["topic"] == t).sum()) for t in topics
        },
        "state_topics": {
            state: {
                t: int((df[(df["state"] == state) & (df["topic"] == t)].shape[0]))
                for t in topics
                if (df[(df["state"] == state) & (df["topic"] == t)].shape[0]) > 0
            }
            for state in df["state"].dropna().unique()
        },
        "states": state_stats,
        "timeline": timeline,
        "agencies": top_agencies,
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "app", "data.json")
    with open(out_path, "w") as f:
        json.dump(app_data, f, indent=None)

    size_kb = os.path.getsize(out_path) / 1024
    print(f"Wrote {out_path} ({size_kb:.0f} KB)")
    print(f"Topics: {len(topics)}, Contracts per topic: 20")


if __name__ == "__main__":
    main()
