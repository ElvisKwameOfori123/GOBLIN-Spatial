"""Install local spatial inputs into the GOBLIN-Spatial project layout.

Raw GIS binaries are intentionally kept out of ordinary Git history.  This
helper copies user-supplied source files into the canonical project paths and
extracts the SIS bundle in place.

Example
-------
python scripts/install_spatial_inputs.py \
  --ed-shp "C:/path/Electoral_Divisions_generalised_SAPS_Shp_with_proper_names.shp" \
  --sis-zip "C:/path/INSM250k_ING_1b.zip" \
  --lpis-audit "C:/path/LPIS_2020_audit.xlsx"
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPATIAL_ROOT = PROJECT_ROOT / "data" / "external" / "spatial"
ED_DIR = SPATIAL_ROOT / "ed"
SIS_DIR = SPATIAL_ROOT / "sis_soils"
LPIS_DIR = SPATIAL_ROOT / "lpis"

ED_CANONICAL_STEM = "Electoral_Divisions_generalised_SAPS_Shp_with_proper_names"
SIS_CANONICAL_ZIP = "INSM250k_ING_1b.zip"
LPIS_CANONICAL = "LPIS_2020_audit.xlsx"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_ed_bundle(ed_shp: Path) -> list[Path]:
    if ed_shp.suffix.lower() != ".shp":
        raise ValueError("--ed-shp must point to the .shp member of the ED shapefile")

    ED_DIR.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []

    for suffix in (".shp", ".shx", ".dbf", ".prj"):
        src = ed_shp.with_suffix(suffix)
        if not src.exists():
            raise FileNotFoundError(f"Missing required ED shapefile sidecar: {src}")
        dst = ED_DIR / f"{ED_CANONICAL_STEM}{suffix}"
        shutil.copy2(src, dst)
        copied.append(dst)

    return copied


def install_sis_bundle(sis_zip: Path) -> list[Path]:
    if not sis_zip.exists():
        raise FileNotFoundError(sis_zip)

    SIS_DIR.mkdir(parents=True, exist_ok=True)
    dst_zip = SIS_DIR / SIS_CANONICAL_ZIP
    shutil.copy2(sis_zip, dst_zip)

    with zipfile.ZipFile(dst_zip) as archive:
        archive.extractall(SIS_DIR)

    required = [
        SIS_DIR / "INSM250k_ING.shp",
        SIS_DIR / "INSM250k_ING.shx",
        SIS_DIR / "INSM250k_ING.dbf",
        SIS_DIR / "INSM250k_ING.prj",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"SIS archive did not contain required members: {missing}")

    return [dst_zip, *required]


def install_lpis_audit(lpis_audit: Path) -> Path:
    if not lpis_audit.exists():
        raise FileNotFoundError(lpis_audit)

    LPIS_DIR.mkdir(parents=True, exist_ok=True)
    dst = LPIS_DIR / LPIS_CANONICAL
    shutil.copy2(lpis_audit, dst)
    return dst


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ed-shp", type=Path, required=True)
    parser.add_argument("--sis-zip", type=Path, required=True)
    parser.add_argument("--lpis-audit", type=Path)
    args = parser.parse_args()

    outputs: list[Path] = []
    outputs.extend(install_ed_bundle(args.ed_shp.expanduser().resolve()))
    outputs.extend(install_sis_bundle(args.sis_zip.expanduser().resolve()))

    if args.lpis_audit is not None:
        outputs.append(install_lpis_audit(args.lpis_audit.expanduser().resolve()))

    print("Installed spatial inputs:")
    for path in outputs:
        print(f"  {path.relative_to(PROJECT_ROOT)}")

    print("\nSHA256 checksums for principal inputs:")
    print(
        "  ED .shp: ",
        sha256_file(ED_DIR / f"{ED_CANONICAL_STEM}.shp"),
        sep="",
    )
    print("  SIS zip: ", sha256_file(SIS_DIR / SIS_CANONICAL_ZIP), sep="")
    if args.lpis_audit is not None:
        print("  LPIS audit: ", sha256_file(LPIS_DIR / LPIS_CANONICAL), sep="")

    print(
        "\nNext: install the geo extra and run the neutral ED x SIS association "
        "overlay. Do not classify GOBLIN soil groups or future land uses yet."
    )


if __name__ == "__main__":
    main()
