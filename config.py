"""Project configuration — API endpoints and settings."""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# SAM.gov
# ---------------------------------------------------------------------------
SAM_API_KEY = os.getenv("SAM_GOV_API_KEY", "")
SAM_BASE_URL = "https://api.sam.gov"
SAM_ENTITIES_URL = f"{SAM_BASE_URL}/entity-information/v3/entities"
SAM_OPPORTUNITIES_URL = f"{SAM_BASE_URL}/opportunities/v2/search"

# ---------------------------------------------------------------------------
# USAspending.gov
# ---------------------------------------------------------------------------
USASPENDING_BASE_URL = "https://api.usaspending.gov/api/v2"

# ---------------------------------------------------------------------------
# GDELT
# ---------------------------------------------------------------------------
GDELT_BASE_URL = "https://api.gdeltproject.org/api/v2"
GDELT_DOC_URL = f"{GDELT_BASE_URL}/doc/doc"

# ---------------------------------------------------------------------------
# DOGE.gov
# ---------------------------------------------------------------------------
DOGE_BASE_URL = "https://api.doge.gov"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "raw")
PROCESSED_DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "processed")
OUTPUT_DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "outputs")
