# World Clock Overlay & Work Tracker

A native Python desktop widget that displays the current time in your local system timezone and up to 4 additional user-configured country timezones. It floats on top of other windows, supports click-through transparency, and logs your active working session duration to a local SQLite database.

![Overlay in horizontal layout, dark theme](screenshots/overlay-horizontal.png)

## Features

- **Up to 5 clocks in one panel**: Your local time plus four configurable timezones, rendered as a single rounded panel with hairline dividers.
- **Day/night indicator**: Each clock shows a sun (7am–7pm) or moon icon, so you can see at a glance who is awake.
- **Relative offset badges**: Each remote timezone displays its difference from your local time (e.g. `+6h`).
- **Two layouts**: Horizontal columns or a vertical stack — double-click the widget to toggle.
- **First-run configuration wizard**: Prompts you on first launch to select which country timezones to load.
- **SQLite work tracking database**: Saves working session start times, end times, and total duration to `~/.world_clock_work_tracker.db`.
- **Monthly stats status bar**: Displays a real-time stopwatch of your current session and a summary of your active working days and total hours in the current month.
- **Four themes**: Frosted Dark, Frosted Light, Cyberpunk Neon, and Nordic Frost, switchable from the context menu.
- **Translucency adjustment**: Supports widget opacity scaling from 30% to 100% via the context menu.
- **Mouse transparency (Click-through)**: Configures the window background to be click-through on Windows, allowing clicks to pass directly to underlying applications.
- **Corner anchoring**: Detects the nearest screen border and locks the window position when toggling layouts to prevent shifting.
- **Drag feedback**: Temporarily reduces window opacity to 30% during drag operations.
- **State persistence**: Saves coordinates and preferences to `~/.world_clock_overlay.json` on exit.

## Screenshots

### Vertical layout (with seconds)

![Overlay in vertical layout with seconds enabled](screenshots/overlay-vertical.png)

### Themes

| Frosted Light | Cyberpunk Neon | Nordic Frost |
| --- | --- | --- |
| ![Frosted Light theme](screenshots/theme-light.png) | ![Cyberpunk Neon theme](screenshots/theme-cyberpunk.png) | ![Nordic Frost theme](screenshots/theme-nordic.png) |

### First-run setup wizard

![Setup wizard](screenshots/setup-wizard.png)

## Running the Application

### Windows Host
Double-click `run_clock.bat` inside the network folder:
```text
\\wsl.localhost\<distro-name>\home\<username>\world-clock-overlay\
```
*(The script verifies dependencies, installs required packages, and launches pythonw.exe in the background).*

### WSL Environment
1. Install Python Tkinter:
   ```bash
   sudo apt-get update && apt-get install python3-tk
   ```
2. Launch the script:
   ```bash
   python3 clock.py
   ```

## Controls

- **Move**: Click and drag anywhere on the panel.
- **Resize layout**: Double-click the widget to toggle horizontal and vertical orientations.
- **Options menu**: Right-click the panel or the system tray icon to change themes, format, translucency, or reset the clocks setup wizard.

## Verification

Run the layout test suite to verify text alignment and spacing:
```bash
python3 test_layout.py
```
