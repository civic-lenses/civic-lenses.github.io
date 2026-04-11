# AIPI 540 — Civic Lenses

[![Deploy Site](https://github.com/civic-lenses/civic-lenses.github.io/actions/workflows/deploy.yml/badge.svg)](https://github.com/civic-lenses/civic-lenses.github.io/actions/workflows/deploy.yml)
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/civic-lenses/civic-lenses.github.io?quickstart=1)

A personalized federal spending recommender that helps citizens track government contracts, grants, and leases using data from GDELT, DOGE.gov, USAspending.gov, and SAM.gov.

**[Live App →](https://civic-lenses.github.io/)** · **[Requirements Checklist →](https://civic-lenses.github.io/checklist/)**

---

## Setup

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env   # add your SAM.gov API key
```

## Data Sources

| Source | Auth | Description |
|--------|------|-------------|
| [GDELT](https://api.gdeltproject.org) | None | News coverage of government spending topics |
| [DOGE.gov](https://api.doge.gov) | None | Cancelled grants, contracts, leases |
| [USAspending.gov](https://api.usaspending.gov) | None | Federal award and agency spending |
| [SAM.gov](https://api.sam.gov) | API key (free) | Contract opportunities and entity registrations |

## Pipeline

```bash
python scripts/make_dataset.py          # 1. Fetch raw data → data/raw/
python scripts/preprocess.py            # 2. Merge + feature engineering → data/processed/
python scripts/naive_baseline.py        # 3a. Naive baseline (GDELT popularity)
python scripts/classical.py             # 3b. Classical ML (TF-IDF + cosine similarity)
```

### Models

| Model | Approach | Personalized? |
|-------|----------|---------------|
| Naive baseline | Rank by GDELT news volume per topic | No |
| Classical ML | TF-IDF + cosine similarity, re-ranked by citizen impact score | Yes |
| Deep learning | TBD | TBD |

## Project Structure

```
├── config.py                  API endpoints and path constants
├── scripts/
│   ├── make_dataset.py        fetch all raw data
│   ├── preprocess.py          merge + feature engineering
│   ├── naive_baseline.py      GDELT popularity baseline
│   ├── classical.py           TF-IDF + cosine similarity recommender
│   ├── generate_checklist.py  render requirements checklist HTML
│   ├── gdelt_client.py        GDELT DOC API client
│   ├── sam_client.py          SAM.gov API client
│   ├── usaspending_client.py  USAspending API client
│   └── doge_client.py         DOGE.gov API client
├── app/                       frontend (deployed to gh-pages)
├── data/
│   ├── raw/                   raw API pulls
│   ├── processed/             unified_contracts.csv
│   └── outputs/               model outputs
├── models/                    trained models
├── notebooks/                 exploration notebooks
├── .env.example               required environment variables
└── requirements.txt
```

## Requirements Checklist

Tracked in [`.github/REQUIREMENTS_CHECKLIST.md`](.github/REQUIREMENTS_CHECKLIST.md).

## Team

Diya Mirji · Jonas Neves · Michael Saju

Duke University · AIPI 540 · Spring 2026
