---
name: Audit Checklist
description: |
  A script handles all mechanical checks and updates the checklist.
  This workflow handles only the judgment calls the script cannot make.

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

timeout-minutes: 10
---

# Audit Checklist

## Step 1: Check for existing audit PR

Check if there is already an open pull request with a branch starting with `audit/checklist-`. If one exists, stop. Do nothing.

## Step 2: Run the audit script

```
python3 scripts/audit_checklist.py
```

This updates `REQUIREMENTS_CHECKLIST.md` for all mechanically verifiable items and writes `.github/checklist-residual.json` listing items that need your judgment.

## Step 3: Evaluate residual items

Read `.github/checklist-residual.json`. For each item, read the referenced files and make a judgment call. Only mark an item satisfied if the evidence is clear. When uncertain, leave it unchecked.

For each item you evaluate, update `.github/REQUIREMENTS_CHECKLIST.md`:
- Table items: change `⬜` to `✅`, fill Location column
- List items: change `[ ]` to `[x]`
- Never uncheck items already checked

## Step 4: Regenerate dashboard

```
python3 scripts/generate_checklist.py
```

## Step 5: Open a PR

If any items changed (either from the script or your judgment), open a pull request.

**Branch**: `audit/checklist-{today's date as YYYY-MM-DD}`

**Title**: `[Audit]: Update checklist — {N} items verified`

**Body**:

```
## Summary

Automated checklist audit.

### Script verified
<list items the script checked off, from its stdout>

### Judgment calls
| Item | Decision | Reasoning |
|------|----------|-----------|
| {ID} | {satisfied / skipped} | {one sentence} |
```

If nothing changed, do not open a PR.
