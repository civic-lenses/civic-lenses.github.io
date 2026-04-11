# Project Requirements Checklist

> Mark items `[x]` as they are completed. Items marked ⚠️ are graded.
> Live view: **https://civic-lenses.github.io/checklist/** (auto-updated on merge to `main`)

---

## 1. Modeling — Three Required Approaches ⚠️

All three must be **implemented, evaluated, and findable** in the repo.

| # | Requirement | Location | Status |
|---|-------------|----------|--------|
| M1 | Naive baseline (majority class / mean predictor) | | ⬜ |
| M2 | Classical (non-DL) ML model | | ⬜ |
| M3 | Deep learning model | | ⬜ |
| M4 | All three documented in README with file locations | | ⬜ |
| M5 | Rationale for each model written up in report | | ⬜ |
| M6 | Selected final model clearly identified (and justified) | | ⬜ |
| M7 | Trained model artifacts present or reproducible | `models/` | ⬜ |

---

## 2. Required Experimentation ⚠️

At least **one focused experiment** must be implemented and written up.
The experiment must directly inform or validate a modeling/system decision.

- [ ] **EX1** — Experiment is well-motivated: poses a specific question about your system
- [ ] **EX2** — Experimental plan documented (hypothesis, method, metrics)
- [ ] **EX3** — Results reported with numbers/visualizations
- [ ] **EX4** — Interpretation written: what do the results tell you?
- [ ] **EX5** — Experiment **directly informs a modeling or system design decision**
- [ ] **EX6** — Actionable recommendations drawn from experiment

---

## 3. Interactive Application ⚠️

> **Zero-tolerance**: if the app doesn't run when graded → **0 for this section**.

- [ ] **APP1** — App exists and runs inference only (no training in app code)
- [ ] **APP2** — Good UX — polished interface, not a bare Streamlit demo
- [ ] **APP3** — Publicly accessible via internet (deployed URL)
- [ ] **APP4** — Live for at least **one week** after submission date (due 2026-04-14)
- [ ] **APP5** — Deployment URL recorded in `README.md`

---

## 4. Written Report ⚠️

Format: NeurIPS/ICML-style paper, white paper, or technical report.

### Required Sections

- [ ] **R01** — Problem Statement
- [ ] **R02** — Data Sources (with provenance and access method)
- [ ] **R03** — Related Work (review of prior literature)
- [ ] **R04** — Evaluation Strategy & Metrics (with justification — *"this is critical"*)
- [ ] **R05** — Modeling Approach → Data Processing Pipeline (with rationale per step)
- [ ] **R06** — Hyperparameter Tuning Strategy
- [ ] **R07** — Models Evaluated: Naive baseline, Classical ML, Deep learning (with rationale)
- [ ] **R08** — Results: quantitative comparison across all models and metrics
- [ ] **R09** — Results: visualizations and confusion matrices
- [ ] **R10** — Error Analysis: **5 specific mispredictions** identified
- [ ] **R11** — Error Analysis: root cause explained for each
- [ ] **R12** — Error Analysis: **concrete, specific** mitigation strategies per case
- [ ] **R13** — Experiment Write-Up (plan → results → interpretation → recommendations)
- [ ] **R14** — Conclusions
- [ ] **R15** — Future Work ("what would you do with another semester?")
- [ ] **R16** — Commercial Viability Statement
- [ ] **R17** — Ethics Statement

---

## 5. In-Class Pitch (5 min hard stop) ⚠️

- [ ] **P1** — Problem & Motivation slide(s)
- [ ] **P2** — Approach Overview slide(s)
- [ ] **P3** — Live Demo prepared and rehearsed
- [ ] **P4** — Results, Insights, or Key Findings slide(s)
- [ ] **P5** — Presentation stays within 5 minutes

---

## 6. Code & Repository

### Repo Structure

- [ ] `README.md` — project description, setup instructions
- [ ] `requirements.txt` — all dependencies pinned
- [ ] `setup.py` — data acquisition / project setup pipeline
- [ ] `main.py` — entry point / app launcher
- [ ] `scripts/make_dataset.py`
- [ ] `scripts/build_features.py`
- [ ] `scripts/model.py`
- [ ] `models/` — directory exists (artifacts generated after training)
- [ ] `data/raw/`, `data/processed/`, `data/outputs/`
- [ ] `notebooks/` — directory exists
- [ ] `.gitignore`
- [ ] **REPO1** — At least one exploration notebook in `notebooks/`

### Code Quality ⚠️

- [ ] **CQ1** — All code modularized into classes/functions (no loose executable code)
- [ ] **CQ2** — No executable code outside `if __name__ == "__main__"` guards
- [ ] **CQ3** — Descriptive variable names throughout
- [ ] **CQ4** — Docstrings on all public functions
- [ ] **CQ5** — **AI usage attributed** at top of each file that used AI assistance (link to source required)
- [ ] **CQ6** — External code/libraries attributed at top of relevant files

> Note: Jupyter notebooks are allowed **only** in `notebooks/` and will not be graded directly.

### Git Best Practices ⚠️

- [x] **GIT1** — Feature branches in use
- [x] **GIT2** — PR template in `.github/PULL_REQUEST_TEMPLATE/`
- [ ] **GIT3** — All code merged via PRs (no direct commits to `main`) — enforced by branch protection
- [ ] **GIT4** — Every PR has a meaningful Summary — enforced by `PR Summary` CI check
- [ ] **GIT5** — Every PR reviewed with **substantive comments** — CODEOWNER approval required
- [ ] **GIT6** — `.env` is **never** committed (check `.gitignore`) — enforced by `Secret Scan` CI check
- [ ] **GIT7** — Large data files / model binaries are **never** committed (50 MB limit) — enforced by `Large File Scan` CI check

### Project Novelty (choose one)

- [ ] **NOV1** — Working on a dataset/problem with no prior modeling approaches, OR
- [ ] **NOV2** — Clearly explains what is new/novel vs. prior approaches (with citations), achieves near-SOTA or better explainability

---

## 7. Pre-Submission Checklist

Run through this before final submission:

- [ ] `python setup.py` runs end-to-end without errors
- [ ] `python scripts/build_features.py` produces processed data
- [ ] `python scripts/model.py` trains all three models and writes artifacts to `models/`
- [ ] App launches and is reachable in browser
- [ ] Live deployment URL is working and accessible without login
- [ ] README deployment link updated to actual URL
- [ ] Written report submitted in the required format
- [ ] Pitch deck/slides prepared
- [ ] Repo is public (or access granted to grader)

---

## Status Summary

| Category | Done | Total | % |
|----------|------|-------|---|
| Modeling | 0 | 7 | 0% |
| Experimentation | 0 | 6 | 0% |
| App | 0 | 5 | 0% |
| Written Report | 0 | 17 | 0% |
| Pitch | 0 | 5 | 0% |
| Repo / Code Quality | 0 | 18 | 0% |
| Git Best Practices | 0 | 7 | 0% |
| **Total** | **0** | **65** | **0%** |

> Last updated: 2026-04-11
