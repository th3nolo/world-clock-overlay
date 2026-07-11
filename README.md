# World Clock Overlay & Work Tracker

A native Python desktop widget that displays the current time in your local system timezone and up to 4 additional user-configured country timezones. It floats on top of other windows, supports click-through transparency, and logs your active working session duration to a local SQLite database.

## Features

- **First-run configuration wizard**: Prompts you on first launch to configure how many clocks to display and select which country timezones to load.
- **SQLite work tracking database**: Saves working session start times, end times, and total duration to `~/.world_clock_work_tracker.db`.
- **Monthly stats status bar**: Displays a real-time stopwatch of your current session and a summary of your active working days and total hours in the current month.
- **Translucency adjustment**: Supports card opacity scaling from 15% to 100% via the context menu.
- **Mouse transparency (Click-through)**: Configures the window background to be click-through on Windows, allowing clicks to pass directly to underlying applications.
- **Corner anchoring**: Detects the nearest screen border and locks the window position when toggling layouts to prevent shifting.
- **Drag feedback**: Temporarily reduces window opacity to 30% during drag operations.
- **State persistence**: Saves coordinates and preferences to `~/.world_clock_overlay.json` on exit.

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

- **Move**: Click and drag any clock card.
- **Resize layout**: Double-click the widget to toggle horizontal and vertical orientations.
- **Options menu**: Right-click any card or the system tray icon to change themes, format, translucency, or reset the clocks setup wizard.

## Verification

Run the layout test suite to verify text alignment and spacing:
```bash
python3 test_layout.py
```
