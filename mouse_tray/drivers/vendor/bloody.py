"""A4Tech Bloody mice on the "8K" wireless dongle (VID 0x1956).

Not the classic Bloody protocol (VID 0x09DA, 64/72-byte feature report 7 that
every public tool speaks) -- the 8K dongle is a different firmware with its own
VID, and nothing about it is documented anywhere. Everything here comes from a
USBPcap of the vendor's *Wireless 8KM-Esport Editor* talking to a Bloody SG5 Pro,
contributed by JurecUA in https://github.com/Fan4Metal/mouse_tray/issues/5.

The device exposes three HID interfaces; two of them matter:

* **interface 2** (usage page ``0xFF02``): the command channel. Commands are
  8-byte *feature* reports with report id 0.
* the **mouse interface** (usage page ``0xFF01``, usage 1 -- interface 0 on the
  dongle, interface 1 on the wired mouse): the status channel. The mouse
  answers with 8-byte *input* reports numbered ``0x06``.

Request
=======

The vendor software sends two commands on interface 2::

    80 00 00 00 00 00 00 7f     "are you there" -- answered on interface 2's
                                own input endpoint with 80 01 01 00 24 01 ...
                                and with a 06 55 .. status line on the mouse
                                interface. Repeated until the mouse answers.
    80 ff 00 00 00 00 00 80     "dump status" -- answered with a burst of 06 xx
                                reports on the mouse interface, the battery
                                among them.

Whether ``80 ff`` works without the ping in front of it is not known, so the
driver sends both, back to back, exactly like the capture.

Reply
=====

The battery line of the burst::

    06 56 PP CC 00 00 00 00
    |  |  |  `-- 1 on the cable, 0 on the 2.4G link
    |  |  `----- charge percent (0x55 = 85)
    |  `-------- status sub-type: 0x56 = battery
    `----------- report id

The same burst carries two more lines, shown in the tooltip only::

    06 81 RR 00 00 00 00 00     polling rate, code in byte 2
    06 87 00 00 00 00 00 II     DPI, index in the *last* byte

    RR: 00=1000  01=500  02=250  03=125  04=8000  05=4000  06=2000 Hz
    II: 00=400   01=800  02=1000 03=1200 04=1600  05=2000 DPI

The order of the lines within the burst is not guaranteed, so the driver reads
until it has all three or the timeout runs out, and matches by sub-type, never
by position. A code missing from the tables (newer firmware) reads as unknown
(``None``) instead of a guess. The remaining sub-type, ``0x55``, is a link
line; ignored. The mouse also *pushes* a ``06 56`` line on its own when the
cable state changes, but never periodically -- the vendor software does not poll
at all -- so this driver always asks.

Wired
=====

On the cable the mouse enumerates as its own device (PID ``0x3144``, "Wired
Gaming Mouse") with the same three-interface layout (checked in the HID
descriptors of the issue #5 captures), and pushes ``06 56`` on connect.

Which device to ask when both the cable and the dongle are plugged in? Observed
on a real mouse (user's ``app.log``, 2026-10-15): asked alone, the wired device
answers the same two commands with the full burst -- battery, rate and DPI,
and the rate followed the button on the mouse (125/500/1000). The dongle, asked
while the cable was connected, answered ``06 56 FF ..`` (percent 255, i.e. "no
radio link") and the app lost the mouse. So the wired PID is asked first and the
dongle is the fallback (see :meth:`BloodyDriver.read_status`). Not verified:
that the wired device answers just as well while the dongle is also plugged in;
if it does not, the fallback applies.
"""

from __future__ import annotations

import logging
import time
from contextlib import suppress
from typing import ClassVar

import hid  # hidapi -- the single core transport dependency

from ...battery import BatteryStatus
from ..bus import matching
from ..driver import MouseDriver, MouseModel, register

log = logging.getLogger(__name__)

_VID = 0x1956

# Status channel: the vendor collection on the mouse interface.
_STATUS_USAGE_PAGE = 0xFF01
_STATUS_USAGE = 0x0001
# Command channel: the vendor collection on interface 2.
_COMMAND_USAGE_PAGE = 0xFF02
_COMMAND_USAGE = 0x0001

# Feature report id 0 + 8 command bytes.
_PING = [0x00, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x7F]
_QUERY = [0x00, 0x80, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x80]
#: The capture shows the query ~13 ms after the ping's reply.
_PING_GAP = 0.02

_REPORT_ID = 0x06
_SUBTYPE_BATTERY = 0x56
_SUBTYPE_POLLING = 0x81
_SUBTYPE_DPI = 0x87
_PERCENT_BYTE = 2
_CABLE_BYTE = 3
_POLLING_BYTE = 2
_DPI_BYTE = 7
_REPORT_LEN = 8
#: Percent byte of a ``06 56`` line from a dongle that has no radio link.
_NO_LINK = 0xFF

#: Code -> value. Codes outside a table decode to ``None``.
_POLLING_HZ = {0x00: 1000, 0x01: 500, 0x02: 250, 0x03: 125, 0x04: 8000, 0x05: 4000, 0x06: 2000}
_DPI = {0x00: 400, 0x01: 800, 0x02: 1000, 0x03: 1200, 0x04: 1600, 0x05: 2000}
#: The burst lands within ~70 ms of the query; leave generous headroom.
_READ_TIMEOUT = 1.0


@register
class BloodyDriver(MouseDriver):
    models: ClassVar[list[MouseModel]] = [
        # 2.4G "Mouse 8K dongle" 0x3069, direct cable "Wired Gaming Mouse" 0x3144.
        MouseModel("Bloody SG5 Pro", _VID, 0x3069, 0x3144),
    ]

    @classmethod
    def detect_all(cls) -> list[BloodyDriver]:
        """The mouse, when either its dongle or its cable is on the bus."""
        return [
            cls(model)
            for model in cls.models
            if matching(model.vid, model.pid_wireless) or matching(model.vid, model.pid_wired)
        ]

    def _links(self) -> list[int]:
        """PIDs of the devices to ask, best first: the cable, then the dongle.

        Only PIDs actually on the bus. The wired device exists only while the
        cable is connected, and then it is the one that knows the mouse's state
        (see the module docstring); the dongle answers "no link" meanwhile.
        """
        model = self.model
        return [pid for pid in (model.pid_wired, model.pid_wireless) if matching(model.vid, pid)]

    def _paths(self, pid: int) -> tuple[bytes | None, bytes | None]:
        """OS paths of the status and the command collection of one device."""
        status_path = command_path = None
        for device in matching(self.model.vid, pid):
            page, usage = device["usage_page"], device["usage"]
            if (page, usage) == (_STATUS_USAGE_PAGE, _STATUS_USAGE) and status_path is None:
                status_path = device["path"]
            elif (page, usage) == (_COMMAND_USAGE_PAGE, _COMMAND_USAGE) and command_path is None:
                command_path = device["path"]
        return status_path, command_path

    def read_status(self) -> BatteryStatus:
        """Ask the cable first, then the dongle; the first usable answer wins.

        "Usable" means a battery line with a plausible percent. A device that
        stays silent or answers 255 (the dongle while the mouse is on the cable)
        is skipped, so one dead link never hides a working one.
        """
        for pid in self._links():
            try:
                burst = self._read_burst(pid)
            except Exception:
                log.warning("%s read via PID 0x%04X failed", self.name, pid, exc_info=True)
                continue
            if burst is None:
                continue
            percent = burst[_SUBTYPE_BATTERY][_PERCENT_BYTE]
            if percent == _NO_LINK:
                log.debug("%s PID 0x%04X answers 'no link' (255)", self.name, pid)
                continue
            return self._decode(burst)
        return self._no_reply()

    def _read_burst(self, pid: int) -> dict[int, list[int]] | None:
        """Ask one device for status and return the burst's lines by sub-type, or ``None``.

        ``None`` means no ``06 56`` battery line arrived; the other lines are
        optional extras.
        """
        status_path, command_path = self._paths(pid)
        if status_path is None or command_path is None:
            return None
        # Open the status channel *before* asking, so the reply is queued for
        # this handle rather than dropped on the floor.
        status = hid.device()
        try:
            status.open_path(status_path)
            if not self._send_query(command_path):
                return None
            return self._wait_for_burst(status)
        except OSError as exc:
            log.warning("%s HID read failed: %s", self.name, exc)
            return None
        finally:
            with suppress(Exception):
                status.close()

    def _no_reply(self) -> BatteryStatus:
        if matching(self.model.vid, self.model.pid_wired):
            # Cable connected but nothing usable came back: charging for sure,
            # level unknown until a device answers.
            log.info("%s on the cable, no battery reply: charging, level not reported", self.name)
            return BatteryStatus(present=True, percent=None, charging=True)
        log.info("%s no battery reply within %.1fs", self.name, _READ_TIMEOUT)
        return BatteryStatus.absent()

    def _decode(self, burst: dict[int, list[int]]) -> BatteryStatus:
        report = burst[_SUBTYPE_BATTERY]
        percent = report[_PERCENT_BYTE]
        cable = bool(report[_CABLE_BYTE])
        if not 0 <= percent <= 100:
            log.warning("%s implausible percent %s", self.name, percent)
            return BatteryStatus.absent()
        polling_hz = self._lookup(burst, _SUBTYPE_POLLING, _POLLING_BYTE, _POLLING_HZ)
        dpi = self._lookup(burst, _SUBTYPE_DPI, _DPI_BYTE, _DPI)
        log.info("%s battery=%s%% cable=%s polling=%s dpi=%s", self.name, percent, cable, polling_hz, dpi)
        return BatteryStatus(
            present=True,
            percent=percent,
            charging=cable and percent < 100,
            full=cable and percent >= 100,
            asleep=False,
            polling_hz=polling_hz,
            dpi=dpi,
        )

    def _lookup(
        self, burst: dict[int, list[int]], subtype: int, byte: int, table: dict[int, int]
    ) -> int | None:
        """Decode one optional line of the burst, ``None`` if absent or unknown."""
        line = burst.get(subtype)
        if line is None or len(line) <= byte:
            return None
        value = table.get(line[byte])
        if value is None:
            log.info("%s unknown code %#04x in 06 %02x line", self.name, line[byte], subtype)
        return value

    def _send_query(self, command_path: bytes) -> bool:
        """Send ping + status query on the command channel. False if unreachable."""
        command = hid.device()
        try:
            command.open_path(command_path)
            log.debug("%s sending ping: %s", self.name, _PING)
            command.send_feature_report(_PING)
            time.sleep(_PING_GAP)
            log.debug("%s sending query: %s", self.name, _QUERY)
            command.send_feature_report(_QUERY)
            return True
        except OSError as exc:
            log.warning("%s HID command failed: %s", self.name, exc)
            return False
        finally:
            with suppress(Exception):
                command.close()

    def _wait_for_burst(self, status: hid.device) -> dict[int, list[int]] | None:
        """Read the status channel until the whole burst is in, or time out.

        Collects the ``06 56`` / ``06 81`` / ``06 87`` lines by sub-type, whatever
        their order, and returns as soon as all three are here -- so a mouse that
        sends them does not cost the full timeout. Without the extras (older
        firmware) the timeout is what ends the wait, and the battery line alone
        is still returned. ``None`` only when there was no battery line at all.
        """
        wanted = {_SUBTYPE_BATTERY, _SUBTYPE_POLLING, _SUBTYPE_DPI}
        burst: dict[int, list[int]] = {}
        deadline = time.monotonic() + _READ_TIMEOUT
        while not wanted <= burst.keys():
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                break
            data = status.read(_REPORT_LEN, timeout_ms=remaining_ms)
            if not data:
                continue
            log.debug("%s status report: %s", self.name, data)
            if len(data) >= _REPORT_LEN and data[0] == _REPORT_ID and data[1] in wanted:
                burst[data[1]] = data
        return burst if _SUBTYPE_BATTERY in burst else None
