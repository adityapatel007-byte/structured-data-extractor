"""Thin wrapper around src.eval.cli so `python scripts/run_eval.py ...` works.

Prefer this entry point in docs — it's discoverable from the repo root.
Adds the repo root to sys.path so `from src.eval.cli import main` resolves
when run directly (rather than as a module).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.eval.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
