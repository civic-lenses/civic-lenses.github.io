# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""
Setup script: fetch raw data, preprocess, and train all models.

Usage:
    python setup.py
"""

import subprocess
import sys


def run(cmd: list[str]) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {' '.join(cmd)}")
    print(f"{'=' * 60}\n")
    subprocess.check_call(cmd, stdout=sys.stdout, stderr=sys.stderr)


if __name__ == "__main__":
    run([sys.executable, "scripts/make_dataset.py"])
    run([sys.executable, "scripts/preprocess.py"])
    run([sys.executable, "scripts/naive_baseline.py"])
    run([sys.executable, "scripts/classical.py"])
    run([sys.executable, "scripts/deep_learning.py"])
    print("\nSetup complete. Run 'python main.py' to launch the app.")
