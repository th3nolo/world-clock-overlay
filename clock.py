import os
import sys
import json
import time
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

# Space must be HELD this long over the overlay to pause/resume. Typing in
# another app taps space for ~0.1s; the key state is global, so a quick tap
# must never count even when the pointer is parked over the overlay.
PAUSE_HOLD_SEC = 0.5

# After a tray-click peek, hide again this quickly if the mouse never
# arrives on the overlay (leaving after a hover always hides immediately)
PEEK_TIMEOUT_SEC = 2.5

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

# Supported translucency levels (right-click menu, tray menu, scroll wheel)
OPACITY_LEVELS = [0.3, 0.5, 0.7, 0.85, 1.0]

# Design Themes.
# Window '-alpha' dims text and panel by the same amount, so over a light
# desktop the panel washes out toward white. text_muted/text_faded must stay
# near-white (near-black for the light theme) to keep contrast through that
# blend, and text_shadow is drawn 1px behind every canvas text for edge
# contrast against whatever bleeds through.
THEMES = {
    'dark': {
        'bg': '#010101',
        'card_bg': '#101014',
        'card_border': '#2c2c30',
        'divider': '#26262b',
        'text_main': '#fafafa',
        'text_muted': '#e0e0e4',
        'text_faded': '#cdcdd4',
        'text_shadow': '#000000',
        'accent': '#6ea8ff',
        'sun': '#ffcf6b',
        'moon': '#9db4ff'
    },
    'light': {
        'bg': '#010101',
        'card_bg': '#f4f4f7',
        'card_border': '#d1d1d6',
        'divider': '#e2e2e7',
        'text_main': '#1c1c1e',
        'text_muted': '#3e3e46',
        'text_faded': '#5a5a64',
        'text_shadow': '#ffffff',
        'accent': '#007aff',
        'sun': '#d9940e',
        'moon': '#5b76d8'
    },
    'cyberpunk': {
        'bg': '#010101',
        'card_bg': '#0a0810',
        'card_border': '#ff007f',
        'divider': '#2a1230',
        'text_main': '#00ffff',
        'text_muted': '#e3e7ee',
        'text_faded': '#d3d9e4',
        'text_shadow': '#000000',
        'accent': '#ff007f',
        'sun': '#ffd166',
        'moon': '#9db4ff'
    },
    'nordic': {
        'bg': '#010101',
        'card_bg': '#2e3440',
        'card_border': '#4c566a',
        'divider': '#3b4252',
        'text_main': '#eceff4',
        'text_muted': '#dbe1ea',
        'text_faded': '#c8d0dc',
        'text_shadow': '#000000',
        'accent': '#88c0d0',
        'sun': '#ebcb8b',
        'moon': '#81a1c1'
    }
}

class PopupMenu:
    """Theme-drawn replacement for tk.Menu popups. Native Windows menus keep
    a white system frame and separators that ignore all color options, so
    the popup is a frameless Toplevel styled entirely from the active theme."""

    CASCADE_DELAY_MS = 250

    def __init__(self, app, items, x, y, parent=None):
        self.app = app
        self.parent = parent
        self.child = None
        self.pending_child = None
        self.closed = False
        # One shared window list per menu tree (root popup + open submenus)
        self.windows = [] if parent is None else parent.windows
        self.theme = theme = app.get_theme()

        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.attributes('-topmost', True)
        self.windows.append(self.win)

        body = tk.Frame(
            self.win, bg=theme['card_bg'],
            highlightthickness=1, highlightbackground=theme['card_border']
        )
        body.pack(fill=tk.BOTH, expand=True)

        for item in items:
            if item[0] == 'separator':
                tk.Frame(body, bg=theme['divider'], height=1).pack(
                    fill=tk.X, padx=8, pady=4)
                continue
            kind, label = item[0], item[1]
            lbl = tk.Label(
                body, text=label, anchor='w', justify='left',
                bg=theme['card_bg'], fg=theme['text_muted'],
                font=('Outfit', 9), padx=14, pady=5
            )
            if kind == 'cascade':
                lbl.config(text=f"{label}      ▸")
                lbl.bind('<Enter>', lambda e, l=lbl, sub=item[2]: self.on_cascade_enter(l, sub))
                lbl.bind('<Button-1>', lambda e, l=lbl, sub=item[2]: self.open_child(l, sub))
            else:
                lbl.bind('<Enter>', lambda e, l=lbl: self.on_command_enter(l))
                lbl.bind('<Button-1>', lambda e, cb=item[2]: self.invoke(cb))
            lbl.bind('<Leave>', lambda e, l=lbl: self.highlight(l, False))
            lbl.pack(fill=tk.X)

        self.win.update_idletasks()
        self.place(x, y)

        root_popup = self.root_popup()
        self.win.bind('<Escape>', lambda e: root_popup.close_all())
        self.win.bind('<FocusOut>', lambda e: root_popup.schedule_focus_check())
        if parent is None:
            self.win.focus_force()

    def root_popup(self):
        p = self
        while p.parent is not None:
            p = p.parent
        return p

    def place(self, x, y):
        w = self.win.winfo_reqwidth()
        h = self.win.winfo_reqheight()
        left, top, right, bottom = self.app.get_current_monitor_workarea()
        x = max(left, min(x, right - w))
        y = max(top, min(y, bottom - h))
        self.win.geometry(f'+{int(x)}+{int(y)}')

    def highlight(self, lbl, on):
        if on:
            lbl.config(bg=self.theme['accent'],
                       fg=self.app.contrast_text(self.theme['accent']))
        else:
            lbl.config(bg=self.theme['card_bg'], fg=self.theme['text_muted'])

    def on_command_enter(self, lbl):
        self.highlight(lbl, True)
        self.cancel_pending()
        self.close_child()

    def on_cascade_enter(self, lbl, sub):
        self.highlight(lbl, True)
        self.cancel_pending()
        self.pending_child = self.win.after(
            self.CASCADE_DELAY_MS, lambda: self.open_child(lbl, sub))

    def cancel_pending(self):
        if self.pending_child:
            self.win.after_cancel(self.pending_child)
            self.pending_child = None

    def open_child(self, lbl, sub):
        self.cancel_pending()
        self.close_child()
        x = self.win.winfo_rootx() + self.win.winfo_width() - 4
        y = lbl.winfo_rooty() - 5
        self.child = PopupMenu(self.app, sub, x, y, parent=self)

    def close_child(self):
        if self.child:
            self.child.destroy_tree()
            self.child = None

    def invoke(self, callback):
        self.root_popup().close_all()
        callback()

    def destroy_tree(self):
        # Destroy this popup and its submenus without touching the parent
        self.closed = True
        self.cancel_pending()
        self.close_child()
        try:
            self.windows.remove(self.win)
        except ValueError:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass

    def close_all(self):
        root = self.root_popup()
        if root.closed:
            return
        root.destroy_tree()
        if self.app.context_popup is root:
            self.app.context_popup = None

    def schedule_focus_check(self):
        self.win.after(60, self.focus_check)

    def focus_check(self):
        # Close when focus leaves the menu tree (click on the desktop,
        # another app, or the overlay itself)
        if self.closed:
            return
        try:
            focused = self.win.focus_get()
        except Exception:
            focused = None
        if focused is None or focused.winfo_toplevel() not in self.windows:
            self.close_all()


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
        self.paused = False
        self.paused_elapsed_str = "00:00:00"
        self.space_hold_start = None
        self.space_toggled = False
        self.pause_btn_bbox = None  # screen hit-area of the timer text
        self.press_on_pause = False
        self.drag_moved = False
        self.hidden = False         # overlay withdrawn, tray icon remains
        self.peeking = False        # shown temporarily until the mouse leaves
        self.peek_hovered = False
        self.peek_start = 0.0
        self.h_hold_start = None    # hold H over the overlay to hide it
        self._tray_click_after = None
        self.tray_tooltip_counter = 9  # first refresh right after startup
        self.stats_cache = None  # (month, today, unique_days, base_seconds, today_seconds)

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

        # Scroll wheel over the overlay steps translucency up/down
        self.root.bind('<MouseWheel>', self.on_mouse_wheel)  # Windows / macOS
        self.root.bind('<Button-4>', self.on_mouse_wheel)    # X11 scroll up
        self.root.bind('<Button-5>', self.on_mouse_wheel)    # X11 scroll down

        # Pause-button clicks are hit-tested by coordinates in stop_drag:
        # canvas item events are unreliable here because the 200ms redraw
        # deletes and recreates every item, dropping mid-click events
        self.canvas.bind('<Motion>', self.on_canvas_motion)

        # Create Right-Click Menu
        self.create_context_menu()
        
        # Place window
        self.restore_position()
        
        # Start updates (force_redraw cancels any pending tick, so re-entering
        # setup via the wizard never leaves a duplicate redraw loop behind)
        self.force_redraw()

        # Space over the overlay pauses/resumes the work timer (cancel any
        # pending poll first for the same wizard re-entry reason)
        if getattr(self, '_poll_after', None) is not None:
            self.root.after_cancel(self._poll_after)
        self.poll_pause_hotkey()

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

    def refresh_monthly_stats(self):
        # Sum only PAST sessions: the live session row is excluded here and
        # its seconds are added at display time, so it is never counted twice.
        # Each session is clipped to today's [00:00, 24:00) for the today
        # total, so an overnight session can never push one day past 24h.
        month_str = date.today().strftime("%Y-%m")
        today_str = date.today().isoformat()
        day_start = datetime.combine(date.today(), datetime.min.time())
        day_end = day_start + timedelta(days=1)
        unique_days = set()
        base_seconds = 0
        today_seconds = 0
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT start_time, end_time, duration_seconds FROM work_sessions "
                "WHERE start_time LIKE ? AND id != ?",
                (f"{month_str}%", self.session_id if self.session_id is not None else -1)
            )
            sessions = cursor.fetchall()
            conn.close()

            for start_str, end_str, duration in sessions:
                try:
                    unique_days.add(start_str.split('T')[0])
                    base_seconds += duration or 0
                    start_dt = datetime.fromisoformat(start_str)
                    end_dt = (datetime.fromisoformat(end_str) if end_str
                              else start_dt + timedelta(seconds=duration or 0))
                    overlap = min(end_dt, day_end) - max(start_dt, day_start)
                    today_seconds += max(0, int(overlap.total_seconds()))
                except Exception:
                    pass
        except Exception as e:
            print("Failed to load monthly stats:", e)
        self.stats_cache = (month_str, today_str, unique_days, base_seconds, today_seconds)

    def get_monthly_stats(self):
        today = date.today()
        if (self.stats_cache is None
                or self.stats_cache[0] != today.strftime("%Y-%m")
                or self.stats_cache[1] != today.isoformat()):
            self.refresh_monthly_stats()
        _, _, unique_days, base_seconds, today_base = self.stats_cache

        live_sec = 0
        live_today = 0
        if not self.paused:
            now = datetime.now()
            day_start = datetime.combine(today, datetime.min.time())
            live_sec = int((now - self.session_start).total_seconds())
            live_today = int((now - max(self.session_start, day_start)).total_seconds())

        days = set(unique_days)
        # While paused, today only counts as a worked day if work was logged
        if not self.paused or today_base > 0:
            days.add(today.isoformat())
        total_hours = (base_seconds + live_sec) / 3600.0
        today_hours = (today_base + live_today) / 3600.0
        return len(days), total_hours, today_hours

    def toggle_pause(self):
        if self.paused:
            self.resume_work()
        else:
            self.pause_work()
        self.force_redraw()  # show the new state now, not at the next tick

    def pause_work(self):
        # Close the live session row; paused time never lands in the DB
        self.update_work_session()
        elapsed = int((datetime.now() - self.session_start).total_seconds())
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self.paused_elapsed_str = f"{h:02d}:{m:02d}:{s:02d}"
        self.session_id = None
        self.paused = True
        self.refresh_monthly_stats()  # the closed session now counts as past

    def resume_work(self):
        self.session_start = datetime.now()
        self.start_work_session()
        self.paused = False

    def is_over_pause_btn(self, x, y):
        b = self.pause_btn_bbox
        return b is not None and b[0] <= x <= b[2] and b[1] <= y <= b[3]

    def on_canvas_motion(self, event):
        self.canvas.config(
            cursor='hand2' if self.is_over_pause_btn(event.x, event.y) else '')

    def force_redraw(self):
        # Repaint immediately instead of waiting out the 200ms tick
        if getattr(self, '_redraw_after', None) is not None:
            self.root.after_cancel(self._redraw_after)
        self.update_clocks()

    def is_key_down(self, vk):
        # The frameless overlay never receives keyboard focus, so normal key
        # bindings would never fire; read the async key state instead
        try:
            import ctypes
            return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
        except Exception:
            return False

    def is_space_down(self):
        return self.is_key_down(0x20)

    def is_h_down(self):
        return self.is_key_down(0x48)

    def poll_pause_hotkey(self):
        # A withdrawn window still reports stale geometry, so hover-driven
        # hotkeys must be dead while hidden
        over = not self.hidden and self.is_pointer_over_window()

        # Space held over the overlay: pause/resume
        if self.is_space_down() and over:
            if self.space_hold_start is None:
                self.space_hold_start = time.monotonic()
            elif (not self.space_toggled
                  and time.monotonic() - self.space_hold_start >= PAUSE_HOLD_SEC):
                self.toggle_pause()
                self.space_toggled = True  # one toggle per hold
        else:
            self.space_hold_start = None
            self.space_toggled = False

        # H held over the overlay: hide to tray; the window fades out
        # during the hold so the gesture is visible while it arms
        if self.is_h_down() and over:
            if self.h_hold_start is None:
                self.h_hold_start = time.monotonic()
            frac = min(1.0, (time.monotonic() - self.h_hold_start) / PAUSE_HOLD_SEC)
            self.root.attributes(
                '-alpha', self.settings['opacity'] * (1 - frac) + 0.05 * frac)
            if frac >= 1.0:
                self.h_hold_start = None
                self.hide_overlay()
        elif self.h_hold_start is not None:
            self.h_hold_start = None
            self.apply_transparency()  # released early: restore opacity

        self.draw_hold_bar()
        # Animate at ~60fps during a hold, sample lazily otherwise
        holding = self.space_hold_start is not None or self.h_hold_start is not None
        interval = 16 if holding else 50
        self._poll_after = self.root.after(interval, self.poll_pause_hotkey)

    # ==========================================================================
    # Hide to Tray / Peek
    # ==========================================================================
    def hide_overlay(self):
        if not HAS_TRAY:
            return  # without a tray icon there would be no way back
        self.hidden = True
        self.peeking = False
        self.root.withdraw()
        self.apply_transparency()  # reset any mid-fade alpha for the next show

    def show_overlay(self, peek=False):
        self.hidden = False
        self.root.deiconify()
        self.root.attributes('-topmost', True)
        self.root.lift()
        self.apply_transparency()
        self.peeking = peek
        if peek:
            self.peek_hovered = False
            self.peek_start = time.monotonic()
            self.peek_watch()

    def peek_watch(self):
        # Peek lifecycle: stay visible while the mouse is over the overlay,
        # hide once it leaves (or after 6s if it never arrives)
        if not self.peeking:
            return
        over = self.is_pointer_over_window()
        if over:
            self.peek_hovered = True
        left_after_hover = self.peek_hovered and not over
        never_arrived = (not self.peek_hovered
                         and time.monotonic() - self.peek_start > PEEK_TIMEOUT_SEC)
        if left_after_hover or never_arrived:
            self.hide_overlay()
            return
        self.root.after(150, self.peek_watch)

    def on_tray_activate(self):
        # pystray fires the same default action for single and double clicks,
        # so tell them apart with a 350ms window: one click peeks, two show
        if self._tray_click_after is not None:
            self.root.after_cancel(self._tray_click_after)
            self._tray_click_after = None
            self.show_overlay(peek=False)   # double click: stay visible
        else:
            self._tray_click_after = self.root.after(350, self._tray_single_click)

    def _tray_single_click(self):
        self._tray_click_after = None
        if self.hidden:
            self.show_overlay(peek=True)    # single click: peek
        else:
            self.root.lift()

    def draw_hold_bar(self):
        # Hold-to-pause progress: the status divider fills from both edges
        # toward the center while Space is held; the toggle fires when the
        # two halves meet. Smoothstep easing avoids the linear download-bar
        # feel. (The 200ms full redraw also calls this so the bar survives
        # canvas.delete("all") between animation frames.)
        self.canvas.delete('hold_bar')
        if self.space_hold_start is None or self.space_toggled:
            return
        frac = min(1.0, (time.monotonic() - self.space_hold_start) / PAUSE_HOLD_SEC)
        eased = frac * frac * (3 - 2 * frac)  # gentle start, gentle landing
        w, h = self.get_window_size()
        status_h = 24 if self.settings['layout'] == 'horizontal' else 52
        sep_y = (h - 10) - status_h
        x1, x2 = 16, w - 16
        cx = (x1 + x2) / 2
        accent = self.get_theme()['accent']
        self.canvas.create_line(
            x1, sep_y, x1 + eased * (cx - x1), sep_y,
            fill=accent, width=2, capstyle='round', tags='hold_bar'
        )
        self.canvas.create_line(
            x2 - eased * (x2 - cx), sep_y, x2, sep_y,
            fill=accent, width=2, capstyle='round', tags='hold_bar'
        )

    # ==========================================================================
    # First-Run Setup Wizard Window
    # ==========================================================================
    def show_setup_wizard(self):
        wizard = tk.Toplevel(self.root)
        wizard.title("World Clock Setup")
        wizard.resizable(False, False)
        wizard.config(bg="#101014")

        # Frameless: the native white title bar (and its Python icon) clashes
        # with the dark body and cannot be recolored, so draw our own header
        wizard.overrideredirect(True)

        # Keep wizard on top
        wizard.attributes('-topmost', True)

        # Dark comboboxes: the default Windows theme ignores field colors,
        # so switch to 'clam' which allows full recoloring
        style = ttk.Style(wizard)
        style.theme_use('clam')
        style.configure(
            'Wizard.TCombobox',
            fieldbackground='#1a1a1f',
            background='#1a1a1f',
            foreground='#fafafa',
            arrowcolor='#8f8f96',
            bordercolor='#2c2c30',
            lightcolor='#1a1a1f',
            darkcolor='#1a1a1f',
            selectbackground='#1a1a1f',
            selectforeground='#fafafa',
            padding=6
        )
        style.map('Wizard.TCombobox', fieldbackground=[('readonly', '#1a1a1f')])
        wizard.option_add('*TCombobox*Listbox.background', '#1a1a1f')
        wizard.option_add('*TCombobox*Listbox.foreground', '#fafafa')
        wizard.option_add('*TCombobox*Listbox.selectBackground', '#6ea8ff')
        wizard.option_add('*TCombobox*Listbox.selectForeground', '#0b0b0e')

        outer = tk.Frame(wizard, bg="#101014",
                         highlightthickness=1, highlightbackground="#2c2c30")
        outer.pack(fill=tk.BOTH, expand=True)

        # Custom header: accent dot + title on the left, close on the right;
        # dragging the header moves the window (frameless windows can't)
        header = tk.Frame(outer, bg="#101014")
        header.pack(fill=tk.X)
        dot = tk.Label(header, text="●", fg="#6ea8ff", bg="#101014",
                       font=("Outfit", 9), padx=12, pady=8)
        dot.pack(side=tk.LEFT)
        title_lbl = tk.Label(header, text="World Clock Setup",
                             fg="#8f8f96", bg="#101014",
                             font=("Outfit", 9, "bold"), anchor="w")
        title_lbl.pack(side=tk.LEFT)
        close_lbl = tk.Label(header, text="✕", fg="#8f8f96", bg="#101014",
                             font=("Outfit", 11), padx=14, pady=4,
                             cursor="hand2")
        close_lbl.pack(side=tk.RIGHT)
        close_lbl.bind('<Button-1>', lambda e: sys.exit(0))
        close_lbl.bind('<Enter>',
                       lambda e: close_lbl.config(fg="#fafafa", bg="#3a3a40"))
        close_lbl.bind('<Leave>',
                       lambda e: close_lbl.config(fg="#8f8f96", bg="#101014"))

        drag_off = {'x': 0, 'y': 0}

        def header_press(e):
            drag_off['x'] = e.x_root - wizard.winfo_x()
            drag_off['y'] = e.y_root - wizard.winfo_y()

        def header_move(e):
            wizard.geometry(f"+{e.x_root - drag_off['x']}+{e.y_root - drag_off['y']}")

        for widget in (header, dot, title_lbl):
            widget.bind('<Button-1>', header_press)
            widget.bind('<B1-Motion>', header_move)

        wizard.bind('<Escape>', lambda e: sys.exit(0))

        body = tk.Frame(outer, bg="#101014")
        body.pack(fill=tk.BOTH, expand=True, padx=28, pady=(10, 24))

        # Title
        tk.Label(
            body,
            text="World Clock",
            fg="#fafafa", bg="#101014",
            font=("Outfit", 16, "bold"),
            anchor="w"
        ).pack(fill=tk.X)

        tk.Label(
            body,
            text="Clock 1 is your local system time.\nPick up to four more timezones to display.",
            fg="#8f8f96", bg="#101014",
            font=("Outfit", 9),
            justify="left",
            anchor="w"
        ).pack(fill=tk.X, pady=(6, 0))

        tk.Frame(body, bg="#26262b", height=1).pack(fill=tk.X, pady=(16, 18))

        combos = []

        # We allow up to 4 additional clocks (total of 5)
        for i in range(4):
            tk.Label(
                body,
                text=f"CLOCK {i + 2}",
                fg="#6b6b72", bg="#101014",
                font=("Outfit", 8, "bold"),
                anchor="w"
            ).pack(fill=tk.X)

            combo = ttk.Combobox(
                body,
                values=[z[0] for z in COMMON_ZONES[1:]] + ["None"],
                state="readonly",
                style='Wizard.TCombobox',
                font=("Outfit", 10)
            )
            # Default empty comboboxes to "None"
            combo.set("None")
            combo.pack(fill=tk.X, pady=(3, 12))
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

        tk.Frame(body, bg="#26262b", height=1).pack(fill=tk.X, pady=(6, 16))

        # Save Button
        tk.Button(
            body,
            text="Save and Launch",
            command=save_setup,
            bg="#6ea8ff", fg="#0b0b0e",
            activebackground="#8dbcff", activeforeground="#0b0b0e",
            font=("Outfit", 10, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=20, pady=9
        ).pack(fill=tk.X)

        tk.Label(
            body,
            text="Everything can be changed later from the right-click menu.",
            fg="#6b6b72", bg="#101014",
            font=("Outfit", 8),
            justify="center"
        ).pack(fill=tk.X, pady=(10, 0))

        # Size to content and center on screen
        wizard.update_idletasks()
        win_w = 400
        win_h = wizard.winfo_reqheight()
        pos_x = (wizard.winfo_screenwidth() - win_w) // 2
        pos_y = (wizard.winfo_screenheight() - win_h) // 2
        wizard.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")

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
            h = 132  # Panel: clock columns + status strip
        else:
            w = 200
            h = N * 72 + 72  # Panel: clock rows + three-line status strip
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
        self.drag_moved = False
        self.press_on_pause = self.is_over_pause_btn(event.x, event.y)
        if not self.press_on_pause:
            # Drop opacity to 30% to visually indicate moving action
            self.root.attributes('-alpha', 0.3)

    def stop_drag(self, event):
        self.apply_transparency()
        if self.press_on_pause and not self.drag_moved:
            self.toggle_pause()
        self.press_on_pause = False

    def do_drag(self, event):
        if (not self.drag_moved
                and abs(event.x - self.drag_start_x) < 4
                and abs(event.y - self.drag_start_y) < 4):
            return  # jitter guard: a click on the pause button is not a drag
        if self.press_on_pause:
            # Turned into a real drag after all — behave like one
            self.press_on_pause = False
            self.root.attributes('-alpha', 0.3)
        self.drag_moved = True
        x = self.root.winfo_x() + (event.x - self.drag_start_x)
        y = self.root.winfo_y() + (event.y - self.drag_start_y)
        w, h = self.get_window_size()
        x, y = self.constrain_coordinates(x, y, w, h)
        self.root.geometry(f"+{x}+{y}")

    # ==========================================================================
    # Scroll Wheel Translucency Control
    # ==========================================================================
    def is_pointer_over_window(self):
        px, py = self.root.winfo_pointerxy()
        x = self.root.winfo_rootx()
        y = self.root.winfo_rooty()
        return (x <= px < x + self.root.winfo_width()
                and y <= py < y + self.root.winfo_height())

    def on_mouse_wheel(self, event):
        # Wheel events can also arrive while the window has keyboard focus
        # but the pointer is elsewhere; only react when hovering the overlay
        if not self.is_pointer_over_window():
            return
        # Windows/macOS report event.delta; X11 reports Button-4/5 in event.num.
        # The unused field holds the non-numeric placeholder '??', so type-check it.
        delta = event.delta if isinstance(getattr(event, 'delta', None), int) else 0
        num = getattr(event, 'num', None)
        if num == 4 or delta > 0:
            self.step_opacity(1)
        elif num == 5 or delta < 0:
            self.step_opacity(-1)

    def step_opacity(self, direction):
        current = self.settings['opacity']
        idx = min(range(len(OPACITY_LEVELS)), key=lambda i: abs(OPACITY_LEVELS[i] - current))
        idx = max(0, min(len(OPACITY_LEVELS) - 1, idx + direction))
        if OPACITY_LEVELS[idx] != current:
            self.change_opacity(OPACITY_LEVELS[idx])

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

    def draw_text(self, x, y, **kwargs):
        # 1px shadow pass behind every text (variant D of the legibility
        # experiments); returns the foreground text id for bbox() callers
        shadow = dict(kwargs)
        shadow['fill'] = self.get_theme().get('text_shadow', '#000000')
        self.canvas.create_text(x + 1, y + 1, **shadow)
        return self.canvas.create_text(x, y, **kwargs)

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
            local_offset_min = int(now.astimezone().utcoffset().total_seconds() / 60)

            target_tz = ZoneInfo(target_tz_name)
            target_offset_min = int(now.astimezone(target_tz).utcoffset().total_seconds() / 60)

            diff_min = target_offset_min - local_offset_min
            diff_hours = diff_min / 60
            
            if diff_hours == 0:
                return "Local"
            
            sign = "+" if diff_hours > 0 else ""
            if diff_hours.is_integer():
                return f"{sign}{int(diff_hours)}h"
            return f"{sign}{diff_hours:.1f}h"
        except Exception:
            return ""

    def get_short_label(self, clock_info):
        # "Spain (Madrid)" -> "MADRID"; "Local System Time" -> "LOCAL"
        if clock_info.get('tz') == 'Local':
            return 'LOCAL'
        name = clock_info.get('name', '')
        if '(' in name and ')' in name:
            name = name[name.index('(') + 1:name.index(')')]
        return name.upper()

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
        n = max(len(clocks), 1)

        # Single rounded panel holding all clocks + the status strip
        panel_x1, panel_y1 = 10, 10
        panel_x2, panel_y2 = w - 10, h - 10
        # The narrow vertical window stacks the status into three lines
        status_h = 24 if layout == 'horizontal' else 52
        status_sep_y = panel_y2 - status_h

        self.draw_rounded_rect(
            panel_x1, panel_y1, panel_x2, panel_y2, 14,
            fill=theme['card_bg'],
            outline=theme['card_border'],
            width=1
        )

        # Hairline between the clocks and the status strip
        self.canvas.create_line(
            panel_x1 + 6, status_sep_y, panel_x2 - 6, status_sep_y,
            fill=theme['divider']
        )

        time_font_size = 16 if show_sec else 20
        # Light-weight face for the hero time (Segoe UI Light ships with Windows)
        time_font = ('Segoe UI Light', time_font_size) if self.is_windows else ('Outfit', time_font_size)
        symbol_font = ('Segoe UI Symbol', 9) if self.is_windows else ('Outfit', 9)

        if layout == 'horizontal':
            col_w = (panel_x2 - panel_x1) / n
        else:
            row_h = (status_sep_y - panel_y1) / n

        # Draw Clock Cells
        for i, clock_info in enumerate(clocks):
            tz_name = clock_info['tz']
            flag_code = clock_info['flag_code']

            # Dynamically override the generic 'local' clock face flag with country flag
            if flag_code == 'local':
                flag_code = self.get_local_flag_code()

            # Cell coordinates inside the panel + hairline divider between cells
            if layout == 'horizontal':
                x1 = panel_x1 + i * col_w
                x2 = x1 + col_w
                y1 = panel_y1
                y2 = status_sep_y
                if i > 0:
                    self.canvas.create_line(x1, y1 + 12, x1, y2 - 12, fill=theme['divider'])
            else:
                x1 = panel_x1
                x2 = panel_x2
                y1 = panel_y1 + i * row_h
                y2 = y1 + row_h
                if i > 0:
                    self.canvas.create_line(x1 + 12, y1, x2 - 12, y1, fill=theme['divider'])

            cell_h = y2 - y1
            pad = 16
            head_y = y1 + cell_h * 0.22
            time_y = y1 + cell_h * 0.52
            meta_y = y1 + cell_h * 0.82

            try:
                if tz_name == 'Local':
                    time_now = datetime.now()
                else:
                    time_now = datetime.now(ZoneInfo(tz_name))
            except Exception:
                self.draw_text(
                    x1 + pad, time_y,
                    text="Error",
                    fill='red',
                    font=('Outfit', 10),
                    anchor='w'
                )
                continue

            # Head row: flag + short uppercase label + day/night mark
            flag_x = x1 + pad
            self.draw_flag(flag_code, flag_x, head_y - 5)
            self.draw_text(
                flag_x + 23, head_y,
                text=self.get_short_label(clock_info),
                fill=theme['text_muted'],
                font=('Outfit', 8, 'bold'),
                anchor='w'
            )

            is_day = 7 <= time_now.hour < 19
            self.draw_text(
                x2 - pad, head_y,
                text='☀' if is_day else '☾',
                fill=theme['sun'] if is_day else theme['moon'],
                font=symbol_font,
                anchor='e'
            )

            # Time Formatting
            if use_24h:
                time_fmt = "%H:%M:%S" if show_sec else "%H:%M"
                time_str = time_now.strftime(time_fmt)
                period_str = ""
            else:
                time_fmt = "%I:%M:%S" if show_sec else "%I:%M"
                time_str = time_now.strftime(time_fmt).lstrip('0')
                period_str = time_now.strftime("%p")

            # Draw Time (hero element)
            time_text_id = self.draw_text(
                x1 + pad, time_y,
                text=time_str,
                fill=theme['text_main'],
                font=time_font,
                anchor='w'
            )

            if period_str:
                time_bbox = self.canvas.bbox(time_text_id)
                self.draw_text(
                    time_bbox[2] + 4, time_y + 4,
                    text=period_str.lower(),
                    fill=theme['accent'],
                    font=('Outfit', 8, 'bold'),
                    anchor='w'
                )

            # Meta row: offset + date
            meta_x = x1 + pad
            offset = self.get_offset_diff(tz_name)
            if offset and offset != 'Local':
                offset_id = self.draw_text(
                    meta_x, meta_y,
                    text=offset,
                    fill=theme['accent'],
                    font=('Outfit', 8, 'bold'),
                    anchor='w'
                )
                meta_x = self.canvas.bbox(offset_id)[2] + 6
            self.draw_text(
                meta_x, meta_y,
                text=time_now.strftime("%a, %b %d"),
                fill=theme['text_faded'],
                font=('Outfit', 8),
                anchor='w'
            )

        # Render Status Strip inside the panel (Session & Work Stats).
        # The timer text doubles as the pause/resume button (tag 'pause_btn').
        if self.paused:
            timer_text = f"⏸ Paused {self.paused_elapsed_str}"
            timer_fill = theme['accent']
        else:
            elapsed_delta = datetime.now() - self.session_start
            elapsed_hours, remainder = divmod(int(elapsed_delta.total_seconds()), 3600)
            elapsed_minutes, elapsed_seconds = divmod(remainder, 60)
            timer_text = f"⏱ Work {elapsed_hours:02d}:{elapsed_minutes:02d}:{elapsed_seconds:02d}"
            timer_fill = theme['text_faded']

        # Fetch monthly statistics
        days_worked, hours_worked, hours_today = self.get_monthly_stats()
        current_month = datetime.now().strftime("%B")
        days_label = "day" if days_worked == 1 else "days"
        today_part = f"Today {hours_today:.1f} hrs"
        month_part = f"{current_month}: {days_worked} {days_label}  ·  {hours_worked:.1f} hrs"
        status_font = ('Outfit', 8, 'bold')

        if layout == 'horizontal':
            # Timer (pause button) on the left, day/month stats on the right
            timer_id = self.draw_text(
                panel_x1 + 16, status_sep_y + status_h / 2,
                text=timer_text,
                fill=timer_fill,
                font=status_font,
                anchor='w'
            )
            self.draw_text(
                panel_x2 - 16, status_sep_y + status_h / 2,
                text=f"{today_part}  ·  {month_part}",
                fill=theme['text_faded'],
                font=status_font,
                anchor='e'
            )
        else:
            timer_id = self.draw_text(
                w / 2, status_sep_y + 12,
                text=timer_text,
                fill=timer_fill,
                font=status_font,
                anchor='center'
            )
            self.draw_text(
                w / 2, status_sep_y + 26,
                text=today_part,
                fill=theme['text_faded'],
                font=status_font,
                anchor='center'
            )
            self.draw_text(
                w / 2, status_sep_y + 40,
                text=month_part,
                fill=theme['text_faded'],
                font=status_font,
                anchor='center'
            )

        # Generous hit padding: the timer text is small, the target shouldn't be
        tb = self.canvas.bbox(timer_id)
        self.pause_btn_bbox = (tb[0] - 10, tb[1] - 8, tb[2] + 10, tb[3] + 8)

        # Tray tooltip mirrors the stats (~every 2s), so hovering the icon
        # answers "how much today?" even while the overlay is hidden
        self.tray_tooltip_counter += 1
        if HAS_TRAY and hasattr(self, 'tray_icon') and self.tray_tooltip_counter >= 10:
            self.tray_tooltip_counter = 0
            tip = f"{timer_text}  ·  {today_part}  ·  {month_part}"
            try:
                if self.tray_icon.title != tip:
                    self.tray_icon.title = tip
            except Exception:
                pass

        self.draw_hold_bar()
        self._redraw_after = self.root.after(200, self.update_clocks)

    # ==========================================================================
    # Context Menu & Tray Actions
    # ==========================================================================
    def contrast_text(self, hex_color):
        # Black or white, whichever reads better on the given color
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        return '#101014' if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else '#ffffff'

    def create_context_menu(self):
        self.context_popup = None
        if platform.system() == 'Darwin':
            self.canvas.bind('<Button-2>', self.show_context_menu)
        else:
            self.canvas.bind('<Button-3>', self.show_context_menu)

    def context_menu_items(self):
        # Built fresh on every right-click, so labels and theme colors are
        # always in sync with the current state
        return [
            ('command',
             "Resume Work Timer" if self.paused else "Pause Work Timer",
             self.toggle_pause),
            ('command', "Hide Overlay (hold H)", self.hide_overlay),
            ('command', "Toggle Layout (Double-Click)", self.toggle_layout),
            ('command', "Reset Clocks Setup Wizard", self.reset_clocks),
            ('separator',),
            ('cascade', "Time Format", [
                ('command', "12-Hour (AM/PM)", lambda: self.change_format('12h')),
                ('command', "24-Hour", lambda: self.change_format('24h')),
            ]),
            ('command', "Toggle Seconds", self.toggle_seconds),
            ('cascade', "Translucency", [
                ('command', f"{int(op * 100)}%",
                 (lambda o=op: self.change_opacity(o)))
                for op in OPACITY_LEVELS
            ]),
            ('cascade', "Themes", [
                ('command', "Frosted Dark", lambda: self.change_theme('dark')),
                ('command', "Frosted Light", lambda: self.change_theme('light')),
                ('command', "Cyberpunk Neon", lambda: self.change_theme('cyberpunk')),
                ('command', "Nordic Frost", lambda: self.change_theme('nordic')),
            ]),
            ('separator',),
            ('command', "Exit App", self.on_exit),
        ]

    def show_context_menu(self, event):
        if self.context_popup is not None:
            self.context_popup.close_all()
        self.context_popup = PopupMenu(
            self, self.context_menu_items(), event.x_root, event.y_root)

    def toggle_layout(self, event=None):
        self.settings['layout'] = 'vertical' if self.settings['layout'] == 'horizontal' else 'horizontal'
        self.apply_layout_size()
        self.force_redraw()
        self.save_settings()

    def change_format(self, fmt):
        self.settings['format'] = fmt
        self.force_redraw()
        self.save_settings()

    def toggle_seconds(self):
        self.settings['show_seconds'] = not self.settings['show_seconds']
        self.apply_layout_size()
        self.force_redraw()
        self.save_settings()

    def change_opacity(self, opacity):
        self.settings['opacity'] = opacity
        self.apply_transparency()
        self.save_settings()

    def change_theme(self, theme_name):
        self.settings['theme'] = theme_name
        self.apply_transparency()
        self.force_redraw()
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

        def on_toggle_pause(icon, item):
            self.root.after(0, self.toggle_pause)

        def on_tray_click(icon, item):
            self.root.after(0, self.on_tray_activate)

        def on_show_overlay(icon, item):
            self.root.after(0, lambda: self.show_overlay(peek=False))

        def on_hide_overlay(icon, item):
            self.root.after(0, self.hide_overlay)

        # pystray requires two-parameter actions, so bind the value via a factory
        def opacity_item(op):
            return item(f"{int(op * 100)}%", lambda icon, item: on_change_opacity(icon, item, op))
            
        def on_exit(icon, item):
            icon.stop()
            self.root.after(0, self.on_exit)

        menu = pystray.Menu(
            # Invisible default action: fires on tray icon clicks
            item('activate', on_tray_click, default=True, visible=False),
            item('Show Overlay', on_show_overlay,
                 visible=lambda item: self.hidden),
            item('Hide Overlay', on_hide_overlay,
                 visible=lambda item: not self.hidden),
            item(lambda text: 'Resume Work Timer' if self.paused else 'Pause Work Timer',
                 on_toggle_pause),
            item('Toggle Layout', on_toggle_layout),
            item('Toggle Seconds', on_toggle_seconds),
            pystray.Menu.SEPARATOR,
            item('Time Format', pystray.Menu(
                item('12-Hour (AM/PM)', lambda icon, item: on_change_format(icon, item, '12h')),
                item('24-Hour', lambda icon, item: on_change_format(icon, item, '24h'))
            )),
            item('Translucency', pystray.Menu(
                *[opacity_item(op) for op in OPACITY_LEVELS]
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
