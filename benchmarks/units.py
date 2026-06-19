"""
Byte-size parsing and dbg-bigfiles parameter construction (pure).

``dbg-bigfiles`` only understands ``B``, ``MiB`` and ``GiB`` units (see its
``bigfiles.py``); notably it does *not* accept ``KiB``. To stay exact and avoid
that pitfall we always emit byte (``B``) strings, which it parses as integers.
"""

from __future__ import annotations

import re


_UNIT_BYTES = {
    "b": 1,
    "k": 1024, "kib": 1024, "kb": 1000,
    "m": 1024 ** 2, "mib": 1024 ** 2, "mb": 1000 ** 2,
    "g": 1024 ** 3, "gib": 1024 ** 3, "gb": 1000 ** 3,
}

_SIZE_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)\s*$")


def parse_size(size: "str | int | float") -> int:
    """
    Parse a human size into an integer number of bytes.

    Bare numbers and a bare ``k``/``m``/``g`` are interpreted as binary (1024-based),
    matching the ``KiB``/``MiB`` intent used throughout the strategy.
    """
    if isinstance(size, (int, float)):
        return int(size)
    
    m = _SIZE_RE.match(size)
    if not m:
        raise ValueError(f"cannot parse size: {size!r}")
    
    number, unit = m.group(1), m.group(2).lower()

    if unit == "":
        unit = "b"

    if unit not in _UNIT_BYTES:
        raise ValueError(f"unrecognized size unit {unit!r} in {size!r}")
    
    return int(float(number) * _UNIT_BYTES[unit])


def to_dbg_params(file_count: int, file_size: "str | int") -> dict:
    """
    Map (file_count, file_size) to dbg-bigfiles ``{total, size}`` byte strings.

    dbg-bigfiles writes files ``while current_total < total``, so ``total =
    file_count * size`` yields exactly ``file_count`` files.
    """
    if file_count < 1:
        raise ValueError("file_count must be >= 1")
    
    per = parse_size(file_size)
    total = per * file_count
    return {"total": f"{total}B", "size": f"{per}B"}
