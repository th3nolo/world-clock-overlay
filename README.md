# World Clock Overlay

A native Python desktop widget that displays the current time in Venezuela, Spain, and Saudi Arabia. It floats on top of other windows and supports click-through transparency.

## Features

- **Timezone displays**: Shows VET, CET/CEST, and AST timezones with relative hour offsets calculated against local system time.
- **Translucency adjustment**: Supports card opacity scaling from 15% to 100% via the context menu.
- **Mouse transparency (Click-through)**: Configures the window background to be click-through on Windows, allowing clicks to pass directly to underlying applications.
- **Corner anchoring**: Detects the nearest screen border and locks the window position when toggling layouts so the widget does not shift.
- **Drag feedback**: Temporarily reduces window opacity to 30% during drag operations.
- **Layout modes**: Supports horizontal strip and vertical dock orientations.
- **State persistence**: Saves coordinates and preferences to `~/.world_clock_overlay.json` on exit.

## Running the Application

### Windows Host
Double-click `run_clock.bat` inside the network folder:
```text
\\wsl.localhost\<distro-name>\home\<username>\world-clock-overlay\
```
*(The script verifies dependencies and launches pythonw.exe in the background).*

### WSL Environment
1. Install Python Tkinter:
   ```bash
   sudo apt-get update && sudo apt-get install python3-tk
   ```
2. Launch the script:
   ```bash
   python3 clock.py
   ```

## Controls

- **Move**: Click and drag any clock card.
- **Resize layout**: Double-click the widget to toggle horizontal and vertical orientations.
- **Options menu**: Right-click any card or the system tray icon to change themes, format, and opacity.

## Verification

Run the layout test suite to verify text alignment and spacing:
```bash
python3 test_layout.py
```
