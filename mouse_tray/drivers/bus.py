"""One shared snapshot of the HID bus.

Detection and the read that follows it ask about several VID/PID pairs, so a
naive ``hid.enumerate(vid, pid)`` per question would rescan the bus each time.
Instead the bus is enumerated once and matched in memory, with a short TTL so
one poll tick shares one snapshot.

The TTL is well below the fastest poll rate, so hot-plug still lands within one
tick.
"""

from __future__ import annotations

import logging
import time

import hid

log = logging.getLogger(__name__)

#: Seconds a bus snapshot stays valid.
_SCAN_TTL = 0.5

_snapshot: tuple[float, list[dict]] | None = None


def enumerate_devices() -> list[dict]:
    """Every HID collection currently on the bus (cached for ``_SCAN_TTL``).

    Never raises: a failed enumeration reads as an empty bus, which the callers
    already treat as "no mouse".
    """
    global _snapshot  # noqa: PLW0603 -- one process-wide cache, by definition
    now = time.monotonic()
    if _snapshot is not None and now - _snapshot[0] < _SCAN_TTL:
        return _snapshot[1]
    try:
        devices = hid.enumerate(0, 0)
    except OSError as exc:
        log.warning("HID enumeration failed: %s", exc)
        devices = []
    _snapshot = (now, devices)
    return devices


def matching(vid: int, pid: int) -> list[dict]:
    """Snapshot entries for one VID/PID pair."""
    return [d for d in enumerate_devices() if d["vendor_id"] == vid and d["product_id"] == pid]

