"""Driver contract and the registry.

A *driver* knows how to detect a mouse on the HID bus and read its battery. The
UI talks only to this contract (:class:`MouseDriver`) and never to a concrete
driver; this build ships one, :mod:`~mouse_tray.drivers.vendor.bloody`.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from ..battery import BatteryStatus

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MouseModel:
    """A supported mouse and the USB ids it shows up under."""

    name: str
    vid: int
    pid_wireless: int
    pid_wired: int


class MouseDriver(ABC):
    """Base class for drivers; an instance is bound to one connected model."""

    #: Models this driver can talk to. Subclasses override.
    models: ClassVar[list[MouseModel]] = []

    def __init__(self, model: MouseModel):
        self.model = model

    @property
    def name(self) -> str:
        """Display name shown in the tooltip and notifications."""
        return self.model.name

    @classmethod
    @abstractmethod
    def detect_all(cls) -> list[MouseDriver]:
        """Return an instance for every connected model this driver handles.

        Empty when nothing handled by this driver is plugged in. Must not raise
        for an absent device.
        """

    @abstractmethod
    def read_status(self) -> BatteryStatus:
        """Read the current battery state.

        Returns :meth:`BatteryStatus.absent` if the device vanished between
        detection and this call (hot-unplug). Must not raise for I/O hiccups.
        """


# --- Registry ---------------------------------------------------------------

_REGISTRY: list[type[MouseDriver]] = []


def register(driver_cls: type[MouseDriver]) -> type[MouseDriver]:
    """Class decorator that adds a driver to the registry."""
    _REGISTRY.append(driver_cls)
    return driver_cls


def all_drivers() -> list[type[MouseDriver]]:
    """Every registered driver class, in registration order."""
    return list(_REGISTRY)


def detect_all_drivers() -> list[MouseDriver]:
    """Every connected supported mouse. A driver that fails is skipped, not fatal."""
    found: list[MouseDriver] = []
    for driver_cls in _REGISTRY:
        try:
            found.extend(driver_cls.detect_all())
        except Exception as exc:  # a misbehaving driver must not kill detection
            log.warning("Driver %s failed during detection: %s", driver_cls.__name__, exc)
    return found
