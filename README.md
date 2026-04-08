# Civic Lenses

AIPI 540 project — analyzing federal spending, contracts, and government efficiency using data from GDELT, SAM.gov, USAspending.gov, and DOGE.gov.

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
| [SAM.gov](https://api.sam.gov) | API key (free) | Federal contract opportunities and entity registrations |
| [USAspending.gov](https://api.usaspending.gov) | None | Federal award and agency spending data |
| [DOGE.gov](https://api.doge.gov) | None | Cancelled grants, contracts, leases, and payment data |

## Pulling Data

```bash
# Fetch from all sources
python scripts/make_dataset.py

# Fetch from specific sources
python scripts/make_dataset.py --sources gdelt doge usaspending

# Test individual clients
python scripts/doge_client.py
python scripts/gdelt_client.py
```

Raw CSVs are saved to `data/raw/`.

## Project Structure

```
├── config.py               <- API endpoints and settings
├── scripts/
│   ├── make_dataset.py     <- Orchestrator to pull all data
│   ├── gdelt_client.py     <- GDELT API client
│   ├── sam_client.py       <- SAM.gov API client
│   ├── usaspending_client.py <- USAspending API client
│   └── doge_client.py      <- DOGE.gov API client
├── data/
│   ├── raw/                <- Raw API pulls
│   ├── processed/          <- Cleaned/merged datasets
│   └── outputs/            <- Model outputs
├── models/                 <- Trained models
└── notebooks/              <- Exploration notebooks
```
