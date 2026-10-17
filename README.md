# Bloody Mouse Tray

**English** | [Русский](README.ru.md) | [Українська](README.uk.md)

Battery level and polling rate indicator for the **Bloody SG5 Pro (8K)** wireless mouse in the Windows 11 system tray.

**Repository:** [JurecUA/Bloody-Mouse-Tray](https://github.com/JurecUA/Bloody-Mouse-Tray)  
Fork / modification based on [Fan4Metal/mouse_tray](https://github.com/Fan4Metal/mouse_tray); support is kept exclusively for this mouse model
(dongle `1956:3069`, cable `1956:3144`). Bloody Central does not need to be kept running.

## Features

- **Interface languages:** English, Russian, and Ukrainian. Choose a language in **Settings → System → Language**; the selection is saved with the other settings.

- **Tray Battery Level:** Displayed as numbers or a battery icon. The icon animates while charging. The mouse is queried every `Poll interval`
  (60 seconds by default); only once per second if the mouse is asleep or not found. Clicking or hovering over the icon reads the mouse immediately.
- **Mouse Hover:** Hovering over the icon displays the current polling rate colored according to the mouse's built-in LED indicator scheme. The charge level returns once the cursor leaves. Labels: `125`, `250`, `500`, `1K`, `2K`, `4K`, `8K`.

  | Rate | Color | | Rate | Color |
  |---|---|---|---|---|
  | 125 | purple | | 2000 | green |
  | 250 | gray (not present on the actual mouse) | | 4000 | yellow |
  | 500 | turquoise | | 8000 | blue |
  | 1000 | white | | | |

  Colors are taken from the "Report Rate Adjustable" section of the manual; RGB values are approximate (`RATE_COLORS` in
  `mouse_tray/config.py`). The rate icon respects the **Text outline** setting; without an outline, white 1000Hz is invisible on a light taskbar.
- **Tooltip:** Mouse name, time since last full charge, polling rate, and DPI. The percentage is only shown in "battery icon" mode (since there are no numbers on the icon itself).
- **Full Charge Timer:** Starts when the charge reaches 100%, including cases where the mouse charged while the computer was off: the program remembers the last seen level and detects a jump to 100% upon startup. In this case, time is counted from the first poll after boot. False 100% readings immediately after unplugging the cable mid-charge (a firmware quirk) are ignored. The tray menu (right-click) shares the same dark styling as the settings: **Reset timer** clears the timer manually, followed by Settings, About, and Exit.
- **Cable and Dongle Simultaneously:** When the cable is connected, the wired mouse is queried first; the dongle remains as a backup option (the dongle reports "no connection" while plugged into a cable).
- **Portability:** Settings, full charge date, and last battery level are stored in `mouse_tray.json` next to the application. Logs (`logs\app.log`) are only written when **Debug logging** is enabled; if disabled, neither the file nor the folder is created (warnings go to the console only, if available). The program does not use `AppData`; it only writes an optional startup entry to the registry (see below) and reads the system font list for settings.
- **Autostart:** The **Start with Windows** checkbox in settings adds an entry to
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (pointing to the current executable path). If you move the program folder, click OK in settings with the checkbox checked to update the path. The **Reset to defaults** button does not affect autostart.

## Running from Source

Requires 64-bit Windows 11 and Python 3.11+ (Python 3.14 pinned in the project).

```powershell
uv sync
uv run python main.py
```

