#!/usr/bin/env python
"""Audit the coherence of a built 2015-2025 historical baseline.

Run after `goblin-spatial build` and `scripts/build_catchment_baseline.py`.
Writes data/processed/validation/historical/baseline_coherence_audit.csv and
exits non-zero if any check fails.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from goblin_spatial.config import load_config
from goblin_spatial.validation.coherence import audit_historical_outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ireland_2015_2025.yaml")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    audit = audit_historical_outputs(cfg)
    out = cfg.project_root / "data/processed/validation/historical/baseline_coherence_audit.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(out, index=False)

    with pd.option_context("display.width", 200, "display.max_colwidth", 80):
        print(audit[["GROUP", "CHECK", "PASS", "DETAIL"]].to_string(index=False))
    passed = int(audit["PASS"].sum())
    print(f"\n{passed} / {len(audit)} coherence checks pass. Written: {out}")
    return 0 if passed == len(audit) else 1


if __name__ == "__main__":
    sys.exit(main())
