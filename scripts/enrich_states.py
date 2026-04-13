# AI-assisted (Claude Code, claude.ai) — https://claude.ai
# External libraries: requests (HTTP client) — https://requests.readthedocs.io — Apache-2.0 license
"""
Enrich unified contracts with state-level geographic data.

Sources:
  - Leases: location field (CITY, ST format) -> 100% coverage
  - Grants: recipient name parsing (state agencies, universities) -> ~50-60%
  - Contracts: USAspending Place of Performance lookup by PIID -> ~60-70%

Usage:
    python scripts/enrich_states.py
"""

import logging
import os
import re
import sys
import time

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)

US_STATES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID",
    "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
    "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE",
    "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR",
    "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT",
    "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
    "DISTRICT OF COLUMBIA": "DC",
}

STATE_ABBREVS = set(US_STATES.values())

# Sorted longest-first so "NORTH CAROLINA" matches before "NORTH"
_STATE_NAMES_SORTED = sorted(US_STATES.keys(), key=len, reverse=True)
_STATE_NAMES_RE = "|".join(re.escape(s) for s in _STATE_NAMES_SORTED)
_STATE_NAME_PATTERN = re.compile(r"\b(" + _STATE_NAMES_RE + r")\b", re.IGNORECASE)

# City, ST pattern (like lease locations)
_CITY_STATE = re.compile(r",\s*([A-Z]{2})\s*$")

# Known institutions mapped to state
KNOWN_INSTITUTIONS = {
    "JOHNS HOPKINS": "MD", "HARVARD": "MA", "MIT ": "MA",
    "MASSACHUSETTS INSTITUTE OF TECHNOLOGY": "MA", "YALE": "CT",
    "PRINCETON": "NJ", "COLUMBIA UNIV": "NY", "CORNELL": "NY",
    "DUKE": "NC", "STANFORD": "CA", "CALTECH": "CA", "EMORY": "GA",
    "VANDERBILT": "TN", "TUFTS": "MA", "DARTMOUTH": "NH",
    "BROWN UNIVERSITY": "RI", "RICE UNIVERSITY": "TX", "BAYLOR": "TX",
    "GALLAUDET": "DC", "HOWARD UNIVERSITY": "DC", "GEORGETOWN": "DC",
    "GEORGE WASHINGTON UNIVERSITY": "DC", "AMERICAN UNIVERSITY": "DC",
    "FORDHAM": "NY", "NYU": "NY", "NEW YORK UNIVERSITY": "NY",
    "CUNY": "NY", "SUNY": "NY", "RUTGERS": "NJ", "DREXEL": "PA",
    "TEMPLE UNIVERSITY": "PA", "CARNEGIE MELLON": "PA",
    "CASE WESTERN": "OH", "OHIO STATE": "OH", "MAYO CLINIC": "MN",
    "NORTHWESTERN UNIVERSITY": "IL", "NOTRE DAME": "IN", "PURDUE": "IN",
    "TULANE": "LA", "WAKE FOREST": "NC", "RESEARCH TRIANGLE": "NC",
    "RTI INTERNATIONAL": "NC", "CLEMSON": "SC", "TUSKEGEE": "AL",
    "AUBURN": "AL", "SPELMAN": "GA", "MOREHOUSE": "GA",
    "GEORGIA TECH": "GA", "GEORGIA INSTITUTE OF TECHNOLOGY": "GA",
    "BRIGHAM YOUNG": "UT", "CREIGHTON": "NE", "BOSTON UNIVERSITY": "MA",
    "BOSTON COLLEGE": "MA", "UNIVERSITY OF CHICAGO": "IL",
    "UNIVERSITY OF PITTSBURGH": "PA", "UNIVERSITY OF ROCHESTER": "NY",
    "UNIVERSITY OF HOUSTON": "TX", "UNIVERSITY OF CINCINNATI": "OH",
    "UNIVERSITY OF MEMPHIS": "TN", "UNIVERSITY OF MIAMI": "FL",
    "UNIVERSITY OF SOUTHERN CALIFORNIA": "CA",
    "TEXAS SOUTHERN": "TX", "TEXAS A&M": "TX", "TEXAS A & M": "TX",
    "LOYOLA UNIVERSITY CHICAGO": "IL", "KENNESAW STATE": "GA",
    "JACKSON STATE": "MS", "MORGAN STATE": "MD", "BOWLING GREEN": "OH",
    "KENT STATE": "OH", "FLORIDA INTERNATIONAL": "FL",
    "FLORIDA ATLANTIC": "FL", "NORTH FLORIDA": "FL",
    "SOUTH FLORIDA": "FL", "CENTRAL FLORIDA": "FL",
    "CHILDREN'S HOSP OF PHILADELPHIA": "PA",
    "CHILDREN'S HOSPITAL OF PHILADELPHIA": "PA",
    "DUQUESNE": "PA", "VILLANOVA": "PA", "LEHIGH": "PA",
    "MARQUETTE": "WI", "DEPAUL": "IL", "LOYOLA": "IL",
    "XAVIER UNIVERSITY": "OH", "SETON HALL": "NJ",
    "GONZAGA": "WA", "PEPPERDINE": "CA", "CHAPMAN UNIVERSITY": "CA",
    "BOISE STATE": "ID", "WEBER STATE": "UT",
    "WICHITA STATE": "KS", "BALL STATE": "IN",
    "APPALACHIAN STATE": "NC", "EAST CAROLINA": "NC",
    "WESTERN CAROLINA": "NC", "UNC": "NC",
    "WINROCK INTERNATIONAL": "AR",
    "ENGENDER HEALTH": "NY", "AMIRA LEARNING": "CA",
}

# Major US cities to state
CITY_TO_STATE = {
    "PHILADELPHIA": "PA", "CHICAGO": "IL", "HOUSTON": "TX",
    "SAN FRANCISCO": "CA", "LOS ANGELES": "CA", "SAN DIEGO": "CA",
    "SAN ANTONIO": "TX", "DALLAS": "TX", "SEATTLE": "WA",
    "PORTLAND": "OR", "DENVER": "CO", "PHOENIX": "AZ", "BALTIMORE": "MD",
    "BOSTON": "MA", "DETROIT": "MI", "MINNEAPOLIS": "MN",
    "MILWAUKEE": "WI", "CLEVELAND": "OH", "CINCINNATI": "OH",
    "PITTSBURGH": "PA", "ATLANTA": "GA", "MIAMI": "FL",
    "NASHVILLE": "TN", "MEMPHIS": "TN", "CHARLOTTE": "NC",
    "RALEIGH": "NC", "DURHAM": "NC", "RICHMOND": "VA", "NEWARK": "NJ",
    "BUFFALO": "NY", "ROCHESTER": "NY", "SYRACUSE": "NY",
    "ALBANY": "NY", "HONOLULU": "HI", "ANCHORAGE": "AK",
    "ALBUQUERQUE": "NM", "CHAPEL HILL": "NC", "BIRMINGHAM": "AL",
    "BATON ROUGE": "LA", "NEW ORLEANS": "LA", "SALT LAKE": "UT",
    "KANSAS CITY": "MO", "ST LOUIS": "MO", "OKLAHOMA CITY": "OK",
    "SACRAMENTO": "CA", "NEW HAVEN": "CT", "HARTFORD": "CT",
    "TACOMA": "WA", "SPOKANE": "WA", "TUCSON": "AZ", "FRESNO": "CA",
    "OMAHA": "NE", "TULSA": "OK", "AURORA": "CO", "TAMPA": "FL",
    "JACKSONVILLE": "FL", "ORLANDO": "FL", "ST PAUL": "MN",
    "LEXINGTON": "KY", "LOUISVILLE": "KY", "COLUMBIA": "SC",
    "CHARLESTON": "SC", "SAVANNAH": "GA", "AUGUSTA": "GA",
    "LITTLE ROCK": "AR", "DES MOINES": "IA", "MADISON": "WI",
    "TRENTON": "NJ", "PROVIDENCE": "RI", "DOVER": "DE",
}

# Signals that the recipient is a US organization (used with state name match)
_US_ORG_SIGNALS = {
    "DEPARTMENT", "DEPT", "UNIVERSITY", "COLLEGE", "STATE", "COUNTY",
    "CITY", "SCHOOL", "DISTRICT", "BOARD", "COMMISSION", "DIVISION",
    "OFFICE", "FOUNDATION", "INSTITUTE", "CENTER", "COUNCIL",
    "ASSOCIATION", "MUSEUM", "HOSPITAL", "MEDICAL", "COMMUNITY",
    "PUBLIC", "TRIBAL", "TRIBE", "CONSERVATION", "ELECTRIC", "ENERGY",
    "TRANSIT", "HOUSING", "AUTHORITY", "INC", "LLC", "LABORATORY",
    "HUMANITIES", "HISTORICAL", "SOCIETY",
}


def extract_state_from_recipient(name: str) -> str | None:
    """Extract US state code from a grant recipient name."""
    if not name or not isinstance(name, str):
        return None
    upper_name = name.strip().upper()

    # 1. Trailing ", XX" (e.g., "City of Jacksonville, FL")
    match = _CITY_STATE.search(upper_name)
    if match and match.group(1) in STATE_ABBREVS:
        return match.group(1)

    # 2. State abbreviation prefix with agency word:
    #    "TX DEPT OF...", "TX ST DEPARTMENT OF..."
    match = re.match(
        r"^([A-Z]{2})\s+(ST\s+)?(DEPT?|DEPARTMENT|DIVISION|BOARD|OFFICE|CABINET|COMMISSION)",
        upper_name,
    )
    if match and match.group(1) in STATE_ABBREVS:
        return match.group(1)

    # 3. Abbreviation suffix after agency-like name:
    #    "HEALTH & HUMAN SVC COMMN TX"
    match = re.search(r"\s([A-Z]{2})$", upper_name)
    if match and match.group(1) in STATE_ABBREVS:
        agency_words = {"DEPT", "DEPARTMENT", "HEALTH", "COMMISSION", "COMMN",
                        "BOARD", "DIVISION", "CABINET", "SERVICES", "HUMAN",
                        "WELFARE", "PUBLIC"}
        if any(kw in upper_name for kw in agency_words):
            return match.group(1)

    # 4. "STATE OF <state name>"
    match = re.match(
        r"STATE\s+OF\s+(.+?)(?:\s+(?:DEPARTMENT|DEPT|ENERGY|OFFICE|BOARD|COMMISSION|UNIVERSITY)|$)",
        upper_name,
    )
    if match:
        state_part = match.group(1).strip().rstrip(" -")
        if state_part in US_STATES:
            return US_STATES[state_part]

    # 5. Inverted: ", <state name> ..." (e.g., "HEALTH, FLORIDA DEPARTMENT OF")
    match = re.search(r",\s*(" + _STATE_NAMES_RE + r")\b", upper_name)
    if match and match.group(1).upper() in US_STATES:
        return US_STATES[match.group(1).upper()]

    # 6. "<State Name> Department/State University..." at start
    match = re.match(
        r"(" + _STATE_NAMES_RE + r")\s+(DEPARTMENT|DEPT|DIVISION|BOARD|OFFICE|COMMISSION|STATE|COMPTROLLER|A\s*&\s*M|SOUTHERN)",
        upper_name,
    )
    if match:
        return US_STATES[match.group(1).upper()]

    # 7. "DEPARTMENT OF <topic> <STATE>"
    match = re.search(r"DEPARTMENT OF\s+\w+\s+(" + _STATE_NAMES_RE + r")\b", upper_name)
    if match:
        return US_STATES[match.group(1).upper()]

    # 8. "UNIVERSITY OF <state>"
    match = re.search(r"UNIVERSITY\s+OF\s+(" + _STATE_NAMES_RE + r")", upper_name)
    if match:
        return US_STATES[match.group(1).upper()]

    # 9. Known institutions (hard-coded universities, hospitals)
    for keyword, state in KNOWN_INSTITUTIONS.items():
        if keyword in upper_name:
            return state

    # 10. State name + US-org signal word co-occurring
    match = _STATE_NAME_PATTERN.search(upper_name)
    if match:
        state_name = match.group(1).upper()
        abbrev = US_STATES.get(state_name)
        if abbrev and any(sig in upper_name for sig in _US_ORG_SIGNALS):
            # Guard against "GEORGIA" matching the country
            if state_name == "GEORGIA" and any(kw in upper_name for kw in ("TBILISI", "CAUCASUS")):
                return None
            return abbrev

    # 11. City name in recipient (including inverted "City of X")
    for city, state in CITY_TO_STATE.items():
        if city in upper_name:
            return state

    # 12. "X, City of" or "X, County of" pattern
    match = re.match(r"^(.+?),\s*(?:CITY|COUNTY|TOWN|VILLAGE)\s+OF", upper_name)
    if match:
        place = match.group(1).strip()
        if place in CITY_TO_STATE:
            return CITY_TO_STATE[place]

    return None


def extract_state_from_lease_location(location: str) -> str | None:
    """Extract state from lease location (CITY, ST format)."""
    if not location or not isinstance(location, str):
        return None
    m = _CITY_STATE.search(location.strip())
    if m and m.group(1) in STATE_ABBREVS:
        return m.group(1)
    return None


def lookup_contract_states_batch(piids: list[str], batch_size: int = 50) -> dict[str, str]:
    """Lookup Place of Performance state for contracts via USAspending API."""
    url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
    result = {}
    total = len(piids)

    for i in range(0, total, batch_size):
        batch = piids[i:i + batch_size]
        payload = {
            "filters": {
                "award_ids": batch,
                "award_type_codes": ["A", "B", "C", "D"],
            },
            "fields": ["Award ID", "Place of Performance State Code"],
            "limit": batch_size,
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            for record in data.get("results", []):
                aid = record.get("Award ID", "")
                state = record.get("Place of Performance State Code", "")
                if aid and state and state in STATE_ABBREVS:
                    result[aid] = state
        except Exception as e:
            logger.warning("USAspending batch %d failed: %s", i, e)

        if (i // batch_size) % 10 == 0:
            logger.info("  USAspending: %d / %d PIIDs queried, %d states found",
                        min(i + batch_size, total), total, len(result))
        time.sleep(0.3)  # rate limit

    return result


def main():
    """Enrich unified_contracts.csv with state codes from leases, grants, and USAspending."""
    path = os.path.join(PROCESSED_DATA_DIR, "unified_contracts.csv")
    df = pd.read_csv(path)
    logger.info("Loaded %d items", len(df))

    df["state"] = None

    # --- Leases: use location field from raw data ---
    leases = pd.read_csv("data/raw/doge_cancelled_leases.csv")
    lease_locations = {}
    for _, row in leases.iterrows():
        loc = extract_state_from_lease_location(row.get("location", ""))
        if loc:
            # Match by description + agency since leases don't have contract_id in raw
            key = (str(row.get("agency", "")), str(row.get("description", ""))[:50])
            lease_locations[key] = loc

    lease_count = 0
    for idx, row in df[df["item_type"] == "lease"].iterrows():
        key = (str(row.get("agency", "")), str(row.get("description", ""))[:50])
        if key in lease_locations:
            df.at[idx, "state"] = lease_locations[key]
            lease_count += 1
    logger.info("Leases: %d states assigned", lease_count)

    # Also store full location for leases
    df["location"] = None
    lease_full = {}
    for _, row in leases.iterrows():
        key = (str(row.get("agency", "")), str(row.get("description", ""))[:50])
        lease_full[key] = row.get("location", "")
    for idx, row in df[df["item_type"] == "lease"].iterrows():
        key = (str(row.get("agency", "")), str(row.get("description", ""))[:50])
        if key in lease_full:
            df.at[idx, "location"] = lease_full[key]

    # --- Grants: parse recipient names ---
    grant_count = 0
    grant_mask = df["item_type"] == "grant"
    for idx, row in df[grant_mask].iterrows():
        state = extract_state_from_recipient(str(row.get("vendor_recipient", "")))
        if state:
            df.at[idx, "state"] = state
            grant_count += 1
    logger.info("Grants: %d / %d states extracted (%.0f%%)",
                grant_count, grant_mask.sum(),
                100 * grant_count / max(grant_mask.sum(), 1))

    # --- Contracts: USAspending Place of Performance ---
    contract_mask = (df["item_type"] == "contract") & df["state"].isna()
    # Get PIIDs (filter out "Multiple PIIDs" entries)
    piid_col = df.get("piid")
    if piid_col is None:
        # PIID might not be in unified CSV, load from raw
        raw = pd.read_csv("data/raw/doge_cancelled_contracts.csv")
        # Build contract_id -> piid mapping
        piid_map = {}
        for i, row in raw.iterrows():
            cid = f"DOGE_C_{i:06d}"
            piid = str(row.get("piid", ""))
            if piid and not piid.startswith("Multiple") and len(piid) >= 10:
                piid_map[cid] = piid

        piids_to_lookup = []
        cid_to_piid = {}
        for idx, row in df[contract_mask].iterrows():
            cid = row["contract_id"]
            if cid in piid_map:
                piid = piid_map[cid]
                piids_to_lookup.append(piid)
                cid_to_piid[piid] = idx

        logger.info("Contracts: looking up %d PIIDs on USAspending...", len(piids_to_lookup))
        if piids_to_lookup:
            piid_states = lookup_contract_states_batch(piids_to_lookup)
            contract_count = 0
            for piid, state in piid_states.items():
                if piid in cid_to_piid:
                    df.at[cid_to_piid[piid], "state"] = state
                    contract_count += 1
            logger.info("Contracts: %d / %d states found (%.0f%%)",
                        contract_count, len(piids_to_lookup),
                        100 * contract_count / max(len(piids_to_lookup), 1))

    # --- Summary ---
    total_with_state = df["state"].notna().sum()
    logger.info("Total: %d / %d items have state (%.0f%%)",
                total_with_state, len(df), 100 * total_with_state / len(df))

    by_type = df.groupby("item_type")["state"].apply(lambda x: x.notna().sum())
    type_totals = df["item_type"].value_counts()
    for t in by_type.index:
        logger.info("  %s: %d / %d (%.0f%%)", t, by_type[t], type_totals[t],
                     100 * by_type[t] / type_totals[t])

    # Top states
    print("\n=== Top 15 States by Contract Count ===")
    top = df["state"].value_counts().head(15)
    for state, count in top.items():
        total_val = df[df["state"] == state]["value"].sum()
        total_sav = df[df["state"] == state]["savings"].sum()
        print(f"  {state}: {count:,} items, ${total_val:,.0f} value, ${total_sav:,.0f} savings")

    # --- Unmatched analysis ---
    unmatched_grants = df[(df["item_type"] == "grant") & df["state"].isna()]
    if len(unmatched_grants) > 0:
        print(f"\n=== Unmatched Grants Analysis ({len(unmatched_grants)} items) ===")
        # By agency
        print("\nTop agencies with unmatched grants:")
        for agency, count in unmatched_grants["agency"].value_counts().head(10).items():
            print(f"  {agency}: {count}")
        # Sample unmatched recipients
        print("\nSample unmatched recipients:")
        for r in unmatched_grants["vendor_recipient"].dropna().sample(
            min(20, len(unmatched_grants)), random_state=42
        ):
            print(f"  {r[:80]}")

    unmatched_contracts = df[(df["item_type"] == "contract") & df["state"].isna()]
    if len(unmatched_contracts) > 0:
        print(f"\n=== Unmatched Contracts ({len(unmatched_contracts)} items) ===")
        print(f"These had no PIID or no USAspending match.")

    # Save
    df.to_csv(path, index=False)
    logger.info("Saved enriched data to %s", path)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    main()
