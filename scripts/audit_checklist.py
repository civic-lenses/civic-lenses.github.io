# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""Deterministic checklist auditor.

Scans the repo, evaluates all mechanically verifiable checklist items,
and updates REQUIREMENTS_CHECKLIST.md directly. Writes a residual file
listing only the items that require human or AI judgment.

Outputs:
  - .github/REQUIREMENTS_CHECKLIST.md  (updated in place)
  - .github/checklist-residual.json    (items needing judgment)
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
CHECKLIST_PATH = ROOT / ".github" / "REQUIREMENTS_CHECKLIST.md"
RESIDUAL_PATH = ROOT / ".github" / "checklist-residual.json"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _run(cmd: str) -> str:
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=ROOT
    )
    return result.stdout.strip()


def _glob(pattern: str) -> list[str]:
    return sorted(str(p.relative_to(ROOT)) for p in ROOT.glob(pattern))


def _exists(path: str) -> bool:
    return (ROOT / path).exists()


def _has_pattern(path: str, pattern: str, flags: int = 0) -> bool:
    try:
        return bool(re.search(pattern, (ROOT / path).read_text(), flags))
    except (FileNotFoundError, UnicodeDecodeError):
        return False


def _py_files() -> list[str]:
    return [
        f for f in _glob("scripts/*.py") + _glob("*.py")
        if not f.endswith("__init__.py")
    ]


# ------------------------------------------------------------------
# Evidence collection (compact)
# ------------------------------------------------------------------

def collect() -> dict:
    py = _py_files()
    readme = (ROOT / "README.md").read_text() if _exists("README.md") else ""

    # Code quality per file
    config_files = {"config.py"}
    cq_all_attr = True
    cq_all_guard = True
    cq_all_mod = True
    total_pub, total_doc = 0, 0

    for f in py:
        try:
            content = (ROOT / f).read_text()
        except (FileNotFoundError, UnicodeDecodeError):
            continue

        has_attr = bool(re.search(r"#\s*AI-assisted", content))
        has_guard = bool(re.search(r'if\s+__name__\s*==\s*["\']__main__["\']', content))
        has_mod = bool(re.search(r"^(class |def )", content, re.MULTILINE))

        if not has_attr:
            cq_all_attr = False
        if f not in config_files and not has_mod:
            cq_all_mod = False
        if f not in config_files and not has_guard:
            # Only flag if file has executable code
            loose = sum(
                1 for line in content.splitlines()
                if line.strip()
                and not line.strip().startswith(("#", "import ", "from ", "@", "class ", "def ", "if __name__"))
                and re.match(r"^[a-zA-Z_]\w*\(", line.strip())
                and not line.strip().startswith(("logger", "logging"))
            )
            if loose > 0 or has_guard:
                cq_all_guard = False

        pub = len([
            n for _, n in re.findall(r'^(class |def )([a-zA-Z]\w*)', content, re.MULTILINE)
            if not n.startswith("_")
        ])
        doc = len(re.findall(r'(class |def )\w+[^:]*:\s*\n\s+"""', content))
        total_pub += pub
        total_doc += doc

    docstring_cov = round(total_doc / total_pub, 2) if total_pub else 1.0

    notebooks = [f for f in _glob("notebooks/**/*") if f.endswith(".ipynb")]
    model_files = [f for f in _glob("models/**/*") if not f.endswith(".gitkeep")]

    has_dl = any(_has_pattern(f, r"^(import torch|from torch|import tensorflow|from tensorflow|from keras|import keras)", re.MULTILINE) for f in py)
    has_experiment = any(_has_pattern(f, r"(sensitivity|ablation|alpha.*\[|hyperparameter|compare.*baseline)") for f in py)

    merged_prs = _run("gh pr list --state merged --limit 10 --json number,title,reviews "
                       "--jq '.[] | \"#\\(.number) reviews=\\(.reviews | length)\"'")

    return {
        "M1": any(_has_pattern(f, r"(baseline|naive|popularity|majority|mean.predict)") for f in py),
        "M2": any(_has_pattern(f, r"(TfidfVectorizer|LogisticRegression|RandomForest|SVM|cosine_similarity|sklearn)") for f in py),
        "M3": has_dl,
        "M7": len(model_files) > 0,
        "CQ1": cq_all_mod,
        "CQ2": cq_all_guard,
        "CQ4_coverage": docstring_cov,
        "CQ5": cq_all_attr,
        "GIT1": bool(re.search(r"origin/", _run("git log --oneline --all --decorate -20"))),
        "GIT2": len(_glob(".github/PULL_REQUEST_TEMPLATE*/**/*") + _glob(".github/pull_request_template*")) > 0,
        "GIT6": _has_pattern(".gitignore", r"\.env") and not bool(_run("git log --all --diff-filter=A --name-only -- '*.env' '.env'")),
        "GIT7": _has_pattern(".gitignore", r"data/") and _has_pattern(".gitignore", r"models/"),
        "APP1": any(f.endswith(".html") for f in _glob("docs/**/*") + _glob("app/**/*"))
                or any(_has_pattern(f, r"(streamlit|gradio|flask|FastAPI)") for f in py),
        "APP5": bool(re.search(r"https?://\S+\.(github\.io|herokuapp|streamlit|vercel|netlify|fly\.dev)", readme)),
        "readme": _exists("README.md"),
        "requirements": _exists("requirements.txt"),
        "gitignore": _exists(".gitignore"),
        "make_dataset": _exists("scripts/make_dataset.py"),
        "build_features": _exists("scripts/preprocess.py"),  # equivalent
        "model_py": _exists("scripts/naive_baseline.py") or _exists("scripts/classical.py"),  # split
        "models_dir": _exists("models"),
        "data_dirs": _exists("data/raw") and _exists("data/processed") and _exists("data/outputs"),
        "notebooks_with_content": len(notebooks) > 0,
        "notebooks_dir": _exists("notebooks"),
        "has_experiment": has_experiment,
        "readme_models_documented": (
            bool(re.search(r"(naive|baseline)", readme, re.I))
            and bool(re.search(r"(classical|TF-?IDF|cosine)", readme, re.I))
            and bool(re.search(r"(scripts/naive|scripts/classical|naive_baseline|classical\.py)", readme))
        ),
        "readme_dl_documented": bool(re.search(r"(deep.learn|neural|transformer|pytorch|tensorflow)", readme, re.I)),
        "merged_prs": merged_prs,
    }


# ------------------------------------------------------------------
# Checklist updater
# ------------------------------------------------------------------

# Rules: evidence key -> checklist item ID -> (satisfied, location/note)
RULES: list[tuple[str, str, str]] = [
    # Modeling
    ("M1", "M1", "scripts/naive_baseline.py"),
    ("M2", "M2", "scripts/classical.py"),
    ("M3", "M3", ""),
    ("M7", "M7", "models/"),
    # Code quality
    ("CQ1", "CQ1", ""),
    ("CQ2", "CQ2", ""),
    ("CQ5", "CQ5", ""),
    # Git
    ("GIT1", "GIT1", ""),
    ("GIT2", "GIT2", ".github/PULL_REQUEST_TEMPLATE/"),
    ("GIT6", "GIT6", ".gitignore"),
    ("GIT7", "GIT7", ".gitignore"),
    # App
    ("APP1", "APP1", "app/index.html"),
]

# Repo structure items (checklist text -> evidence key)
STRUCTURE_ITEMS: dict[str, str] = {
    "`README.md`": "readme",
    "`requirements.txt`": "requirements",
    "`.gitignore`": "gitignore",
    "`scripts/make_dataset.py`": "make_dataset",
    "`scripts/build_features.py`": "build_features",
    "`scripts/model.py`": "model_py",
    "`models/`": "models_dir",
    "`data/raw/`, `data/processed/`, `data/outputs/`": "data_dirs",
}


def update_checklist(evidence: dict) -> tuple[list[str], list[dict]]:
    """Update checklist markdown. Returns (changes_made, residual_items)."""
    text = CHECKLIST_PATH.read_text()
    changes: list[str] = []
    residual: list[dict] = []

    # --- Table-format items (M1-M7): ⬜ -> ✅ with location ---
    for ekey, item_id, location in RULES:
        if not evidence.get(ekey):
            continue
        # Match: | M1 | description | location | ⬜ |
        pattern = rf"(\|\s*{item_id}\s*\|[^|]+\|)[^|]*(\|\s*)⬜(\s*\|)"
        loc = f" `{location}` " if location else " "
        replacement = rf"\g<1>{loc}\g<2>✅\g<3>"
        new_text = re.sub(pattern, replacement, text)
        if new_text != text:
            changes.append(f"{item_id}: {location or 'verified'}")
            text = new_text

    # --- List-format items: [ ] -> [x] ---
    list_rules = {
        "CQ1": evidence.get("CQ1"),
        "CQ2": evidence.get("CQ2"),
        "CQ5": evidence.get("CQ5"),
        "GIT1": evidence.get("GIT1"),
        "GIT2": evidence.get("GIT2"),
        "GIT6": evidence.get("GIT6"),
        "GIT7": evidence.get("GIT7"),
        "APP1": evidence.get("APP1"),
        "APP5": evidence.get("APP5"),
    }
    for item_id, satisfied in list_rules.items():
        if not satisfied:
            continue
        pattern = rf"(- \[) (\] \*\*{item_id}\*\*)"
        replacement = r"\g<1>x\g<2>"
        new_text = re.sub(pattern, replacement, text)
        if new_text != text:
            changes.append(f"{item_id}")
            text = new_text

    # --- Repo structure plain checklist items ---
    for label, ekey in STRUCTURE_ITEMS.items():
        if not evidence.get(ekey):
            continue
        escaped = re.escape(label)
        pattern = rf"(- \[) (\] {escaped})"
        replacement = r"\g<1>x\g<2>"
        new_text = re.sub(pattern, replacement, text)
        if new_text != text:
            changes.append(f"repo: {label}")
            text = new_text

    # --- Items that need judgment (for AI workflow) ---
    judgment_items = [
        {"id": "M4", "question": "Are all implemented models documented in README with file locations?",
         "signal": f"baseline={evidence['readme_models_documented']}, dl={evidence['readme_dl_documented']}"},
        {"id": "M6", "question": "Is a final model clearly identified and justified?",
         "signal": "check README for explicit final model statement"},
        {"id": "CQ3", "question": "Are variable names descriptive throughout?",
         "signal": "spot-check scripts/*.py"},
        {"id": "CQ4", "question": f"Docstring coverage is {evidence['CQ4_coverage']:.0%}. Sufficient?",
         "signal": f"coverage={evidence['CQ4_coverage']}"},
        {"id": "CQ6", "question": "Is external code/library usage attributed?",
         "signal": "check for uncommented external code"},
        {"id": "GIT3", "question": "Are all commits merged via PRs (no direct pushes)?",
         "signal": "check merge commit ratio in git history"},
        {"id": "GIT4", "question": "Do all PRs have meaningful summaries?",
         "signal": "CI enforces this via pr-checks.yml"},
        {"id": "GIT5", "question": "Do PRs have substantive review comments?",
         "signal": evidence.get("merged_prs", "")},
        {"id": "APP2", "question": "Is the app UI polished beyond a bare template?",
         "signal": "read app/index.html, app/styles.css"},
        {"id": "NOV1", "question": "Is the project working on a novel dataset/problem?",
         "signal": "check README for novelty claims"},
        {"id": "REPO1", "question": "Is there an exploration notebook in notebooks/?",
         "signal": f"notebooks_exist={evidence['notebooks_with_content']}"},
    ]

    if evidence.get("has_experiment"):
        for ex_id in ["EX1", "EX2", "EX3", "EX4", "EX5", "EX6"]:
            judgment_items.append({
                "id": ex_id,
                "question": f"Does the experiment code satisfy {ex_id}?",
                "signal": "experiment code found, read for quality",
            })

    # Filter to items not already checked
    for item in judgment_items:
        item_id = item["id"]
        # Check if already marked done in table format
        if re.search(rf"\|\s*{item_id}\s*\|.*✅", text):
            continue
        # Check if already marked done in list format
        if re.search(rf"- \[x\] \*\*{item_id}\*\*", text):
            continue
        residual.append(item)

    # --- Update summary table ---
    text = _update_summary(text)

    # --- Update date ---
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    text = re.sub(r"Last updated: \d{4}-\d{2}-\d{2}", f"Last updated: {today}", text)

    CHECKLIST_PATH.write_text(text)
    return changes, residual


def _update_summary(text: str) -> str:
    """Recount checked items per section and update the summary table."""
    # Count by item ID prefixes rather than section boundaries
    sections = {
        "Modeling":           (["M"],    7),
        "Experimentation":    (["EX"],   6),
        "App":                (["APP"],  5),
        "Written Report":     (["R"],    17),
        "Pitch":              (["P"],    5),
        "Repo / Code Quality": (["CQ", "REPO", "NOV"], 18),  # includes repo structure plain items
        "Git Best Practices": (["GIT"],  7),
    }

    # Count checked table items (✅) and list items ([x]) with IDs
    checked_table = set(re.findall(r"\|\s*([A-Z]+\d+)\s*\|.*?✅", text))
    checked_list = set(re.findall(r"\[x\]\s*\*\*([A-Z]+\d+)\*\*", text))
    # Plain repo structure items (no ID, just [x])
    plain_checked = len(re.findall(r"- \[x\] `(?:README|requirements|\.gitignore|scripts/|models/|data/|notebooks/|setup|main)", text))

    counts: dict[str, int] = {}
    for label, (prefixes, _) in sections.items():
        count = sum(
            1 for item_id in (checked_table | checked_list)
            if any(item_id.startswith(p) for p in prefixes)
        )
        if label == "Repo / Code Quality":
            count += plain_checked
        counts[label] = count

    total_done = sum(counts.values())
    total_all = sum(t for _, t in sections.values())

    # Replace each row in the summary table
    for label, (_, total) in sections.items():
        done = counts.get(label, 0)
        pct = round(100 * done / total) if total else 0
        pattern = rf"(\| {re.escape(label)} \|)\s*\d+\s*\|\s*\d+\s*\|\s*\d+%\s*\|"
        replacement = rf"\g<1> {done} | {total} | {pct}% |"
        text = re.sub(pattern, replacement, text)

    # Total row
    total_pct = round(100 * total_done / total_all) if total_all else 0
    text = re.sub(
        r"(\| \*\*Total\*\* \|)\s*\*\*\d+\*\*\s*\|\s*\*\*\d+\*\*\s*\|\s*\*\*\d+%\*\*\s*\|",
        rf"\g<1> **{total_done}** | **{total_all}** | **{total_pct}%** |",
        text,
    )

    return text


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main() -> None:
    evidence = collect()
    changes, residual = update_checklist(evidence)

    RESIDUAL_PATH.write_text(json.dumps(residual, indent=2) + "\n")

    print(f"Updated {len(changes)} items in REQUIREMENTS_CHECKLIST.md")
    for c in changes:
        print(f"  ✓ {c}")
    print(f"\n{len(residual)} items need judgment (written to {RESIDUAL_PATH.name})")
    for r in residual:
        print(f"  ? {r['id']}: {r['question']}")


if __name__ == "__main__":
    main()
