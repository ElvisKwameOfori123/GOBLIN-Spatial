"""Frozen repository-contained land context for the principal 2020 scenario run.

The principal scenario runtime consumes one neutral ED-level control that carries
three distinct evidence layers: 08B agricultural capability, 08C mapped physical
soil and LPIS 2020 context.  The layers remain scientifically separate even
though they share one storage object.

Normal scenario execution never downloads parcels, soil packages or ED geometry.
Heavy source reconstruction is an explicit provenance workflow only.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd


LAND_CONTEXT_YEAR = 2020
LAND_CONTEXT_EXPECTED_EDS = 2857
LAND_CONTEXT_EXPECTED_COLUMNS = 40
LAND_CONTEXT_CANONICAL_SHA256 = (
    "6a94c125413260ed462c9d5430fe6d39be7df48d282734eea218351829aa6e5d"
)

LAND_CONTEXT_COLUMNS = (
    "CSOED",
    "SOIL_PROFILE_SOURCE",
    "SOIL_SOURCE_HOLDINGS",
    "SOIL_SOURCE_UAA_HA",
    "SOIL_USE_CLASS_1_SHARE",
    "SOIL_USE_CLASS_2_SHARE",
    "SOIL_USE_CLASS_3_SHARE",
    "SOIL_USE_CLASS_4_SHARE",
    "SOIL_USE_CLASS_5_SHARE",
    "SOIL_USE_CLASS_6_SHARE",
    "GOBLIN_SOIL_G1_SHARE",
    "GOBLIN_SOIL_G2_SHARE",
    "GOBLIN_SOIL_G3_SHARE",
    "FOREST_YC_WEIGHTED_MEAN",
    "IFS_PEAT_CUTOVER_UAA_SHARE",
    "IFS_MAP_DEEP_WELL_DRAINED_HA",
    "IFS_MAP_SHALLOW_WELL_DRAINED_HA",
    "IFS_MAP_POORLY_DRAINED_HA",
    "IFS_MAP_POORLY_DRAINED_PEATY_HA",
    "IFS_MAP_ALLUVIUM_HA",
    "IFS_MAP_PEAT_HA",
    "IFS_MAP_MISCELLANEOUS_HA",
    "LPIS_YEAR",
    "LPIS_CLAIMED_AG_HA",
    "LPIS_ELIGIBLE_AG_HA",
    "LPIS_SPATIAL_FOOTPRINT_HA",
    "LPIS_CLAIMED_GRASS_HA",
    "LPIS_ELIGIBLE_GRASS_HA",
    "LPIS_PERMANENT_PASTURE_HA",
    "LPIS_LOW_INPUT_GRASS_HA",
    "LPIS_TEMPORARY_GRASS_HA",
    "LPIS_HAY_MEADOW_HA",
    "LPIS_OTHER_GRASS_HA",
    "LPIS_COMMONAGE_GRASS_HA",
    "LPIS_ANC_GRASS_HA",
    "LPIS_ENV_SCHEME_GRASS_HA",
    "LPIS_ORGANIC_GRASS_HA",
    "LPIS_BOG_PEAT_CONTEXT_HA",
    "LPIS_HABITAT_CONTEXT_HA",
    "LPIS_FORESTRY_CONTEXT_HA",
)

CLASS_SHARE_COLUMNS = tuple(f"SOIL_USE_CLASS_{i}_SHARE" for i in range(1, 7))
GROUP_SHARE_COLUMNS = tuple(f"GOBLIN_SOIL_G{i}_SHARE" for i in range(1, 4))
PHYSICAL_AREA_COLUMNS = (
    "IFS_MAP_DEEP_WELL_DRAINED_HA",
    "IFS_MAP_SHALLOW_WELL_DRAINED_HA",
    "IFS_MAP_POORLY_DRAINED_HA",
    "IFS_MAP_POORLY_DRAINED_PEATY_HA",
    "IFS_MAP_ALLUVIUM_HA",
    "IFS_MAP_PEAT_HA",
    "IFS_MAP_MISCELLANEOUS_HA",
)
LPIS_GRASS_PARTITION_COLUMNS = (
    "LPIS_PERMANENT_PASTURE_HA",
    "LPIS_LOW_INPUT_GRASS_HA",
    "LPIS_TEMPORARY_GRASS_HA",
    "LPIS_HAY_MEADOW_HA",
    "LPIS_OTHER_GRASS_HA",
)


def _canonical_csoed(value: object) -> str:
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if "/" not in text:
        return text
    parts = [part.strip() for part in text.split("/") if part.strip()]
    return "/".join(parts)


def _reconstruct_sharded_csv(directory: Path) -> bytes:
    parts = sorted(directory.glob("part-*.csv"))
    if not parts:
        raise FileNotFoundError(f"no part-*.csv shards found in {directory}")

    header: bytes | None = None
    output = bytearray()
    for index, path in enumerate(parts):
        raw = path.read_bytes()
        first, sep, rest = raw.partition(b"\n")
        if not sep:
            raise ValueError(f"land-context shard has no header/data separator: {path}")
        if header is None:
            header = first.rstrip(b"\r")
            output.extend(header + b"\n")
        elif first.rstrip(b"\r") != header:
            raise ValueError(f"land-context shard header mismatch: {path}")
        output.extend(rest)
        if index < len(parts) - 1 and output and not output.endswith(b"\n"):
            output.extend(b"\n")
    return bytes(output)


def _reconstruct_base64_payload(directory: Path) -> bytes:
    payloads = sorted(directory.glob("payload-*.b64"))
    if not payloads:
        raise FileNotFoundError(f"no payload-*.b64 files found in {directory}")
    chunks: list[bytes] = []
    for path in payloads:
        text = "".join(path.read_text(encoding="utf-8").split())
        try:
            chunks.append(base64.b64decode(text, validate=True))
        except ValueError as exc:
            raise ValueError(f"invalid base64 land-context payload: {path}") from exc
    return b"".join(chunks)


def reconstruct_land_context_bytes(source: str | Path) -> bytes:
    """Return the exact logical CSV bytes represented by the repository control."""

    path = Path(source)
    if path.is_file():
        return path.read_bytes()
    if not path.is_dir():
        raise FileNotFoundError(f"land-context source not found: {path}")

    parts = sorted(path.glob("part-*.csv"))
    payloads = sorted(path.glob("payload-*.b64"))
    if parts and payloads:
        raise ValueError(
            "land-context directory contains both final CSV shards and base64 payloads; "
            "remove staging artifacts so one representation is authoritative"
        )
    if parts:
        return _reconstruct_sharded_csv(path)
    if payloads:
        return _reconstruct_base64_payload(path)
    raise FileNotFoundError(
        f"land-context directory contains neither part-*.csv nor payload-*.b64: {path}"
    )


def land_context_sha256(source: str | Path) -> str:
    return hashlib.sha256(reconstruct_land_context_bytes(source)).hexdigest()


def _manifest(directory: Path) -> dict[str, object]:
    path = directory / "manifest.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("land-context manifest must be a JSON object")
    return data


def validate_land_context(frame: pd.DataFrame) -> dict[str, object]:
    """Validate the frozen scientific contract without rebuilding any source data."""

    if tuple(frame.columns) != LAND_CONTEXT_COLUMNS:
        missing = sorted(set(LAND_CONTEXT_COLUMNS) - set(frame.columns))
        extra = sorted(set(frame.columns) - set(LAND_CONTEXT_COLUMNS))
        raise ValueError(
            "land-context schema mismatch; "
            f"columns={len(frame.columns)}, missing={missing}, extra={extra}"
        )
    if len(frame) != LAND_CONTEXT_EXPECTED_EDS:
        raise ValueError(
            f"land-context rows={len(frame):,}; expected={LAND_CONTEXT_EXPECTED_EDS:,}"
        )

    keys = frame["CSOED"].map(_canonical_csoed)
    if keys.eq("").any() or keys.duplicated().any():
        raise ValueError("land-context CSOED keys must be non-empty and unique")

    years = pd.to_numeric(frame["LPIS_YEAR"], errors="raise").astype(int)
    if not years.eq(LAND_CONTEXT_YEAR).all():
        raise ValueError("frozen land context must contain LPIS_YEAR=2020 only")

    classes = frame[list(CLASS_SHARE_COLUMNS)].apply(pd.to_numeric, errors="raise").to_numpy(float)
    groups = frame[list(GROUP_SHARE_COLUMNS)].apply(pd.to_numeric, errors="raise").to_numpy(float)
    if (~np.isfinite(classes)).any() or (classes < -1e-10).any():
        raise ValueError("08B class shares must be finite and non-negative")
    if (~np.isfinite(groups)).any() or (groups < -1e-10).any():
        raise ValueError("08B G1/G2/G3 shares must be finite and non-negative")

    class_closure = float(np.max(np.abs(classes.sum(axis=1) - 1.0)))
    group_closure = float(np.max(np.abs(groups.sum(axis=1) - 1.0)))
    pair_groups = np.column_stack(
        (classes[:, 0] + classes[:, 1], classes[:, 2] + classes[:, 3], classes[:, 4] + classes[:, 5])
    )
    pair_error = float(np.max(np.abs(pair_groups - groups)))
    if class_closure > 1e-8 or group_closure > 1e-8 or pair_error > 1e-8:
        raise AssertionError(
            "08B closure failed: "
            f"class={class_closure:.3e}, group={group_closure:.3e}, pair_to_G={pair_error:.3e}"
        )

    source_counts = frame["SOIL_PROFILE_SOURCE"].astype(str).value_counts().to_dict()
    if source_counts != {"ED": 2820, "COUNTY_FALLBACK": 37}:
        raise AssertionError(
            "08B provenance changed; expected ED=2820 and COUNTY_FALLBACK=37, "
            f"found={source_counts}"
        )

    physical = frame[list(PHYSICAL_AREA_COLUMNS)].apply(pd.to_numeric, errors="raise").to_numpy(float)
    if (~np.isfinite(physical)).any() or (physical < -1e-8).any():
        raise ValueError("08C physical areas must be finite and non-negative")
    physical_total = physical.sum(axis=1)
    if (physical_total <= 0).any():
        raise AssertionError("08C physical soil must have positive mapped area in every ED")

    lpis_area_columns = [column for column in LAND_CONTEXT_COLUMNS if column.startswith("LPIS_") and column.endswith("_HA")]
    lpis = frame[lpis_area_columns].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    if np.isfinite(lpis).any() and np.nanmin(lpis) < -1e-8:
        raise ValueError("LPIS context areas cannot be negative")

    grass = pd.to_numeric(frame["LPIS_CLAIMED_GRASS_HA"], errors="raise").to_numpy(float)
    partition = frame[list(LPIS_GRASS_PARTITION_COLUMNS)].apply(pd.to_numeric, errors="coerce").fillna(0.0).sum(axis=1).to_numpy(float)
    grass_error = float(np.max(np.abs(partition - grass)))
    if grass_error > 1e-6:
        raise AssertionError(
            "LPIS represented grass partition does not close to claimed grass; "
            f"max_abs_error={grass_error:.3e} ha"
        )

    return {
        "rows": int(len(frame)),
        "unique_eds": int(keys.nunique()),
        "columns": int(len(frame.columns)),
        "08b_class_closure_max_abs": class_closure,
        "08b_group_closure_max_abs": group_closure,
        "08b_class_pair_to_g_max_abs": pair_error,
        "08b_provenance": source_counts,
        "08c_min_mapped_area_ha": float(physical_total.min()),
        "lpis_grass_partition_max_abs_ha": grass_error,
    }


def read_land_context_table(
    source: str | Path | pd.DataFrame,
    *,
    verify_sha256: bool = True,
) -> pd.DataFrame:
    """Read the single frozen 2020 runtime control and enforce its contract."""

    if isinstance(source, pd.DataFrame):
        frame = source.copy()
    else:
        path = Path(source)
        raw = reconstruct_land_context_bytes(path)
        if verify_sha256:
            expected = LAND_CONTEXT_CANONICAL_SHA256
            if path.is_dir():
                manifest = _manifest(path)
                expected = str(manifest.get("sha256", expected))
            actual = hashlib.sha256(raw).hexdigest()
            if actual != expected:
                raise AssertionError(
                    "frozen land-context SHA256 mismatch; "
                    f"expected={expected}, actual={actual}"
                )
        frame = pd.read_csv(io.BytesIO(raw), low_memory=False)

    validate_land_context(frame)
    frame = frame.copy()
    frame["CSOED"] = frame["CSOED"].map(_canonical_csoed)
    return frame.sort_values("CSOED", kind="stable").reset_index(drop=True)
