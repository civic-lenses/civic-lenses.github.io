# AIPI 540 — Civic Lenses

[![Duke AIPI 540](https://img.shields.io/badge/Duke-AIPI%20540-012169)](https://masters.pratt.duke.edu/)
[![Deploy Site](https://github.com/civic-lenses/civic-lenses.github.io/actions/workflows/deploy.yml/badge.svg)](https://github.com/civic-lenses/civic-lenses.github.io/actions/workflows/deploy.yml)

A personalized federal spending recommender that helps citizens track government contracts, grants, and leases using data from GDELT, DOGE.gov, USAspending.gov, and SAM.gov.

**[Live App →](https://civic-lenses.github.io/)** · **[Requirements Checklist →](https://civic-lenses.github.io/checklist/)**

---

## Problem

Federal spending data is scattered across multiple government systems (SAM.gov, USAspending.gov, DOGE.gov) with no unified way for citizens to discover what matters to them. News coverage adds signal but isn't connected to the underlying contract data. Civic Lenses joins these sources, scores each contract on transparency, public interest, and news attention, and recommends the most relevant items based on a user's topic preferences.

## Data Sources

| Source | Auth | Description |
|--------|------|-------------|
| [GDELT](https://api.gdeltproject.org) | None | News coverage of government spending topics |
| [DOGE.gov](https://api.doge.gov) | None | Cancelled grants, contracts, leases |
| [USAspending.gov](https://api.usaspending.gov) | None | Federal award and agency spending |
| [SAM.gov](https://api.sam.gov) | API key (free) | Contract opportunities and entity registrations |

## Models

| Model | File | Approach | Personalized? |
|-------|------|----------|---------------|
| Naive baseline | `scripts/naive_baseline.py` | Rank by GDELT news volume per topic | No |
| Classical ML | `scripts/classical.py` | TF-IDF + cosine similarity, re-ranked by citizen impact score | Yes |
| Deep learning | `scripts/deep_learning.py` | Sentence Transformer embeddings + pairwise MLP ranker trained on DOGE scrutiny labels | Yes |

**Selected model**: Classical ML (TF-IDF). See `docs/report.md` R13-R14 for justification.

## Project Structure

```
├── Makefile                   setup, data, train, run commands
├── config.py                  API endpoints and path constants
├── scripts/
│   ├── make_dataset.py        fetch all raw data
│   ├── preprocess.py          merge + feature engineering
│   ├── naive_baseline.py      GDELT popularity baseline
│   ├── classical.py           TF-IDF + cosine similarity recommender
│   ├── deep_learning.py       Sentence Transformer + pairwise neural ranker
│   ├── experiment.py          classical vs DL model comparison
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

## Quickstart

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/civic-lenses/civic-lenses.github.io?quickstart=1)

```bash
make venv                      # create .venv + install dependencies
source .venv/bin/activate
cp .env.example .env           # add your SAM.gov API key
make data                      # fetch raw data from all sources
make features                  # preprocess → data/processed/
make train                     # train all three models
make run                       # launch the app
```

Run `make` to see all available commands.

## Team

Diya Mirji · Jonas Neves · Michael Saju

Duke University · AIPI 540 · Spring 2026
