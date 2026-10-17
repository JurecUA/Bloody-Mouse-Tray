"""Driver package: the contract, the registry, and the one driver this build ships.

Importing the package imports the Bloody driver, which runs its ``@register``
decorator and fills the registry.
"""

from __future__ import annotations

from .driver import MouseDriver, MouseModel, all_drivers, detect_all_drivers, register
from .vendor import bloody  # noqa: F401  (registers the Bloody driver)

__all__ = ["MouseDriver", "MouseModel", "all_drivers", "detect_all_drivers", "register"]
