"""User-tunable settings and shared color constants."""

from __future__ import annotations

from dataclasses import dataclass

#: Application version, shown in the settings and about dialogs. Single source
#: for the runtime version (re-exported as ``mouse_tray.__version__``).
VERSION = "1.0.0"

#: Project identity, shown in the about dialog. Kept here with VERSION so the
#: dialog has a single source for everything it prints about the app itself.
DESCRIPTION = (
    "Battery and report-rate indicator for the Bloody SG5 Pro (8K) wireless mouse "
    "in the Windows system tray. Portable: settings live next to the program."
)
HOMEPAGE = "https://github.com/Fan4Metal/mouse_tray"

#: Author, stamped into the exe's version resource (CompanyName and
#: LegalCopyright) by tools/make_release.py.
AUTHOR = "Fan4_Metal"

#: Colors of the report-rate icon, matching the mouse's own rate indicator LED
#: (colors read off the manual's "Report Rate Adjustable" page; the RGB values
#: are approximations of what is printed there, not measured). 250 Hz is not
#: on the mouse -- only newer vendor software has it -- so it is neutral gray.
RATE_COLORS = {
    125: (200, 90, 220),  # purple
    250: (150, 150, 150),  # gray
    500: (0, 200, 190),  # teal
    1000: (255, 255, 255),  # white
    2000: (60, 210, 60),  # green
    4000: (255, 220, 0),  # yellow
    8000: (70, 150, 255),  # blue
}
# Why these are lighter than the LED colors: the outline is black for a fill with
# luminance above 0.5 and white below (see ui/icons.py::_outline_color). The first
# blue (40, 120, 255) sat just under that line, got a *white* outline, and the "8K"
# turned to mush on a dark taskbar. Every color here stays above 0.5 (tested).
RATE_COLOR_UNKNOWN = (150, 150, 150)

# Colors (RGB)
RED = (255, 0, 0)
GREEN = (71, 255, 12)
BLUE = (91, 184, 255)
YELLOW = (255, 255, 0)


#: Charge thresholds (percent) for the two low bands of ``dynamic_color``.
MID_THRESHOLD = 50
LOW_THRESHOLD = 20

#: Text size slider range, in percent of the fitted maximum: TEXT_SIZE_DEFAULT
#: fills the icon and is the default; lower values shrink.
TEXT_SIZE_MIN = 50
TEXT_SIZE_DEFAULT = 100
TEXT_SIZE_MAX = 100


@dataclass
class Config:
    """Application settings.

    Attributes:
        poll_rate:        Seconds between battery reads while the mouse is
                          present and awake -- discharging or charging alike.
        fast_poll_rate:   Seconds between reads while the mouse is asleep or
                          missing, where we want to notice it coming back.
        foreground_color: RGB color of the indicator digits. Under
                          ``dynamic_color`` it is also the color of the top
                          charge band (above ``MID_THRESHOLD``).
        dynamic_color:    When True, the battery-percent indicator is colored by
                          charge level: ``low_color`` at or below
                          ``LOW_THRESHOLD``, ``mid_color`` at or below
                          ``MID_THRESHOLD``, ``foreground_color`` above it.
        mid_color:        RGB color of the middle charge band under
                          ``dynamic_color``.
        low_color:        RGB color of the lowest charge band under
                          ``dynamic_color``.
        battery_icon:     When True, the charge level is drawn as a battery
                          filled to that percent instead of as digits; the exact
                          number moves to the hover tooltip. Only affects the
                          percent readout -- "no mouse", sleep and unknown-level
                          states stay textual.
        background_color: RGBA color of the icon background (transparent default).
        font:             Font file used for the digital indicator.
        text_size:        Tray digit size, ``TEXT_SIZE_MIN``-``TEXT_SIZE_MAX``
                          percent of the fitted maximum. ``TEXT_SIZE_DEFAULT``
                          (100) fills the icon; lower values shrink every
                          string proportionally.
        text_outline:     When True, the digits carry a thin contrasting
                          outline so they stay readable on a same-colored
                          taskbar. Turn it off for plain glyphs.
        display_name:     Human-facing app name (tray tooltip, notifications,
                          settings-dialog title). Change this freely; it does not
                          affect any stored path.
        debug:            Enable verbose DEBUG logging (raw HID reports). Can
                          also be turned on via the MOUSE_TRAY_DEBUG env var.
    """

    poll_rate: int = 60
    fast_poll_rate: int = 1
    foreground_color: tuple[int, int, int] = BLUE
    dynamic_color: bool = False
    mid_color: tuple[int, int, int] = YELLOW
    low_color: tuple[int, int, int] = RED
    battery_icon: bool = False
    background_color: tuple[int, int, int, int] = (0, 0, 0, 0)
    font: str = "consola.ttf"
    text_size: int = TEXT_SIZE_DEFAULT
    text_outline: bool = True
    dark_theme: bool = True
    display_name: str = "Bloody Mouse Tray"
    debug: bool = False

    def charge_color(self, percent: int) -> tuple[int, int, int]:
        """Color for a battery ``percent`` when ``dynamic_color`` is on.

        The top band keeps ``foreground_color`` -- so enabling the option only
        recolors the two low bands, and the user's chosen color still means "the
        charge is fine".
        """
        try:
            level = int(percent)
        except (TypeError, ValueError):
            return self.foreground_color
        if level <= LOW_THRESHOLD:
            return self.low_color
        if level <= MID_THRESHOLD:
            return self.mid_color
        return self.foreground_color


# Default instance used across the app. Replace fields here to retune.
config = Config()
