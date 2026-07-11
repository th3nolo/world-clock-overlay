# 🕒 Native World Clock Overlay Widget

A lightweight, high-performance, **native Python application** displaying the time in **Venezuela (VET)**, **Saudi Arabia (AST/KSA)**, and **Spain (CET/CEST)**. 

Designed specifically to be non-intrusive, transparent, and floating. On Windows, the app uses native window keying to make empty spaces **100% transparent and click-through**, meaning you can click, drag, and select text *behind* the widget without it interfering with your work.

---

## ✨ Features

- **🚀 100% Native & Lightweight**: Built using Python's standard `tkinter` library. Requires **zero package installations** (`pip install`) on Windows. It uses less than 15MB of RAM and virtually 0% CPU.
- **🛡️ Native Click-Through (Windows)**: The background of the widget is completely transparent and click-through. The clock cards themselves are solid, draggable, and interactive. You can work directly "underneath" the overlay.
- **🎨 Premium Visual Themes**: Vector-drawn flags and clean cards supporting:
  - **Frosted Dark** (Slate grey/dark glass aesthetic)
  - **Frosted Light** (Light mode)
  - **Cyberpunk Neon** (Dark mode with pink borders and cyan glowing text)
  - **Nordic Frost** (Arctic blue elements)
- **📐 Dual Layouts**: Supports horizontal strip and vertical dock layout orientations.
- **📈 Relative Offset Indicator**: Shows the hour difference from the widget to your local machine's system time (e.g. `+7h`, `-4h`, `Local`).
- **⚙️ Interactive Settings Menu**: Right-click anywhere on the clocks to:
  - Toggle 12-Hour (AM/PM) / 24-Hour display format.
  - Toggle seconds display (updating clocks less frequently).
  - Adjust transparency (overall window opacity).
  - Swap themes.
  - Exit the application.
- **💾 Position Memory**: Automatically remembers where you positioned the widget on your screen and opens in that exact spot next time.

---

## 🚀 How to Run Natively on Windows (Recommended)

Since your WSL directory is accessible from Windows, you can launch the app directly:

1. Open your Windows **File Explorer** and go to your WSL directory path:
   ```text
   \\wsl.localhost\<distro-name>\home\<username>\world-clock-overlay\
   ```
   *(Replace `<distro-name>` and `<username>` with your actual WSL Linux distribution name and user profile name)*
2. Double-click the **`run_clock.bat`** file.
3. **That's it!** The transparent clock overlay will appear on your Windows desktop.
   *Note: Using `run_clock.bat` runs the script silently in the background with no command prompt window.*

---

## 🚀 How to Run in WSL

If you prefer to run it inside WSL (displaying on your screen via WSLg):

1. Install Python Tkinter (required on Linux/WSL):
   ```bash
   sudo apt-get update
   sudo apt-get install python3-tk
   ```
2. Run the application:
   ```bash
   cd ~/world-clock-overlay
   python3 clock.py
   ```

---

## 🖱️ Controls & Customization

- **Drag to Move**: Click and drag *any* of the clock cards to move the widget anywhere on your screen.
- **Change Settings**: **Right-click** on any clock card to open the configuration menu (Layout, Time Format, Theme, Opacity, Exit).
- **Toggle Layout**: **Double-click** anywhere on the widget to instantly swap between horizontal and vertical styles.

---

## 🛠️ Layout QA Testing Pipeline

An automated layout verification test suite is available in `test_layout.py` to prevent overlap bugs (like names colliding with timezone offsets). 

To execute the layout verification test:
```bash
python3 test_layout.py
```
This runs assertions across all layout combinations (horizontal/vertical, seconds visible/hidden) and guarantees no text overlaps occur.

