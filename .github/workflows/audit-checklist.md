---
name: Audit Checklist
description: |
  Evaluates which requirements checklist items are satisfied by combining
  deterministic evidence (script) with AI judgment (this workflow).
  Updates REQUIREMENTS_CHECKLIST.md and opens a PR for human review.

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

You evaluate which project requirements are satisfied by reading pre-collected evidence and applying judgment where the evidence is ambiguous.

## Step 0: Check for existing audit PR

Before doing any work, check if there is already an open pull request with a branch starting with `audit/checklist-`. If one exists, skip the entire workflow and do nothing. This prevents duplicate PRs from piling up.

## Step 1: Collect evidence and read checklist

First, run the evidence collector script. Execute this shell command:

```
python3 scripts/audit_checklist.py
```

This produces `.github/checklist-evidence.json` with deterministic signals: file existence, code patterns, git history, README content.

Then read:

1. `.github/checklist-evidence.json` (the evidence you just generated)
2. `.github/REQUIREMENTS_CHECKLIST.md` (the checklist to update)

Trust the evidence signals. Do not re-check what the script already verified.

## Step 2: Apply rules for clear-cut items

These items map directly to evidence fields. Mark satisfied if the condition holds. Do not use judgment for these.

| Item | Condition |
|------|-----------|
| M1 | `modeling.has_naive_baseline == true` |
| M2 | `modeling.has_classical_ml == true` |
| M3 | `modeling.has_deep_learning == true` |
| M7 | `modeling.has_model_artifacts == true` |
| CQ1 | `code_quality.all_modularized == true` |
| CQ2 | `code_quality.all_have_main_guard == true` |
| CQ5 | `code_quality.all_have_ai_attribution == true` |
| GIT1 | `git.branches_used` shows multiple branches |
| GIT2 | `key_files.pr_template == true` |
| GIT6 | `git.gitignore_has_env == true` AND `git.env_in_history` is empty |
| GIT7 | `git.gitignore_has_data == true` AND `git.gitignore_has_models == true` |
| `README.md` | `key_files.readme == true` |
| `requirements.txt` | `key_files.requirements == true` |
| `.gitignore` | `key_files.gitignore == true` |
| `scripts/make_dataset.py` | `key_files.make_dataset == true` |
| `scripts/build_features.py` | `key_files.preprocess == true` (equivalent file) |
| `scripts/model.py` | `key_files.naive_baseline == true` OR `key_files.classical == true` (split across files) |
| `models/` | `dirs_exist.models == true` |
| `data/raw/`, `data/processed/`, `data/outputs/` | respective `dirs_exist` fields |
| `notebooks/` | `dirs_exist.notebooks == true` AND `files.notebooks` is non-empty |
| APP1 | `application.has_frontend_html == true` OR `application.has_streamlit_or_gradio == true` |

## Step 3: Apply judgment for ambiguous items

These items require reading code or interpreting context. Use the evidence as a starting point, then read specific files if needed.

- **M4** (all three documented in README): Check `readme.mentions_naive_baseline`, `readme.mentions_classical`, `readme.mentions_deep_learning`, and `readme.has_model_file_locations`. Only mark satisfied if all implemented models are documented with file locations.
- **M6** (final model identified): Read README for an explicit statement about which model is the production/final model.
- **CQ3** (descriptive variable names): `code_quality.files` lists each file. If the script found no issues, mark satisfied. If you need to verify, spot-check one or two files.
- **CQ4** (docstrings): Check `code_quality.docstring_coverage`. Mark satisfied if coverage is above 0.7 (70% of public definitions have docstrings).
- **CQ6** (external attribution): Skim files for external code usage without attribution.
- **GIT3** (PRs only): Check if `git.merge_commits` shows that recent history uses merge commits. A single direct commit among many PRs is acceptable.
- **GIT4** (PR summaries): Check `git.merged_prs`. Mark satisfied if the CI check exists (it does: `pr-checks.yml` enforces this).
- **GIT5** (substantive reviews): Check `git.merged_prs` for review counts. Mark satisfied only if most merged PRs show `reviews > 0`.
- **APP2** (polished UX): Only if APP1 is satisfied. Read the HTML/CSS/JS files and judge whether it goes beyond a bare template.
- **APP5** (deployment URL in README): Check `application.readme_has_url`.
- **EX1-EX6** (experimentation): Check `modeling.has_experiment_code`. If true, read the experiment code and assess whether it poses a question, has a plan, reports results, and draws conclusions. Mark individual EX items based on what you find.
- **NOV1/NOV2** (novelty): Read README for novelty claims. A recommender for federal spending with custom scoring is likely novel (NOV1).
- **`setup.py`**: Check `key_files.setup_py`. If false, check whether `requirements.txt` + README setup instructions serve the same purpose. Mark satisfied with a note if so.
- **`main.py`**: Check `key_files.main_py`. If false, check whether frontend code or a CLI entry point exists. Mark satisfied with a note if so.
- **REPO1** (exploration notebook): Only satisfied if `files.notebooks` contains at least one `.ipynb` file.

## Step 4: Items to skip

Leave these unchanged (cannot verify from repo alone):

- **M5** (rationale in report): requires reading the report
- **R01-R17** (written report sections): unless a report file is in the repo
- **P1-P5** (in-class pitch): unless slides are in the repo
- **FS1-FS9** (pre-submission): requires running code
- **APP3-APP4** (publicly accessible, live for a week): requires external verification

## Step 5: Update the checklist

Edit `.github/REQUIREMENTS_CHECKLIST.md`:

1. For table-format items (M1-M7): change `⬜` to `✅` for satisfied items. Fill in the `Location` column with the actual file path(s).
2. For list-format items: change `[ ]` to `[x]` for satisfied items.
3. For items where the checklist uses a template filename but the project uses an equivalent: add a parenthetical note with the actual filename, e.g. `scripts/build_features.py` becomes `scripts/build_features.py (→ preprocess.py)`.
4. Never uncheck an item that was already checked. Existing checkmarks represent human judgment.
5. Update the **Status Summary** table at the bottom with correct counts and percentages.
6. Update the `Last updated` date to today's date.

## Step 6: Regenerate the HTML dashboard

Run `python3 scripts/generate_checklist.py` to update `docs/checklist/index.html`.

## Step 7: Open a PR

If any items changed status, open a pull request.

**Branch**: `audit/checklist-{today's date as YYYY-MM-DD}`

**Title**: `[Audit]: Update checklist — {N} items verified`

**Body**:

```
## Summary

Automated checklist audit based on current repo state.

### Newly satisfied
| Item | Evidence |
|------|----------|
| {ID} | {brief reason — cite the evidence field or file} |

### Judgment calls
| Item | Decision | Reasoning |
|------|----------|-----------|
| {ID} | {satisfied / not satisfied} | {one sentence} |

### Could not determine
| Item | Reason |
|------|--------|
| {ID} | {why} |
```

If nothing changed, do not open a PR.
