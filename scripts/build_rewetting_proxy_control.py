"""Build a transparent rewetting-capacity proxy from frozen SC2 peat release.

This utility is intentionally downstream of SC2 and does not alter the scientific
engine. It applies a user-specified national drained-grassland-peat fraction to
SC2 released PEAT hectares only and writes the explicit ED-level control required
by SC3.

The default central fraction is 105,000 / 335,000 = 0.3134328358, based on the
midpoint of the 90,000-120,000 ha drained grassland peat range discussed by
Tuohy et al. (2023). Because no validated national ED-level drainage-status map
is currently available, this output is a transparent proxy/sensitivity control,
not parcel-level evidence. Rewetting results should therefore be interpreted
separately from productive SC3 transformability.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

DEFAULT_DRAINED_HA = 105_000.0
DEFAULT_GRASSLAND_PEAT_HA = 335_000.0
VERSION = "SC3_REWETTING_PROXY_CENTRAL_V1"
EVIDENCE = (
    "Proxy control: midpoint 105000 ha of the 90000-120000 ha drained grassland "
    "peat range reported by Tuohy et al. (2023), divided by 335000 ha mapped "
    "grassland peat, applied uniformly to frozen SC2 released PEAT hectares. "
    "No ED-level drainage-status map is implied."
)


def build_proxy(
    sc2: pd.DataFrame,
    *,
    drained_ha: float,
    grassland_peat_ha: float,
    version: str,
) -> pd.DataFrame:
    required = {"CSOED", "COLM_RELEASED_PEAT_HA"}
    missing = sorted(required - set(sc2.columns))
    if missing:
        raise ValueError(f"SC2 input missing columns: {missing}")
    if drained_ha < 0 or grassland_peat_ha <= 0:
        raise ValueError("drained_ha must be non-negative and grassland_peat_ha positive")

    share = min(max(float(drained_ha) / float(grassland_peat_ha), 0.0), 1.0)
    peat = pd.to_numeric(sc2["COLM_RELEASED_PEAT_HA"], errors="raise").clip(lower=0.0)
    out = pd.DataFrame(
        {
            "CSOED": sc2["CSOED"].astype(str),
            "REWETTING_CAPACITY_PEAT_HA": peat * share,
            "CAPACITY_VERSION": str(version),
            "EVIDENCE_NOTE": EVIDENCE,
        }
    )
    if out["CSOED"].duplicated().any():
        raise ValueError("SC2 input contains duplicate CSOED values")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sc2", required=True, help="Frozen sc2_ed_context.csv")
    parser.add_argument("--output", required=True, help="Output rewetting control CSV")
    parser.add_argument("--drained-ha", type=float, default=DEFAULT_DRAINED_HA)
    parser.add_argument("--grassland-peat-ha", type=float, default=DEFAULT_GRASSLAND_PEAT_HA)
    parser.add_argument("--version", default=VERSION)
    args = parser.parse_args()

    source = Path(args.sc2)
    output = Path(args.output)
    frame = pd.read_csv(source)
    control = build_proxy(
        frame,
        drained_ha=args.drained_ha,
        grassland_peat_ha=args.grassland_peat_ha,
        version=args.version,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    control.to_csv(output, index=False)
    share = float(args.drained_ha) / float(args.grassland_peat_ha)
    print(f"Wrote {output} with drained-share proxy {share:.6f} across {len(control):,} EDs")


if __name__ == "__main__":
    main()
