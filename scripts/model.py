# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""
Train all three models: naive baseline, classical ML, and deep learning.

Usage:
    python scripts/model.py
"""

import subprocess
import sys


def main():
    scripts = [
        "scripts/naive_baseline.py",
        "scripts/classical.py",
        "scripts/deep_learning.py",
    ]
    for script in scripts:
        print(f"\n{'=' * 60}")
        print(f"  Training: {script}")
        print(f"{'=' * 60}\n")
        subprocess.check_call([sys.executable, script])


if __name__ == "__main__":
    main()
