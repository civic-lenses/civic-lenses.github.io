---
name: Audit Checklist
description: |
  Reads the repo and intelligently evaluates which requirements checklist
  items are satisfied. Updates REQUIREMENTS_CHECKLIST.md with current
  status and regenerates the live HTML dashboard. Opens a PR with changes.
  Human reviews and merges.

strict: false

engine:
  id: copilot
  model: claude-sonnet-4

on:
  schedule:
    - cron: 'daily around 6am utc'
  workflow_dispatch:
  push:
    branches: [main]
    paths:
      - "scripts/**"
      - "config.py"
      - "requirements.txt"
      - "README.md"
      - "docs/**"
      - "app/**"
      - "notebooks/**"
      - "models/**"
      - ".github/REQUIREMENTS_CHECKLIST.md"

permissions: read-all

safe-outputs:
  create-pull-request:
    base-branch: main

tools:
  github:
    toolsets: [repos, pull_requests]
  edit:

timeout-minutes: 15
---

# Audit Checklist

You are an auditor for an AIPI 540 course project called Civic Lenses. Your job is to read the repository and determine which requirements checklist items are currently satisfied, then update the checklist file to reflect reality.

## Step 1: Read current state

Read these files from the repository:

1. `.github/REQUIREMENTS_CHECKLIST.md` (the checklist to update)
2. `README.md` (project documentation)
3. `config.py` (project configuration)
4. `requirements.txt` (dependencies)

List all files in `scripts/`, `models/`, `notebooks/`, `docs/`, `app/`, and `data/` directories.

Read the contents of every `.py` file in `scripts/`.

Check recent git history: the last 20 commits on `main`, and all merged PRs.

## Step 2: Evaluate each item

Work through the checklist section by section. For each item, decide: **satisfied**, **not satisfied**, or **cannot determine** (for items that require running code or external access).

### Modeling (M1-M7)

- **M1 Naive baseline**: Look for a script that implements a non-personalized baseline model (e.g. popularity ranking, majority class, mean predictor). The model must produce recommendations or predictions without learning from individual user data.
- **M2 Classical ML model**: Look for a script that implements a non-deep-learning ML model (e.g. TF-IDF, logistic regression, random forest, SVM). Must use learned features, not just heuristics.
- **M3 Deep learning model**: Look for a script that implements a neural network model (e.g. embeddings, transformer, LSTM, MLP with multiple layers). Must use PyTorch, TensorFlow, or similar.
- **M4 All three documented in README**: Check if README describes all three models with file locations.
- **M5 Rationale in report**: Cannot determine (report is external). Leave unchanged.
- **M6 Final model identified**: Check README or code for a clearly designated final/production model.
- **M7 Model artifacts**: Check if `models/` contains saved model files, or if code has clear save/load logic that would produce them.

### Experimentation (EX1-EX6)

Look for experimental code: alpha sensitivity analysis, ablation studies, hyperparameter sweeps, A/B comparisons between models. Check if results are printed, logged, or saved. EX1-EX6 relate to documentation quality that may not be fully determinable from code alone. Mark satisfied only if code clearly implements and reports an experiment.

### Interactive Application (APP1-APP5)

- **APP1**: Check if `docs/` or `app/` contains frontend code (HTML/JS/CSS) or if there's a Streamlit/Gradio/Flask app.
- **APP2**: Evaluate if the app has styled UI beyond a bare default template.
- **APP3-APP5**: Check README for a deployment URL. Cannot verify if the URL is live.

### Written Report (R01-R17)

Cannot determine from code. Leave unchanged unless a report file exists in the repo.

### In-Class Pitch (P1-P5)

Cannot determine from code. Leave unchanged.

### Repo Structure

Check each expected file/directory. The checklist may use template names from the course starter. Apply flexible matching:

- `setup.py`: any setup or installation script. `requirements.txt` + documented setup instructions in README can satisfy this.
- `main.py`: any entry point. A frontend in `docs/` or `app/`, or a clear CLI entry point counts.
- `scripts/make_dataset.py`: exact or equivalent data acquisition script.
- `scripts/build_features.py`: any feature engineering or preprocessing script (e.g. `preprocess.py`).
- `scripts/model.py`: any model training script(s). Multiple model files (e.g. `naive_baseline.py`, `classical.py`) collectively satisfy this.
- `models/`: directory exists.
- `data/raw/`, `data/processed/`, `data/outputs/`: directories exist.
- `notebooks/`: directory exists with at least one notebook for REPO1.
- `.gitignore`: file exists and covers `.env`.

### Code Quality (CQ1-CQ6)

- **CQ1 Modularized**: Check that all `.py` files use classes or functions, not loose procedural code.
- **CQ2 __main__ guards**: Check that executable code is inside `if __name__ == "__main__"` blocks.
- **CQ3 Descriptive names**: Skim variable and function names. Satisfied unless names are cryptic (single letters, abbreviations without context).
- **CQ4 Docstrings**: Check that public classes and functions have docstrings.
- **CQ5 AI attribution**: Check that `.py` files have an AI attribution comment (e.g. `# AI-assisted`).
- **CQ6 External attribution**: Check for external library attribution where needed.

### Git Best Practices (GIT1-GIT7)

- **GIT1 Feature branches**: Check git history for branch-based development.
- **GIT2 PR template**: Check if `.github/PULL_REQUEST_TEMPLATE/` exists with a template.
- **GIT3 PRs only**: Check if recent commits to main come via merge commits (PRs).
- **GIT4 PR summaries**: Check if merged PRs have summary sections (CI enforces this).
- **GIT5 Substantive reviews**: Check if merged PRs have review comments. Mark satisfied only if evidence is clear.
- **GIT6 .env not committed**: Check `.gitignore` includes `.env`. Check git history for any `.env` commits.
- **GIT7 No large files**: Cannot fully verify but check `.gitignore` for data/model exclusions.

### Project Novelty (NOV1-NOV2)

Check README and code for novelty claims. A recommender system for federal spending data with custom scoring is likely novel (NOV1). Mark if clearly stated.

### Pre-Submission (FS1-FS9)

These require running code. Leave unchanged.

## Step 3: Update the checklist

Edit `.github/REQUIREMENTS_CHECKLIST.md`:

1. For table-format items (M1-M7): change `⬜` to `✅` for satisfied items. Fill in the `Location` column with the actual file path(s).
2. For list-format items: change `[ ]` to `[x]` for satisfied items.
3. For items you marked "cannot determine": leave unchanged.
4. Never mark an item as unsatisfied if it was already marked satisfied (`✅` or `[x]`). Existing checkmarks represent human judgment that you should not override.
5. Update the **Status Summary** table at the bottom with correct counts and percentages.
6. Update the `Last updated` date to today's date.

**Important**: The repo structure section lists template filenames from the course. If the project uses different but equivalent filenames, note the actual filename in the Location column or inline, and mark the item satisfied.

## Step 4: Regenerate the HTML dashboard

Run `python3 scripts/generate_checklist.py` to regenerate `docs/checklist/index.html` from the updated markdown.

## Step 5: Open a PR

If any items changed status, open a pull request:

**Branch**: `audit/checklist-{today's date as YYYY-MM-DD}`

**Title**: `[Audit]: Update checklist — {N} items verified`

**Body**:

```
## Summary

Automated checklist audit based on current repo state.

### Newly satisfied
| Item | Evidence |
|------|----------|
| {ID} | {brief reason} |

### Could not determine
| Item | Reason |
|------|--------|
| {ID} | {why} |

### Repo structure mismatches
| Expected | Actual | Note |
|----------|--------|------|
| {template name} | {real file} | {explanation} |
```

If nothing changed, do not open a PR.
