# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""
Setup script: fetch raw data, preprocess, and train all models.

Usage:
    python setup.py
"""

import subprocess
import sys


def run(cmd: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {cmd}")
    print(f"{'=' * 60}\n")
    subprocess.check_call(cmd.split(), stdout=sys.stdout, stderr=sys.stderr)


if __name__ == "__main__":
    run("python3 scripts/make_dataset.py")
    run("python3 scripts/preprocess.py")
    run("python3 scripts/naive_baseline.py")
    run("python3 scripts/classical.py")
    run("python3 scripts/deep_learning.py")
    print("\nSetup complete. Run 'python main.py' to launch the app.")
