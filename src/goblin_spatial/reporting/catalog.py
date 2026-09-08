"""Generic provenance helpers for frozen reporting artefacts.

Run identity is owned by the scientific synthesis layer. This module deliberately
contains no parallel run abstraction and never invokes the model.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path


def file_sha256(path: str | Path) -> str:
    """Return the SHA-256 digest of an existing file."""

    p = Path(path)
    h = sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
