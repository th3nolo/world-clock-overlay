# World Clock Overlay & Work Tracker

World Clock Overlay is an always-on-top desktop clock for remote work across time zones. See your local time next to up to four other clocks. Set reminders in a teammate’s time zone and track your work hours on your computer.

![Local time alongside Nairobi, Berlin, Kathmandu, and the Chatham Islands](screenshots/overlay-horizontal.png)

## Features

- **World clocks.** Choose from the IANA time zone database. Each clock shows the local date and how far ahead or behind you it is, down to the minute.
- **Reminders.** Enter a date and time in the zone where an event is scheduled. For a handoff at 09:00 in Nairobi, choose `Africa/Nairobi` and enter `09:00`. Keep the app running to receive the reminder.
- **Work timer.** Pause when you step away and see your hours for the day and month. Sessions are stored in `~/.world_clock_work_tracker.db` on your computer.
- **Overlay controls.** Drag the clock where you want it, switch between horizontal and vertical layouts, and adjust the opacity. On Windows, clicks on the empty background pass through to the window below.

## Screenshots

### Vertical layout

![Overlay in vertical layout with seconds enabled](screenshots/overlay-vertical.png)

### Themes

| Frosted Light | Cyberpunk Neon | Nordic Frost |
| --- | --- | --- |
| ![Frosted Light theme](screenshots/theme-light.png) | ![Cyberpunk Neon theme](screenshots/theme-cyberpunk.png) | ![Nordic Frost theme](screenshots/theme-nordic.png) |

| Raycast Dark | Liquid Glass |
| --- | --- |
| ![Raycast Dark theme](screenshots/theme-raycast.png) | ![Liquid Glass theme](screenshots/theme-glass.png) |

### Setup wizard

![First-run setup with four time zones selected](screenshots/setup-wizard.png)

## Demos

### Pause with the space bar on Windows

Hover over the overlay and hold Space for half a second. Hold it again to resume.

![Hold Space to pause](screenshots/pause-hold-space.gif)

### Pause with a click

Click the work timer to pause or resume.

![Click the timer to pause](screenshots/pause-click.gif)

### Scroll-wheel opacity

Scroll over the overlay to adjust its opacity. On Windows, scrolling in Liquid Glass changes the tint.

![Scroll wheel adjusts opacity](screenshots/wheel-translucency.gif)

### Theme menu

Right-click the overlay and choose a theme.

![Context menu follows the active theme](screenshots/context-menu-themes.gif)

### Layout toggle

Double-click to switch layouts. The overlay stays anchored to the nearest screen corner.

![Double-click to switch layouts](screenshots/layout-toggle.gif)

## Run

### Windows

In PowerShell, use [uv](https://docs.astral.sh/uv/getting-started/installation/) and CPython 3.11–3.15 with Tkinter. Replace `3.12` with your installed version.

```powershell
uv venv --no-python-downloads --python 3.12 .venv
uv pip sync --python .venv --require-hashes --only-binary :all: --default-index https://pypi.org/simple requirements-windows.txt
.\.venv\Scripts\python.exe clock.py
```

After setup, double-click `run_clock.bat` to launch.

### WSL

Use [WSL 2 with WSLg](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps) and Python 3.9 or newer. On Ubuntu or Debian, install `python3-tk` and `tzdata`.

```bash
python3 clock.py
```

Liquid Glass uses a static panel on WSL.

## Controls

- Click the timer to pause or resume. Double-click the overlay to switch layouts.
- Right-click to change clocks, add a reminder, or adjust the display.
- With the tray icon active, choose **Hide Overlay** from the right-click menu. Click the tray icon to peek or double-click to restore.
- On Windows, hover over Liquid Glass and press Delete to show it in screen recordings.

## Tests

From the project folder, run both scripts. On Windows, use `.\.venv\Scripts\python.exe` in place of `python3`.

```bash
python3 test_layout.py
python3 test_wheel_stats.py
```
