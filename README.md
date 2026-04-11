# Civic Lenses

[![Deploy Site](https://github.com/civic-lenses/civic-lenses.github.io/actions/workflows/deploy.yml/badge.svg)](https://github.com/civic-lenses/civic-lenses.github.io/actions/workflows/deploy.yml)
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/civic-lenses/civic-lenses.github.io?quickstart=1)

AIPI 540 project — a personalized federal spending recommender that helps citizens track government contracts, grants, and leases using data from GDELT, DOGE.gov, USAspending.gov, and SAM.gov.

## Setup

```bash
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your SAM.gov API key
```

## Data Sources

| Source | Auth | Description |
|--------|------|-------------|
| [GDELT](https://api.gdeltproject.org) | None | Global news coverage of government spending topics |
| [DOGE.gov](https://api.doge.gov) | None | Cancelled grants, contracts, leases, and payment data |
| [USAspending.gov](https://api.usaspending.gov) | None | Federal award and agency spending data |
| [SAM.gov](https://api.sam.gov) | API key (free) | Federal contract opportunities and entity registrations |

## Pipeline

### 1. Fetch raw data

```bash
# Fetch from all sources
python scripts/make_dataset.py

# Fetch from specific sources
python scripts/make_dataset.py --sources gdelt doge usaspending

# Test individual clients
python scripts/gdelt_client.py
python scripts/doge_client.py
```

Raw CSVs are saved to `data/raw/`:
- `gdelt_articles.csv` — news articles for 6 government spending queries over a 30-day window
- `doge_cancelled_contracts.csv`, `doge_cancelled_grants.csv`, `doge_cancelled_leases.csv`
- `doge_payment_stats.csv`
- `usaspending_agencies.csv`, `usaspending_awards.csv`
- `sam_opportunities.csv`

### 2. Preprocess & join

```bash
python scripts/preprocess.py
```

Merges all raw sources into `data/processed/unified_contracts.csv`. Steps:
1. Normalize DOGE contracts, grants, and leases to a common schema
2. Assign topic labels from agency name keywords
3. Compute **DOGE scrutiny score** — `savings / value` ratio (0–1)
4. Join USAspending agency budget figures (obligated & outlay amounts)
5. Join **GDELT popularity scores** — recency-weighted news signal per topic
6. Compute **transparency score** — readability proxy based on description length, jargon density, and specificity
7. Compute **citizen impact score** — composite of all four signals

#### Unified dataset schema (`unified_contracts.csv`)

| Column | Description |
|--------|-------------|
| `contract_id` | Unique identifier (`DOGE_C_`, `DOGE_G_`, `DOGE_L_` prefixed) |
| `item_type` | `contract`, `grant`, or `lease` |
| `agency` | Awarding agency (normalized) |
| `vendor_recipient` | Vendor (contracts) or recipient (grants/leases) |
| `description` | Plain-text description |
| `value` | Total contract/grant value ($) |
| `savings` | DOGE claimed savings ($) |
| `deleted_date` | Date DOGE terminated it |
| `doge_flag` | 1 if terminated by DOGE, 0 otherwise |
| `doge_scrutiny_score` | Normalized savings/value ratio (0–1) |
| `agency_obligated_amount` | From USAspending |
| `agency_outlay_amount` | From USAspending |
| `gdelt_popularity_score` | Recency-weighted news score (0–1) |
| `gdelt_article_count` | Raw article count for topic |
| `topic` | Topic category (healthcare, defense, education, etc.) |
| `description_length` | Character count of description |
| `transparency_score` | Readability proxy (0–1, higher = clearer) |
| `citizen_impact_score` | Composite score (0–1) |

### 3. Models

#### Naive baseline

```bash
python scripts/naive_baseline.py
```

Ranks contracts purely by GDELT news volume for the matching topic — no personalization. Every user sees the same list. Serves as the floor all downstream models must beat.

#### Classical ML model (TF-IDF + cosine similarity)

```bash
python scripts/classical.py
```

Content-based recommender that scores each contract individually against a user's topic preferences:

- **Fit**: TF-IDF vectorizer on contract descriptions + agency + topic (up to 15k features, 1–2-grams)
- **Recommend**: cosine similarity between user query (expanded from topic seed keywords) and each contract
- **Re-rank**: `final_score = 0.7 × relevance + 0.3 × citizen_impact_score`
- **Output per card**: `relevance_score`, `final_score`, `matched_topics`, `flags`, plain-English `reason` snippet

Flags surfaced: `doge_flag`, `vague_description`, `high_value` (>$1B), `high_scrutiny`, `trending`.

Evaluation metrics: `precision@k`, `topic_coverage`, `mean_relevance`, `mean_final_score` at k=5/10/20.

## Project Structure

```
├── config.py                  <- API endpoints and path constants
├── scripts/
│   ├── make_dataset.py        <- Orchestrator: fetch all raw data
│   ├── preprocess.py          <- Merge + feature engineering pipeline
│   ├── naive_baseline.py      <- GDELT popularity baseline model
│   ├── classical.py           <- TF-IDF + cosine similarity recommender
│   ├── gdelt_client.py        <- GDELT DOC API client (rate-limit aware)
│   ├── sam_client.py          <- SAM.gov API client
│   ├── usaspending_client.py  <- USAspending API client
│   └── doge_client.py         <- DOGE.gov API client
├── data/
│   ├── raw/                   <- Raw API pulls (CSVs)
│   ├── processed/             <- unified_contracts.csv
│   └── outputs/               <- Model outputs
├── models/                    <- Trained models
├── app/                       <- Frontend (index.html, main.js, styles.css)
├── .env.example               <- Required environment variables
└── requirements.txt
```

## Topic Categories

Topics used throughout the pipeline for filtering, scoring, and user onboarding:

`healthcare` · `defense` · `education` · `infrastructure` · `foreign_aid` · `research` · `energy` · `agriculture` · `finance` · `government_efficiency` · `general_spending` · `doge_scrutiny`
