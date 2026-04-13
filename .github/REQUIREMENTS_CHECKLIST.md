# Project Requirements Checklist

> Items marked 🤖 are verified automatically by CI on every push to `main`.
> Items marked 👤 require manual verification.
> Live view: **https://civic-lenses.github.io/checklist/** (auto-updated on merge to `main`)

---

## 1. Modeling — Three Required Approaches ⚠️

All three must be **implemented, evaluated, and findable** in the repo.

| # | Requirement | Location | Status |
|---|-------------|----------|--------|
| M1 | 🤖 Naive baseline (majority class / mean predictor) | `scripts/naive_baseline.py` | ✅ |
| M2 | 🤖 Classical (non-DL) ML model | `scripts/classical.py` | ✅ |
| M3 | 🤖 Deep learning model | `scripts/deep_learning.py` | ✅ |
| M4 | 👤 All three documented in README with file locations | `README.md` | ✅ |
| M5 | 👤 Rationale for each model written up in report | `docs/report.md` R07 | ✅ |
| M6 | 👤 Selected final model clearly identified (and justified) | `docs/report.md` R13-R14 | ✅ |
| M7 | 🤖 Trained model artifacts present or reproducible | `models/` | ✅ |

---

## 2. Required Experimentation ⚠️

At least **one focused experiment** must be implemented and written up.
The experiment must directly inform or validate a modeling/system decision.

- [x] **EX1** 👤 — Experiment is well-motivated: poses a specific question about your system
- [x] **EX2** 👤 — Experimental plan documented (hypothesis, method, metrics)
- [x] **EX3** 👤 — Results reported with numbers/visualizations
- [x] **EX4** 👤 — Interpretation written: what do the results tell you?
- [x] **EX5** 👤 — Experiment **directly informs a modeling or system design decision**
- [x] **EX6** 👤 — Actionable recommendations drawn from experiment

---

## 3. Interactive Application ⚠️

> **Zero-tolerance**: if the app doesn't run when graded → **0 for this section**.

- [x] **APP1** 🤖 — App exists and runs inference only (no training in app code)
- [x] **APP2** 👤 — Good UX — polished interface, not a bare Streamlit demo
- [x] **APP3** 👤 — Publicly accessible via internet (deployed URL)
- [x] **APP4** 👤 — Live for at least **one week** after submission date (due 2026-04-14)
- [x] **APP5** 🤖 — Deployment URL recorded in `README.md`

---

## 4. Written Report ⚠️

Format: NeurIPS/ICML-style paper, white paper, or technical report.

### Required Sections

- [x] **R01** 👤 — Problem Statement
- [x] **R02** 👤 — Data Sources (with provenance and access method)
- [x] **R03** 👤 — Related Work (review of prior literature)
- [x] **R04** 👤 — Evaluation Strategy & Metrics (with justification — *"this is critical"*)
- [x] **R05** 👤 — Modeling Approach → Data Processing Pipeline (with rationale per step)
- [x] **R06** 👤 — Hyperparameter Tuning Strategy
- [x] **R07** 👤 — Models Evaluated: Naive baseline, Classical ML, Deep learning (with rationale)
- [x] **R08** 👤 — Results: quantitative comparison across all models and metrics
- [x] **R09** 👤 — Results: visualizations and confusion matrices
- [x] **R10** 👤 — Error Analysis: **5 specific mispredictions** identified
- [x] **R11** 👤 — Error Analysis: root cause explained for each
- [x] **R12** 👤 — Error Analysis: **concrete, specific** mitigation strategies per case
- [x] **R13** 👤 — Experiment Write-Up (plan → results → interpretation → recommendations)
- [x] **R14** 👤 — Conclusions
- [x] **R15** 👤 — Future Work ("what would you do with another semester?")
- [x] **R16** 👤 — Commercial Viability Statement
- [x] **R17** 👤 — Ethics Statement

---

## 5. In-Class Pitch (5 min hard stop) ⚠️

- [ ] **P1** 👤 — Problem & Motivation slide(s)
- [ ] **P2** 👤 — Approach Overview slide(s)
- [ ] **P3** 👤 — Live Demo prepared and rehearsed
- [ ] **P4** 👤 — Results, Insights, or Key Findings slide(s)
- [ ] **P5** 👤 — Presentation stays within 5 minutes

---

## 6. Code & Repository

### Repo Structure

- [x] 🤖 `README.md` — project description, setup instructions
- [x] 🤖 `requirements.txt` — all dependencies pinned
- [x] 👤 `setup.py` — data acquisition / project setup pipeline
- [x] 👤 `main.py` — entry point / app launcher
- [x] 🤖 `scripts/make_dataset.py`
- [x] 🤖 `scripts/build_features.py`
- [x] 🤖 `scripts/model.py`
- [x] 🤖 `models/` — directory exists (artifacts generated after training)
- [x] 🤖 `data/raw/`, `data/processed/`, `data/outputs/`
- [x] 🤖 `notebooks/` — directory exists
- [x] 🤖 `.gitignore`
- [x] 👤 **REPO1** — At least one exploration notebook in `notebooks/`

### Code Quality ⚠️

- [x] **CQ1** 🤖 — All code modularized into classes/functions (no loose executable code)
- [x] **CQ2** 🤖 — No executable code outside `if __name__ == "__main__"` guards
- [ ] **CQ3** 👤 — Descriptive variable names throughout
- [ ] **CQ4** 👤 — Docstrings on all public functions
- [x] **CQ5** 🤖 — **AI usage attributed** at top of each file that used AI assistance (link to source required)
- [ ] **CQ6** 👤 — External code/libraries attributed at top of relevant files

> Note: Jupyter notebooks are allowed **only** in `notebooks/` and will not be graded directly.

### Git Best Practices ⚠️

- [x] **GIT1** 🤖 — Feature branches in use
- [x] **GIT2** 🤖 — PR template in `.github/PULL_REQUEST_TEMPLATE/`
- [ ] **GIT3** 👤 — All code merged via PRs (no direct commits to `main`) — enforced by branch protection
- [x] **GIT4** 🤖 — Every PR has a meaningful Summary — enforced by `PR Summary` CI check
- [ ] **GIT5** 👤 — Every PR reviewed with **substantive comments** — CODEOWNER approval required
- [x] **GIT6** 🤖 — `.env` is **never** committed (check `.gitignore`) — enforced by `Secret Scan` CI check
- [x] **GIT7** 🤖 — Large data files / model binaries are **never** committed (50 MB limit) — enforced by `Large File Scan` CI check

### Project Novelty (choose one)

- [x] **NOV1** 👤 — Working on a dataset/problem with no prior modeling approaches, OR
- [x] **NOV2** 👤 — Clearly explains what is new/novel vs. prior approaches (with citations), achieves near-SOTA or better explainability

---

## 7. Pre-Submission Checklist

Run through this before final submission:

- [ ] 👤 FS1: `python setup.py` runs end-to-end without errors
- [ ] 👤 FS2: `python scripts/build_features.py` produces processed data
- [ ] 👤 FS3: `python scripts/model.py` trains all three models and writes artifacts to `models/`
- [ ] 👤 FS4: App launches and is reachable in browser
- [ ] 👤 FS5: Live deployment URL is working and accessible without login
- [ ] 👤 FS6: README deployment link updated to actual URL
- [ ] 👤 FS7: Written report submitted in the required format
- [ ] 👤 FS8: Pitch deck/slides prepared
- [ ] 👤 FS9: Repo is public (or access granted to grader)

---

## Status Summary

| Category | Done | Total | % |
|----------|------|-------|---|
| Modeling | 7 | 7 | 100% |
| Experimentation | 6 | 6 | 100% |
| App | 5 | 5 | 100% |
| Written Report | 17 | 17 | 100% |
| Pitch | 0 | 5 | 0% |
| Repo / Code Quality | 17 | 18 | 94% |
| Git Best Practices | 5 | 7 | 71% |
| **Total** | **59** | **65** | **91%** |

> Last updated: 2026-04-13
