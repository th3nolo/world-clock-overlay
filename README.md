# World Clock Overlay & Work Tracker

A Python desktop overlay, built with Tkinter, that shows your local time and up to four more timezones. It floats above other windows and records your work sessions in a local SQLite database.

![Overlay in horizontal layout, dark theme](screenshots/overlay-horizontal.png)

## Features

- **Up to 5 clocks in one panel**: your local time plus four timezones you pick, drawn as one rounded panel with thin divider lines.
- **Day/night icons**: each clock shows a sun (7am–7pm) or a moon.
- **Time difference**: each remote clock shows its offset from your local time, e.g. `+6h`.
- **Two layouts**: horizontal columns or a vertical stack; double-click the overlay to switch.
- **Setup wizard**: on first launch, pick the timezones to display.
- **Work tracker**: each run of the overlay is recorded as a work session (start, end, duration) in `~/.world_clock_work_tracker.db`.
- **Status bar**: a live stopwatch for the current session, plus days worked and total hours in the current month.
- **Four themes**: Frosted Dark, Frosted Light, Cyberpunk Neon, and Nordic Frost.
- **Translucency**: set the overlay between 30% and 100% opacity from the right-click menu, or scroll the mouse wheel while hovering the overlay.
- **Readable on light backgrounds**: secondary text (labels, dates, status bar) is near-white — near-black in the light theme — and every text is drawn with a 1px contrast shadow, so the translucent overlay stays legible over white windows.
- **Click-through (Windows)**: clicks on the empty background pass through to the window underneath.
- **Corner anchoring**: when the layout toggles, the window keeps its nearest screen corner instead of drifting.
- **Drag feedback**: the overlay dims to 30% opacity while being dragged.
- **Saved state**: position and preferences are written to `~/.world_clock_overlay.json` on exit and restored on launch.
- **System tray icon** (optional): mirrors the right-click menu; requires the Pillow and pystray packages.

## Screenshots

### Vertical layout (with seconds)

![Overlay in vertical layout with seconds enabled](screenshots/overlay-vertical.png)

### Themes

| Frosted Light | Cyberpunk Neon | Nordic Frost |
| --- | --- | --- |
| ![Frosted Light theme](screenshots/theme-light.png) | ![Cyberpunk Neon theme](screenshots/theme-cyberpunk.png) | ![Nordic Frost theme](screenshots/theme-nordic.png) |

### Setup wizard

![Setup wizard](screenshots/setup-wizard.png)

## Running the Application

### Windows host

Double-click `run_clock.bat` from the WSL network path:
```text
\\wsl.localhost\<distro-name>\home\<username>\world-clock-overlay\
```
The script installs Pillow and pystray if they are missing, then launches `pythonw.exe` in the background.

### WSL

1. Install Tkinter:
   ```bash
   sudo apt-get update && sudo apt-get install python3-tk
   ```
2. Launch:
   ```bash
   python3 clock.py
   ```

## Controls

- **Move**: click and drag anywhere on the overlay.
- **Toggle layout**: double-click to switch between horizontal and vertical.
- **Translucency**: scroll the mouse wheel while hovering the overlay (steps through 30/50/70/85/100%).
- **Options**: right-click the overlay (or the tray icon) for time format, seconds, translucency, themes, and "Reset Clocks Setup Wizard".

## Tests

The layout tests check that labels and icons do not overlap:
```bash
python3 test_layout.py
```

The wheel/stats tests check scroll-wheel translucency stepping and work-hour accounting (uses an isolated profile, never touches your real config or database):
```bash
python3 test_wheel_stats.py
```
