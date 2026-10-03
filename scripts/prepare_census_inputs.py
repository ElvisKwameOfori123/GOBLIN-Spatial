"""Stage 00: prepare the 2010 and 2020 CSO ED census inputs before the model runs.

Reconciles suppressed (blank) AVA42 livestock cells so that published ED values
are kept, State totals are reproduced exactly and 2020 county/region controls
hold within their publication rounding. Writes the prepared ED input files
and the audit tables in data/inputs/baseline/census_reconciliation/.

Usage
-----
    python scripts/prepare_census_inputs.py            # write prepared inputs
    python scripts/prepare_census_inputs.py --check    # verify committed files regenerate exactly
    python scripts/prepare_census_inputs.py --variant aim_first --output-root /tmp/variant_c

``--output-root`` writes the same relative file layout under another folder
(used for the robustness variants); the committed inputs are left untouched.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from goblin_spatial.preparation.census_suppression import PRIOR_SPECS  # noqa: E402
from goblin_spatial.preparation.stage00 import Stage00Paths, compare_outputs, prepare  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variant", default="joint", choices=sorted(PRIOR_SPECS))
    parser.add_argument("--check", action="store_true", help="fail if committed outputs differ")
    parser.add_argument("--output-root", type=Path, default=None)
    args = parser.parse_args()
    if args.check and (args.variant != "joint" or args.output_root):
        parser.error("--check verifies the committed joint outputs only")

    paths = Stage00Paths.default(ROOT)
    result = prepare(paths, variant=args.variant)

    differ, tolerant = [], []
    for name, payload in result.files.items():
        relative = Path(name).relative_to(ROOT)
        target = (args.output_root or ROOT) / relative
        if args.check:
            if not target.is_file():
                differ.append(f"{relative}: missing")
                continue
            verdict = compare_outputs(str(relative), target.read_bytes(), payload)
            if verdict is None:
                continue
            if verdict.startswith("WITHIN_TOLERANCE"):
                tolerant.append(f"{relative}: {verdict[len('WITHIN_TOLERANCE: '):]}")
            else:
                differ.append(f"{relative}: {verdict}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        print(f"wrote {target}")

    print("shrinkage lambda by year and variable:")
    print(result.shrinkage.to_string())
    print(result.closure[["YEAR", "VARIABLE", "STATE_TOTAL", "RECONCILED_TOTAL", "MODEL_UNIVERSE_TOTAL"]].to_string(index=False))
    if differ:
        print("Stage 00 outputs differ from the committed files:\n  " + "\n  ".join(differ))
        return 1
    if args.check:
        if tolerant:
            print("Monte Carlo diagnostics regenerate within tolerance (platform floating point):\n  " + "\n  ".join(tolerant))
        print("Stage 00 check passed: prepared census inputs and data-defining tables regenerate exactly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
