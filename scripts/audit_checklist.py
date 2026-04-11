# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""Deterministic evidence collector for checklist auditing.

Scans the repo for file existence, code patterns, git history, and
other mechanically verifiable signals. Writes a JSON evidence file
that the AI audit workflow uses to make judgment calls.

Output: .github/checklist-evidence.json
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
EVIDENCE_PATH = ROOT / ".github" / "checklist-evidence.json"


def _run(cmd: str) -> str:
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=ROOT
    )
    return result.stdout.strip()


def _glob(pattern: str) -> list[str]:
    return sorted(str(p.relative_to(ROOT)) for p in ROOT.glob(pattern))


def _file_exists(path: str) -> bool:
    return (ROOT / path).exists()


def _file_has_pattern(path: str, pattern: str) -> bool:
    try:
        return bool(re.search(pattern, (ROOT / path).read_text()))
    except (FileNotFoundError, UnicodeDecodeError):
        return False


def _all_py_files() -> list[str]:
    """All .py files excluding __init__.py (empty init files skew aggregates)."""
    return [
        f for f in _glob("scripts/*.py") + _glob("*.py")
        if not f.endswith("__init__.py")
    ]


def collect_evidence() -> dict:
    evidence: dict = {}

    # ------------------------------------------------------------------
    # File structure
    # ------------------------------------------------------------------
    evidence["files"] = {
        "scripts": _glob("scripts/*.py"),
        "models": _glob("models/**/*"),
        "notebooks": _glob("notebooks/**/*"),
        "docs": _glob("docs/**/*"),
        "app": _glob("app/**/*"),
        "data_raw": _glob("data/raw/**/*"),
        "data_processed": _glob("data/processed/**/*"),
        "data_outputs": _glob("data/outputs/**/*"),
        "top_level": _glob("*.py") + _glob("*.txt") + _glob("*.md"),
    }

    evidence["dirs_exist"] = {
        "models": _file_exists("models"),
        "notebooks": _file_exists("notebooks"),
        "data/raw": _file_exists("data/raw"),
        "data/processed": _file_exists("data/processed"),
        "data/outputs": _file_exists("data/outputs"),
    }

    evidence["key_files"] = {
        "readme": _file_exists("README.md"),
        "requirements": _file_exists("requirements.txt"),
        "gitignore": _file_exists(".gitignore"),
        "config": _file_exists("config.py"),
        "env_example": _file_exists(".env.example"),
        "setup_py": _file_exists("setup.py"),
        "main_py": _file_exists("main.py"),
        "make_dataset": _file_exists("scripts/make_dataset.py"),
        "build_features": _file_exists("scripts/build_features.py"),
        "preprocess": _file_exists("scripts/preprocess.py"),
        "model_py": _file_exists("scripts/model.py"),
        "naive_baseline": _file_exists("scripts/naive_baseline.py"),
        "classical": _file_exists("scripts/classical.py"),
        "pr_template": len(_glob(".github/PULL_REQUEST_TEMPLATE*/**/*")
                          + _glob(".github/pull_request_template*")) > 0,
    }

    # ------------------------------------------------------------------
    # Code quality signals (mechanical checks)
    # ------------------------------------------------------------------
    py_files = _all_py_files()
    cq: dict = {"files": {}}
    for f in py_files:
        info: dict = {}
        try:
            content = (ROOT / f).read_text()
        except (FileNotFoundError, UnicodeDecodeError):
            continue

        info["has_ai_attribution"] = bool(
            re.search(r"#\s*AI-assisted", content)
        )
        info["has_main_guard"] = bool(
            re.search(r'if\s+__name__\s*==\s*["\']__main__["\']', content)
        )
        info["has_classes_or_functions"] = bool(
            re.search(r"^(class |def )", content, re.MULTILINE)
        )
        # Loose executable code = statements at module level that aren't
        # imports, assignments, decorators, comments, or class/def/if blocks
        lines = content.splitlines()
        loose_executable = 0
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "import ", "from ",
                "@", "class ", "def ", "if __name__")):
                continue
            # Simple heuristic: function calls at module level
            if re.match(r"^[a-zA-Z_]\w*\(", stripped) and not stripped.startswith(("logger", "logging")):
                loose_executable += 1
        info["loose_executable_lines"] = loose_executable

        # Docstrings on public functions/classes
        public_defs = re.findall(
            r'^(class |def )([a-zA-Z][a-zA-Z0-9_]*)', content, re.MULTILINE
        )
        public_count = len([name for _, name in public_defs if not name.startswith("_")])
        docstring_count = len(re.findall(
            r'(class |def )\w+[^:]*:\s*\n\s+"""', content
        ))
        info["public_definitions"] = public_count
        info["definitions_with_docstrings"] = docstring_count

        cq["files"][f] = info

    # Aggregates
    all_files = cq["files"]
    # Config files (pure assignments) don't need classes/functions or main guards
    config_files = {"config.py"}
    cq["all_have_ai_attribution"] = all(
        v["has_ai_attribution"] for v in all_files.values()
    )
    cq["all_have_main_guard"] = all(
        v["has_main_guard"]
        for f, v in all_files.items()
        if f not in config_files
        and (v["loose_executable_lines"] > 0 or v["has_main_guard"])
    )
    cq["all_modularized"] = all(
        v["has_classes_or_functions"]
        for f, v in all_files.items()
        if f not in config_files
    )
    total_public = sum(v["public_definitions"] for v in all_files.values())
    total_documented = sum(v["definitions_with_docstrings"] for v in all_files.values())
    cq["docstring_coverage"] = (
        round(total_documented / total_public, 2) if total_public else 1.0
    )

    evidence["code_quality"] = cq

    # ------------------------------------------------------------------
    # Modeling signals
    # ------------------------------------------------------------------
    modeling: dict = {}

    # Naive baseline
    modeling["has_naive_baseline"] = any(
        _file_has_pattern(f, r"(baseline|naive|popularity|majority|mean.predict)")
        for f in py_files
    )

    # Classical ML
    modeling["has_classical_ml"] = any(
        _file_has_pattern(f, r"(TfidfVectorizer|LogisticRegression|RandomForest|SVM|cosine_similarity|sklearn)")
        for f in py_files
    )

    # Deep learning (check imports, not arbitrary string matches)
    modeling["has_deep_learning"] = any(
        _file_has_pattern(f, r"^(import torch|from torch|import tensorflow|from tensorflow|from keras|import keras)")
        for f in py_files
    )

    # Model artifacts
    model_files = [f for f in _glob("models/**/*") if not f.endswith(".gitkeep")]
    modeling["has_model_artifacts"] = len(model_files) > 0
    modeling["model_files"] = model_files

    # Experiment code
    modeling["has_experiment_code"] = any(
        _file_has_pattern(f, r"(sensitivity|ablation|alpha.*\[|hyperparameter|compare.*baseline)")
        for f in py_files
    )

    evidence["modeling"] = modeling

    # ------------------------------------------------------------------
    # Application signals
    # ------------------------------------------------------------------
    app: dict = {}
    app["has_frontend_html"] = any(
        f.endswith(".html") for f in
        _glob("docs/**/*") + _glob("app/**/*")
    )
    app["has_frontend_js"] = any(
        f.endswith(".js") for f in
        _glob("docs/**/*") + _glob("app/**/*")
    )
    app["has_frontend_css"] = any(
        f.endswith(".css") for f in
        _glob("docs/**/*") + _glob("app/**/*")
    )
    app["has_streamlit_or_gradio"] = any(
        _file_has_pattern(f, r"(streamlit|gradio|flask|FastAPI)")
        for f in py_files
    )

    # Check README for deployment URL
    readme_text = ""
    try:
        readme_text = (ROOT / "README.md").read_text()
    except FileNotFoundError:
        pass
    app["readme_has_url"] = bool(
        re.search(r"https?://\S+\.(github\.io|herokuapp|streamlit|vercel|netlify|fly\.dev)", readme_text)
    )
    evidence["application"] = app

    # ------------------------------------------------------------------
    # Git signals
    # ------------------------------------------------------------------
    git: dict = {}
    git["recent_commits"] = _run("git log --oneline -20")
    git["merge_commits"] = _run(
        "git log --oneline --merges -10"
    )
    git["branches_used"] = _run(
        "git log --oneline --all --decorate -30"
    )
    git["merged_prs"] = _run(
        "gh pr list --state merged --limit 10 --json number,title,reviews "
        "--jq '.[] | \"#\\(.number) \\(.title) reviews=\\(.reviews | length)\"'"
    )
    git["gitignore_has_env"] = _file_has_pattern(".gitignore", r"\.env")
    git["gitignore_has_data"] = _file_has_pattern(".gitignore", r"data/")
    git["gitignore_has_models"] = _file_has_pattern(".gitignore", r"models/")
    git["env_in_history"] = bool(_run("git log --all --diff-filter=A --name-only -- '*.env' '.env'"))

    evidence["git"] = git

    # ------------------------------------------------------------------
    # README signals
    # ------------------------------------------------------------------
    readme: dict = {}
    readme["mentions_naive_baseline"] = bool(
        re.search(r"(naive|baseline|popularity)", readme_text, re.IGNORECASE)
    )
    readme["mentions_classical"] = bool(
        re.search(r"(classical|TF-?IDF|cosine)", readme_text, re.IGNORECASE)
    )
    readme["mentions_deep_learning"] = bool(
        re.search(r"(deep.learn|neural|transformer|embedding|pytorch|tensorflow)", readme_text, re.IGNORECASE)
    )
    readme["has_setup_instructions"] = bool(
        re.search(r"(## Setup|## Install|pip install|requirements\.txt)", readme_text)
    )
    readme["has_model_file_locations"] = bool(
        re.search(r"(scripts/naive|scripts/classical|scripts/model|naive_baseline|classical\.py)", readme_text)
    )
    evidence["readme"] = readme

    # ------------------------------------------------------------------
    # Report / presentation
    # ------------------------------------------------------------------
    evidence["report"] = {
        "has_report_file": len(
            _glob("report.*") + _glob("docs/report.*") + _glob("*.pdf")
            + _glob("report/**/*")
        ) > 0,
        "has_slides": len(
            _glob("*.pptx") + _glob("slides.*") + _glob("pitch.*")
            + _glob("docs/slides.*") + _glob("presentation.*")
        ) > 0,
    }

    return evidence


def main() -> None:
    evidence = collect_evidence()
    EVIDENCE_PATH.write_text(
        json.dumps(evidence, indent=2, default=str) + "\n"
    )
    print(f"Evidence written to {EVIDENCE_PATH}")

    # Quick summary
    m = evidence["modeling"]
    cq = evidence["code_quality"]
    print(f"\nModeling:  naive={m['has_naive_baseline']}  classical={m['has_classical_ml']}  DL={m['has_deep_learning']}  artifacts={m['has_model_artifacts']}")
    print(f"Code:      AI-attr={cq['all_have_ai_attribution']}  main-guard={cq['all_have_main_guard']}  modular={cq['all_modularized']}  docstrings={cq['docstring_coverage']:.0%}")
    print(f"App:       html={evidence['application']['has_frontend_html']}  js={evidence['application']['has_frontend_js']}")
    print(f"Git:       .env-safe={evidence['git']['gitignore_has_env']}  no-env-history={not evidence['git']['env_in_history']}")


if __name__ == "__main__":
    main()
