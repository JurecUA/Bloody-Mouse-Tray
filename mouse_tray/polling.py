"""How a report rate looks on the tray icon, and when a charge counts as new.

Pure functions, no wx -- so both are unit-tested without a display.
"""

from __future__ import annotations

from .config import RATE_COLOR_UNKNOWN, RATE_COLORS


def rate_label(hz: int) -> str:
    """Short icon text for a report rate: ``125``, ``250``, ``500``, ``1K`` ... ``8K``.

    From a thousand up the number is shortened to thousands with a ``K`` so the
    text stays two characters wide; a non-round value keeps its decimals
    (``1500`` -> ``1.5K``).
    """
    if hz < 1000:
        return str(hz)
    thousands = hz / 1000
    return f"{thousands:g}K"


def rate_color(hz: int) -> tuple[int, int, int]:
    """Icon color for a report rate; gray when the rate has no known color."""
    return RATE_COLORS.get(hz, RATE_COLOR_UNKNOWN)


def is_new_full_charge(previous_percent: int | None, percent: int | None, has_full_date: bool) -> bool:
    """Whether ``percent`` means the battery has just reached 100%.

    ``previous_percent`` is the level seen the last time the app looked, even in
    an earlier run -- so a mouse charged while the PC was off (below 100 at the
    last look, 100 now, no cable needed) is recognized as a fresh full charge.

    Without a previous level (first run) a full battery only counts when no
    full-charge date is stored yet; otherwise the stored date is kept.
    """
    if percent is None or percent < 100:
        return False
    if previous_percent is None:
        return not has_full_date
    return previous_percent < 100
