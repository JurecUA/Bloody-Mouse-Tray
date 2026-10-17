"""Plain data the app hands to the settings dialog (no wx, so it is easy to test)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BatteryInfo:
    """What the settings dialog's battery card shows; built from the last reading."""

    percent: int | None
    headline: str  # mouse name, report rate and DPI
    detail: str  # e.g. "Full 3 d ago" or "Charging"
