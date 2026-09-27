"""Canonical Electoral Division key handling for historical cattle inputs."""

from __future__ import annotations


def canonical_ed_key(value: object) -> str:
    """Return a stable ED key across zero-padded and grouped CSO codes.

    For example, 01003 and 1003 both become 1003, while grouped codes
    are ordered numerically so 32028/32025 becomes 32025/32028.
    """

    text = str(value).strip()
    if not text:
        raise ValueError("ED code must not be blank")

    parts: list[int] = []
    for raw in text.split("/"):
        token = raw.strip()
        if not token:
            raise ValueError(f"invalid grouped ED code: {value!r}")
        try:
            number = int(float(token))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid ED code: {value!r}") from exc
        parts.append(number)

    parts.sort()
    return "/".join(str(number) for number in parts)
