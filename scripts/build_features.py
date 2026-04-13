# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""
Build features: preprocess raw data into unified contracts dataset.

This is a wrapper for backwards compatibility. The actual pipeline
is in scripts/preprocess.py.

Usage:
    python scripts/build_features.py
"""

from scripts.preprocess import main

if __name__ == "__main__":
    main()
