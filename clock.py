import os
import sys
import json
import platform
import sqlite3
import threading
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import tkinter as tk
from tkinter import messagebox, ttk

# Configuration paths
CONFIG_FILE = os.path.join(os.path.expanduser('~'), '.world_clock_overlay.json')
DB_FILE = os.path.join(os.path.expanduser('~'), '.world_clock_work_tracker.db')

# Curated list of common timezones for the setup wizard dropdown
COMMON_ZONES = [
    ("Local System Time", "Local"),
    ("Venezuela (Caracas)", "America/Caracas"),
    ("Spain (Madrid)", "Europe/Madrid"),
    ("Saudi Arabia (Riyadh)", "Asia/Riyadh"),
    ("US Eastern (New York)", "America/New_York"),
    ("US Central (Chicago)", "America/Chicago"),
    ("US Pacific (Los Angeles)", "America/Los_Angeles"),
    ("United Kingdom (London)", "Europe/London"),
    ("Germany (Berlin)", "Europe/Berlin"),
    ("Japan (Tokyo)", "Asia/Tokyo"),
    ("India (Kolkata)", "Asia/Kolkata"),
    ("Australia (Sydney)", "Australia/Sydney"),
    ("UAE (Dubai)", "Asia/Dubai"),
    ("Argentina (Buenos Aires)", "America/Argentina/Buenos_Aires"),
    ("Colombia (Bogota)", "America/Bogota"),
    ("Mexico (Mexico City)", "America/Mexico_City"),
    ("Brazil (Sao Paulo)", "America/Sao_Paulo"),
    ("Singapore", "Asia/Singapore"),
    ("South Africa (Johannesburg)", "Africa/Johannesburg")
]

# Map zones to flag drawing codes
FLAG_MAP = {
    'Local': 'local',
    'America/Caracas': 'venezuela',
    'Europe/Madrid': 'spain',
    'Asia/Riyadh': 'ksa',
    'America/New_York': 'usa',
    'America/Chicago': 'usa',
    'America/Los_Angeles': 'usa',
    'Europe/London': 'uk',
    'Europe/Berlin': 'germany',
    'Asia/Tokyo': 'japan',
    'Asia/Kolkata': 'india',
    'Australia/Sydney': 'australia',
    'Asia/Dubai': 'uae',
    'America/Argentina/Buenos_Aires': 'argentina',
    'America/Bogota': 'colombia',
    'America/Mexico_City': 'mexico',
}

# Design Themes
THEMES = {
    'dark': {
        'bg': '#010101',
        'card_bg': '#16161a',
        'card_border': '#2d2d30',
        'text_main': '#ffffff',
        'text_muted': '#a0a0a5',
        'text_faded': '#68686d',  # 20%+ more faded than text_muted
        'accent': '#3a86ff'
    },
    'light': {
        'bg': '#010101',
        'card_bg': '#f4f4f7',
        'card_border': '#d1d1d6',
        'text_main': '#1c1c1e',
        'text_muted': '#636366',
        'text_faded': '#9a9aa0',  # 20%+ more faded than text_muted
        'accent': '#007aff'
    },
    'cyberpunk': {
        'bg': '#010101',
        'card_bg': '#0a0810',
        'card_border': '#ff007f',
        'text_main': '#00ffff',
        'text_muted': '#8b9bb4',
        'text_faded': '#58657a',  # 20%+ more faded than text_muted
        'accent': '#ff007f'
    },
    'nordic': {
        'bg': '#010101',
        'card_bg': '#2e3440',
        'card_border': '#4c566a',
        'text_main': '#d8dee9',
        'text_muted': '#9fa8b8',
        'text_faded': '#6d7787',  # 20%+ more faded than text_muted
        'accent': '#88c0d0'
    }
}

# Conditional imports for System Tray support
HAS_TRAY = False
try:
    from PIL import Image, ImageDraw
    import pystray
    from pystray import MenuItem as item
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

class WorldClockApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("World Clock Overlay")
        
        self.is_windows = platform.system() == 'Windows'
        
        # Load state / settings
        self.load_settings()
        
        # Initialize SQLite Work Tracker
        self.init_db()
        self.session_id = None
        self.session_start = datetime.now()
        self.start_work_session()
        self.db_save_counter = 0

        # If no clocks are configured (First run), show setup wizard
        if not self.settings.get('clocks'):
            self.root.withdraw()  # Hide main window during setup
            self.show_setup_wizard()
            self.root.mainloop()
            return

        # Setup main window
        self.setup_main_window()

    def setup_main_window(self):
        self.root.deiconify()  # Ensure window is visible
        self.root.overrideredirect(True)  # Frameless window
        self.root.attributes('-topmost', True)  # Always on top
        
        self.apply_transparency()
        
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        # Create Canvas
        self.canvas = tk.Canvas(
            self.root, 
            bg=self.get_theme()['bg'], 
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind events
        self.canvas.bind('<Button-1>', self.start_drag)
        self.canvas.bind('<B1-Motion>', self.do_drag)
        self.canvas.bind('<ButtonRelease-1>', self.stop_drag)
        self.root.bind('<Double-Button-1>', self.toggle_layout)
        
        # Create Right-Click Menu
        self.create_context_menu()
        
        # Place window
        self.restore_position()
        
        # Start updates
        self.update_clocks()
        
        # Start System Tray Icon
        if HAS_TRAY:
            self.tray_thread = threading.Thread(target=self.start_tray_icon, daemon=True)
            self.tray_thread.start()
            
        # Listen for window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

    # ==========================================================================
    # SQLite Work Tracker Implementation
    # ==========================================================================
    def init_db(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS work_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT,
                    end_time TEXT,
                    duration_seconds INTEGER
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            print("Failed to initialize database:", e)

    def start_work_session(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO work_sessions (start_time, end_time, duration_seconds) VALUES (?, NULL, 0)",
                (self.session_start.isoformat(),)
            )
            self.session_id = cursor.lastrowid
            conn.commit()
            conn.close()
        except Exception as e:
            print("Failed to start database session:", e)

    def update_work_session(self):
        if self.session_id is None:
            return
        try:
            now = datetime.now()
            duration = int((now - self.session_start).total_seconds())
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE work_sessions SET end_time = ?, duration_seconds = ? WHERE id = ?",
                (now.isoformat(), duration, self.session_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print("Failed to update database session:", e)

    def get_monthly_stats(self):
        try:
            today = date.today()
            month_str = today.strftime("%Y-%m")
            
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT start_time, duration_seconds FROM work_sessions WHERE start_time LIKE ?",
                (f"{month_str}%",)
            )
            sessions = cursor.fetchall()
            conn.close()
            
            unique_days = set()
            total_seconds = 0
            for start_time_str, duration in sessions:
                try:
                    day = start_time_str.split('T')[0]
                    unique_days.add(day)
                    total_seconds += duration
                except Exception:
                    pass
            
            # Add current live session seconds to the stats
            live_sec = int((datetime.now() - self.session_start).total_seconds())
            total_seconds += live_sec
            unique_days.add(today.isoformat())
            
            total_hours = total_seconds / 3600.0
            return len(unique_days), total_hours
        except Exception as e:
            print("Failed to load monthly stats:", e)
            return 0, 0.0

    # ==========================================================================
    # First-Run Setup Wizard Window
    # ==========================================================================
    def show_setup_wizard(self):
        wizard = tk.Toplevel(self.root)
        wizard.title("World Clock Setup")
        wizard.geometry("380x420")
        wizard.resizable(False, False)
        wizard.config(bg="#16161a")
        
        # Keep wizard on top
        wizard.attributes('-topmost', True)
        
        # Title
        tk.Label(
            wizard, 
            text="World Clock Setup", 
            fg="white", bg="#16161a", 
            font=("Outfit", 14, "bold")
        ).pack(pady=10)
        
        tk.Label(
            wizard,
            text="Clock 1 is set to your Local System Time.\nConfigure additional clocks below:",
            fg="#a0a0a5", bg="#16161a",
            font=("Outfit", 9),
            justify="center"
        ).pack(pady=5)

        # Dropdowns Frame
        dropdown_frame = tk.Frame(wizard, bg="#16161a")
        dropdown_frame.pack(pady=10, fill=tk.BOTH, expand=True)

        combos = []

        # We allow up to 4 additional clocks (total of 5)
        for i in range(4):
            lbl = tk.Label(
                dropdown_frame, 
                text=f"Clock {i+2} Timezone:", 
                fg="#a0a0a5", bg="#16161a", 
                font=("Outfit", 9, "bold")
            )
            lbl.grid(row=i, column=0, padx=10, pady=8, sticky="w")
            
            combo = ttk.Combobox(
                dropdown_frame, 
                values=[z[0] for z in COMMON_ZONES[1:]] + ["None"],
                state="readonly",
                width=24
            )
            # Default empty comboboxes to "None"
            combo.set("None")
            combo.grid(row=i, column=1, padx=10, pady=8)
            combos.append(combo)

        # Set default values for Clock 2 & 3 to Spain and Saudi Arabia for quick setup
        combos[0].set("Spain (Madrid)")
        combos[1].set("Saudi Arabia (Riyadh)")

        def save_setup():
            clocks = [
                {"tz": "Local", "name": "Local Time", "flag_code": "local"}
            ]
            
            for combo in combos:
                val = combo.get()
                if val != "None":
                    # Find corresponding timezone name
                    matched = [z for z in COMMON_ZONES if z[0] == val]
                    if matched:
                        tz_name = matched[0][1]
                        # Extract friendly name
                        friendly_name = val.split(' (')[0]
                        flag_code = FLAG_MAP.get(tz_name, 'generic')
                        clocks.append({
                            "tz": tz_name,
                            "name": friendly_name,
                            "flag_code": flag_code
                        })
            
            self.settings['clocks'] = clocks
            self.save_settings()
            wizard.destroy()
            self.setup_main_window()

        # Save Button
        tk.Button(
            wizard,
            text="Save and Launch",
            command=save_setup,
            bg="#3a86ff", fg="white",
            activebackground="#2563eb", activeforeground="white",
            font=("Outfit", 10, "bold"),
            relief="flat",
            bd=0,
            padx=20, pady=8
        ).pack(pady=15)

        # Exit wizard cleanly
        wizard.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))

    # ==========================================================================
    # Settings Management
    # ==========================================================================
    def load_settings(self):
        default_settings = {
            'layout': 'horizontal',
            'format': '12h',
            'show_seconds': True,
            'opacity': 0.85,
            'theme': 'dark',
            'clocks': [],  # Saved clocks list
            'x': None,
            'y': None
        }
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.settings = {**default_settings, **json.load(f)}
            except Exception:
                self.settings = default_settings
        else:
            self.settings = default_settings

    def save_settings(self):
        try:
            if hasattr(self, 'root') and self.root.winfo_exists():
                self.settings['x'] = self.root.winfo_x()
                self.settings['y'] = self.root.winfo_y()
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.settings, f)
        except Exception as e:
            print("Failed to save settings:", e)

    def get_theme(self):
        return THEMES.get(self.settings['theme'], THEMES['dark'])

    def apply_transparency(self):
        theme = self.get_theme()
        self.root.config(bg=theme['bg'])
        
        if self.is_windows:
            self.root.wm_attributes("-transparentcolor", theme['bg'])
            self.root.attributes('-alpha', self.settings['opacity'])
        else:
            self.root.attributes('-alpha', self.settings['opacity'])

    # ==========================================================================
    # Window Layout Positioning
    # ==========================================================================
    def get_current_monitor_workarea(self):
        if self.is_windows:
            try:
                import ctypes
                
                class RECT(ctypes.Structure):
                    _fields_ = [
                        ('left', ctypes.c_long),
                        ('top', ctypes.c_long),
                        ('right', ctypes.c_long),
                        ('bottom', ctypes.c_long)
                    ]
                    
                class MONITORINFO(ctypes.Structure):
                    _fields_ = [
                        ('cbSize', ctypes.c_ulong),
                        ('rcMonitor', RECT),
                        ('rcWork', RECT),
                        ('dwFlags', ctypes.c_ulong)
                    ]
                
                user32 = ctypes.windll.user32
                hwnd = self.root.winfo_id()
                MONITOR_DEFAULTTONEAREST = 2
                monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
                
                info = MONITORINFO()
                info.cbSize = ctypes.sizeof(MONITORINFO)
                if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                    work = info.rcWork
                    return work.left, work.top, work.right, work.bottom
            except Exception as e:
                print("Failed to get monitor bounds:", e)
                
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        return 0, 0, screen_w, screen_h

    def constrain_coordinates(self, x, y, w, h):
        left, top, right, bottom = self.get_current_monitor_workarea()
        
        if x < left:
            x = left
        elif x + w > right:
            x = right - w
            
        if y < top:
            y = top
        elif y + h > bottom:
            y = bottom - h
            
        return x, y

    def restore_position(self):
        w, h = self.get_window_size()
        x = self.settings['x']
        y = self.settings['y']
        
        if x is None or y is None:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            x = screen_w - w - 40
            y = screen_h - h - 80
            
        x, y = self.constrain_coordinates(x, y, w, h)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def get_window_size(self):
        show_sec = self.settings['show_seconds']
        N = len(self.settings.get('clocks', []))
        if N == 0: N = 3
        
        if self.settings['layout'] == 'horizontal':
            w = N * 190 + 20 if show_sec else N * 180 + 20
            h = 125  # Space for cards + status bar at the bottom
        else:
            w = 200
            card_h = 75 if show_sec else 65
            h = N * (card_h + 10) + 40  # Cards + status bar padding
        return w, h

    def apply_layout_size(self):
        w_old = self.root.winfo_width()
        h_old = self.root.winfo_height()
        w_new, h_new = self.get_window_size()
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        
        left, top, right, bottom = self.get_current_monitor_workarea()
        cx = x + w_old / 2
        cy = y + h_old / 2
        mx = (left + right) / 2
        my = (top + bottom) / 2
        
        h_anchor = 'right' if cx > mx else 'left'
        v_anchor = 'bottom' if cy > my else 'top'
        
        if h_anchor == 'right':
            x_new = (x + w_old) - w_new
        else:
            x_new = x
            
        if v_anchor == 'bottom':
            y_new = (y + h_old) - h_new
        else:
            y_new = y
            
        x_new, y_new = self.constrain_coordinates(x_new, y_new, w_new, h_new)
        self.root.geometry(f"{w_new}x{h_new}+{x_new}+{y_new}")

    # ==========================================================================
    # Mouse Drag Handlers & Opacity Feedback
    # ==========================================================================
    def start_drag(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        # Drop opacity to 30% to visually indicate moving action
        self.root.attributes('-alpha', 0.3)

    def stop_drag(self, event):
        self.apply_transparency()

    def do_drag(self, event):
        x = self.root.winfo_x() + (event.x - self.drag_start_x)
        y = self.root.winfo_y() + (event.y - self.drag_start_y)
        w, h = self.get_window_size()
        x, y = self.constrain_coordinates(x, y, w, h)
        self.root.geometry(f"+{x}+{y}")

    # ==========================================================================
    # Rendering & Vector Flag Drawings
    # ==========================================================================
    def draw_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1+r, y1,
            x2-r, y1,
            x2, y1,
            x2, y1+r,
            x2, y2-r,
            x2, y2,
            x2-r, y2,
            x1+r, y2,
            x1, y2,
            x1, y2-r,
            x1, y1+r,
            x1, y1
        ]
        return self.canvas.create_polygon(points, **kwargs, smooth=True)

    def draw_flag(self, flag_code, x, y):
        w, h = 16, 10
        if flag_code == 'local':
            # Draw clock logo for local system time
            self.canvas.create_oval(x, y, x+w, y+h, fill='#3a86ff', outline='')
            self.canvas.create_line(x+8, y+5, x+8, y+2, fill='white', width=1)
            self.canvas.create_line(x+8, y+5, x+12, y+5, fill='white', width=1)
        elif flag_code == 'venezuela':
            self.canvas.create_rectangle(x, y, x+w, y+3, fill='#ffcc00', outline='')
            self.canvas.create_rectangle(x, y+3, x+w, y+6, fill='#00247d', outline='')
            self.canvas.create_rectangle(x, y+6, x+w, y+h, fill='#cf142b', outline='')
        elif flag_code == 'ksa':
            self.canvas.create_rectangle(x, y, x+w, y+h, fill='#006c35', outline='')
            self.canvas.create_line(x+3, y+7, x+w-3, y+7, fill='white', width=1)
        elif flag_code == 'spain':
            self.canvas.create_rectangle(x, y, x+w, y+2, fill='#aa151b', outline='')
            self.canvas.create_rectangle(x, y+2, x+w, y+8, fill='#f1bf00', outline='')
            self.canvas.create_rectangle(x, y+8, x+w, y+h, fill='#aa151b', outline='')
        elif flag_code == 'usa':
            for line in range(5):
                color = '#b22234' if line % 2 == 0 else 'white'
                self.canvas.create_rectangle(x, y + line * 2, x + w, y + (line + 1) * 2, fill=color, outline='')
            self.canvas.create_rectangle(x, y, x + 8, y + 6, fill='#3c3b6e', outline='')
        elif flag_code == 'uk':
            self.canvas.create_rectangle(x, y, x + w, y + h, fill='#00247d', outline='')
            self.canvas.create_line(x, y, x + w, y + h, fill='white', width=2)
            self.canvas.create_line(x, y + h, x + w, y, fill='white', width=2)
            self.canvas.create_line(x, y + h/2, x + w, y + h/2, fill='white', width=2)
            self.canvas.create_line(x + w/2, y, x + w/2, y + h, fill='white', width=2)
            self.canvas.create_line(x, y + h/2, x + w, y + h/2, fill='#cf142b', width=1)
            self.canvas.create_line(x + w/2, y, x + w/2, y + h, fill='#cf142b', width=1)
        elif flag_code == 'japan':
            self.canvas.create_rectangle(x, y, x + w, y + h, fill='white', outline='#d1d1d6')
            self.canvas.create_oval(x + 5, y + 2, x + 11, y + 8, fill='#bc002d', outline='')
        elif flag_code == 'germany':
            self.canvas.create_rectangle(x, y, x + w, y + 3, fill='black', outline='')
            self.canvas.create_rectangle(x, y + 3, x + w, y + 6, fill='#dd0000', outline='')
            self.canvas.create_rectangle(x, y + 6, x + w, y + h, fill='#ffcc00', outline='')
        else:
            # Generic globe flag drawing
            self.canvas.create_oval(x, y, x + w, y + h, fill='#1b365d', outline='#3a86ff')

    def get_offset_diff(self, target_tz_name):
        if target_tz_name == 'Local':
            return "Local"
        try:
            now = datetime.now()
            local_offset_sec = -now.astimezone().utcoffset().total_seconds()
            local_offset_min = -int(local_offset_sec / 60)
            
            target_tz = ZoneInfo(target_tz_name)
            target_offset_sec = now.astimezone(target_tz).utcoffset().total_seconds()
            target_offset_min = int(target_offset_sec / 60)
            
            diff_min = target_offset_min - (-local_offset_min)
            diff_hours = diff_min / 60
            
            if diff_hours == 0:
                return "Local"
            
            sign = "+" if diff_hours > 0 else ""
            if diff_hours.is_integer():
                return f"{sign}{int(diff_hours)}h"
            return f"{sign}{diff_hours:.1f}h"
        except Exception:
            return ""

    def get_local_flag_code(self):
        try:
            # First, check if the system timezone name matches any flag directly
            local_tz = datetime.now().astimezone().tzinfo
            tz_name = str(local_tz)
            if tz_name in FLAG_MAP:
                return FLAG_MAP[tz_name]
                
            # Fallback: estimate via UTC offset (extremely robust)
            now = datetime.now()
            offset_sec = now.astimezone().utcoffset().total_seconds()
            offset_hours = offset_sec / 3600.0
            
            if offset_hours == -4.0:
                return 'venezuela'
            elif offset_hours == 3.0:
                return 'ksa'
            elif offset_hours in [1.0, 2.0]:
                return 'spain'
            elif offset_hours in [-5.0, -6.0, -7.0, -8.0]:
                return 'usa'
        except Exception:
            pass
        return 'local'

    def create_text_with_shadow(self, x, y, text, fill, font, anchor='w'):
        # Choose a shadow color based on the text color.
        # Draw a dark shadow under light text, or a light outline under dark text.
        is_dark_text = fill.lower() in ['#1c1c1e', '#2e3440', '#636366', '#9a9aa0', 'black', '#000000', '#6d7787', '#58657a']
        shadow_color = '#ffffff' if is_dark_text else '#000000'
        
        # 1px offset shadow
        self.canvas.create_text(
            x + 1, y + 1,
            text=text,
            fill=shadow_color,
            font=font,
            anchor=anchor
        )
        return self.canvas.create_text(
            x, y,
            text=text,
            fill=fill,
            font=font,
            anchor=anchor
        )

    def update_clocks(self):
        self.canvas.delete("all")
        theme = self.get_theme()
        
        # Save session to SQLite database once every 60 seconds (300 updates of 200ms)
        self.db_save_counter += 1
        if self.db_save_counter >= 300:
            self.db_save_counter = 0
            self.update_work_session()
            
        w, h = self.get_window_size()
        self.canvas.config(bg=theme['bg'])
        
        layout = self.settings['layout']
        show_sec = self.settings['show_seconds']
        use_24h = self.settings['format'] == '24h'
        
        clocks = self.settings.get('clocks', [])
        
        # Draw Clock Cards
        for i, clock_info in enumerate(clocks):
            tz_name = clock_info['tz']
            friendly_name = clock_info['name']
            flag_code = clock_info['flag_code']
            
            # Dynamically override the generic 'local' clock face flag with country flag
            if flag_code == 'local':
                flag_code = self.get_local_flag_code()
            
            # Calculate dynamic card coordinates
            if layout == 'horizontal':
                card_w = 180 if show_sec else 170
                x1 = 10 + i * (card_w + 10)
                y1 = 10
                x2 = x1 + card_w
                y2 = h - 35  # Reserved space for bottom status bar
            else:
                card_h = 75 if show_sec else 65
                x1 = 10
                y1 = 10 + i * (card_h + 10)
                x2 = w - 10
                y2 = y1 + card_h
                
            self.draw_rounded_rect(
                x1, y1, x2, y2, 8, 
                fill=theme['card_bg'], 
                outline=theme['card_border'], 
                width=1
            )
            
            # Draw Flag
            flag_x = x1 + 10
            flag_y = y1 + 10
            self.draw_flag(flag_code, flag_x, flag_y)
            
            # Label
            self.create_text_with_shadow(
                flag_x + 22, flag_y + 5,
                text=friendly_name,
                fill=theme['text_muted'],
                font=('Outfit', 9, 'bold'),
                anchor='w'
            )
            
            # Time Offset
            offset = self.get_offset_diff(tz_name)
            if offset:
                self.create_text_with_shadow(
                    x2 - 10, flag_y + 5,
                    text=offset,
                    fill=theme['accent'],
                    font=('Outfit', 8, 'bold'),
                    anchor='e'
                )
                
            # Time Formatting
            try:
                if tz_name == 'Local':
                    time_now = datetime.now()
                else:
                    time_now = datetime.now(ZoneInfo(tz_name))
                
                if use_24h:
                    time_fmt = "%H:%M:%S" if show_sec else "%H:%M"
                    time_str = time_now.strftime(time_fmt)
                    period_str = ""
                else:
                    time_fmt = "%I:%M:%S" if show_sec else "%I:%M"
                    time_str = time_now.strftime(time_fmt).lstrip('0')
                    period_str = time_now.strftime("%p")
                    
                # Draw Time
                time_y = y1 + 35
                time_font_size = 14 if show_sec else 16
                time_text_id = self.create_text_with_shadow(
                    x1 + 10, time_y,
                    text=time_str,
                    fill=theme['text_main'],
                    font=('Courier New', time_font_size, 'bold') if self.is_windows else ('Outfit', time_font_size, 'bold'),
                    anchor='w'
                )
                
                if period_str:
                    time_bbox = self.canvas.bbox(time_text_id)
                    period_x = time_bbox[2] + 4
                    self.create_text_with_shadow(
                        period_x, time_y + 2,
                        text=period_str.lower(),
                        fill=theme['accent'],
                        font=('Outfit', 8, 'bold'),
                        anchor='w'
                    )
                    
                # Draw Date
                date_str = time_now.strftime("%a, %b %d")
                self.create_text_with_shadow(
                    x1 + 10, y2 - 12,
                    text=date_str,
                    fill=theme['text_muted'],
                    font=('Outfit', 8),
                    anchor='w'
                )
            except Exception:
                self.create_text_with_shadow(
                    x1 + 10, y1 + 35,
                    text="Error",
                    fill='red',
                    font=('Outfit', 10),
                    anchor='w'
                )

        # Render bottom Status Bar (Session & Work Stats)
        elapsed_delta = datetime.now() - self.session_start
        elapsed_hours, remainder = divmod(elapsed_delta.seconds, 3600)
        elapsed_minutes, elapsed_seconds = divmod(remainder, 60)
        elapsed_str = f"{elapsed_hours:02d}:{elapsed_minutes:02d}:{elapsed_seconds:02d}"

        # Fetch monthly statistics
        days_worked, hours_worked = self.get_monthly_stats()
        current_month = datetime.now().strftime("%B")
        
        status_text = f"⏱️ Work: {elapsed_str} | {current_month}: {days_worked} days, {hours_worked:.1f} hrs"
        
        # Position status bar at the bottom center
        status_y = h - 14
        self.create_text_with_shadow(
            w / 2, status_y,
            text=status_text,
            fill=theme['text_faded'],
            font=('Outfit', 8, 'bold'),
            anchor='center'
        )
                
        self.root.after(200, self.update_clocks)

    # ==========================================================================
    # Context Menu & Tray Actions
    # ==========================================================================
    def create_context_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0, bg='#1c1c1e', fg='white', activebackground='#3a86ff')
        
        self.menu.add_command(label="Toggle Layout (Double-Click)", command=self.toggle_layout)
        self.menu.add_command(label="Reset Clocks Setup Wizard", command=self.reset_clocks)
        self.menu.add_separator()
        
        format_menu = tk.Menu(self.menu, tearoff=0, bg='#1c1c1e', fg='white', activebackground='#3a86ff')
        format_menu.add_command(label="12-Hour (AM/PM)", command=lambda: self.change_format('12h'))
        format_menu.add_command(label="24-Hour", command=lambda: self.change_format('24h'))
        self.menu.add_cascade(label="Time Format", menu=format_menu)
        
        self.menu.add_command(label="Toggle Seconds", command=self.toggle_seconds)
        
        opacity_menu = tk.Menu(self.menu, tearoff=0, bg='#1c1c1e', fg='white', activebackground='#3a86ff')
        for op in [0.3, 0.5, 0.7, 0.85, 1.0]:
            opacity_menu.add_command(
                label=f"{int(op*100)}%", 
                command=lambda o=op: self.change_opacity(o)
            )
        self.menu.add_cascade(label="Translucency", menu=opacity_menu)
        
        theme_menu = tk.Menu(self.menu, tearoff=0, bg='#1c1c1e', fg='white', activebackground='#3a86ff')
        theme_menu.add_command(label="Frosted Dark", command=lambda: self.change_theme('dark'))
        theme_menu.add_command(label="Frosted Light", command=lambda: self.change_theme('light'))
        theme_menu.add_command(label="Cyberpunk Neon", command=lambda: self.change_theme('cyberpunk'))
        theme_menu.add_command(label="Nordic Frost", command=lambda: self.change_theme('nordic'))
        self.menu.add_cascade(label="Themes", menu=theme_menu)
        
        self.menu.add_separator()
        self.menu.add_command(label="Exit App", command=self.on_exit)
        
        if platform.system() == 'Darwin':
            self.canvas.bind('<Button-2>', self.show_context_menu)
        else:
            self.canvas.bind('<Button-3>', self.show_context_menu)

    def show_context_menu(self, event):
        self.menu.post(event.x_root, event.y_root)

    def toggle_layout(self, event=None):
        self.settings['layout'] = 'vertical' if self.settings['layout'] == 'horizontal' else 'horizontal'
        self.apply_layout_size()
        self.update_clocks()
        self.save_settings()

    def change_format(self, fmt):
        self.settings['format'] = fmt
        self.update_clocks()
        self.save_settings()

    def toggle_seconds(self):
        self.settings['show_seconds'] = not self.settings['show_seconds']
        self.apply_layout_size()
        self.update_clocks()
        self.save_settings()

    def change_opacity(self, opacity):
        self.settings['opacity'] = opacity
        self.apply_transparency()
        self.save_settings()

    def change_theme(self, theme_name):
        self.settings['theme'] = theme_name
        self.apply_transparency()
        self.update_clocks()
        self.save_settings()

    def reset_clocks(self):
        # Clear clocks configuration and restart wizard
        self.settings['clocks'] = []
        self.save_settings()
        self.root.withdraw()
        if HAS_TRAY and hasattr(self, 'tray_icon'):
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.show_setup_wizard()

    def start_tray_icon(self):
        def on_toggle_layout(icon, item):
            self.root.after(0, self.toggle_layout)
            
        def on_toggle_seconds(icon, item):
            self.root.after(0, self.toggle_seconds)
            
        def on_change_format(icon, item, fmt):
            self.root.after(0, lambda: self.change_format(fmt))
            
        def on_change_theme(icon, item, theme_name):
            self.root.after(0, lambda: self.change_theme(theme_name))
            
        def on_change_opacity(icon, item, val):
            self.root.after(0, lambda: self.change_opacity(val))
            
        def on_exit(icon, item):
            icon.stop()
            self.root.after(0, self.on_exit)

        menu = pystray.Menu(
            item('Toggle Layout', on_toggle_layout),
            item('Toggle Seconds', on_toggle_seconds),
            pystray.Menu.SEPARATOR,
            item('Time Format', pystray.Menu(
                item('12-Hour (AM/PM)', lambda icon, item: on_change_format(icon, item, '12h')),
                item('24-Hour', lambda icon, item: on_change_format(icon, item, '24h'))
            )),
            item('Translucency', pystray.Menu(
                item('30%', lambda icon, item: on_change_opacity(icon, item, 0.3)),
                item('50%', lambda icon, item: on_change_opacity(icon, item, 0.5)),
                item('70%', lambda icon, item: on_change_opacity(icon, item, 0.7)),
                item('85%', lambda icon, item: on_change_opacity(icon, item, 0.85)),
                item('100%', lambda icon, item: on_change_opacity(icon, item, 1.0))
            )),
            item('Themes', pystray.Menu(
                item('Frosted Dark', lambda icon, item: on_change_theme(icon, item, 'dark')),
                item('Frosted Light', lambda icon, item: on_change_theme(icon, item, 'light')),
                item('Cyberpunk Neon', lambda icon, item: on_change_theme(icon, item, 'cyberpunk')),
                item('Nordic Frost', lambda icon, item: on_change_theme(icon, item, 'nordic'))
            )),
            pystray.Menu.SEPARATOR,
            item('Exit App', on_exit)
        )

        icon_img = self.create_tray_icon_image()
        self.tray_icon = pystray.Icon("world_clock_overlay", icon_img, "World Clock", menu)
        self.tray_icon.run()

    def create_tray_icon_image(self):
        image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        theme = self.get_theme()
        accent_color = theme['accent']
        
        draw.ellipse((4, 4, 60, 60), outline=accent_color, width=5)
        draw.line((32, 32, 32, 16), fill='white', width=5)
        draw.line((32, 32, 48, 32), fill='white', width=5)
        return image

    def on_exit(self):
        self.update_work_session()
        self.save_settings()
        if HAS_TRAY and hasattr(self, 'tray_icon'):
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = WorldClockApp()
    app.root.mainloop()
