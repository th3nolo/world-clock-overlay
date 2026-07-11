import os
import sys
import json
import platform
from datetime import datetime
from zoneinfo import ZoneInfo
import tkinter as tk
from tkinter import messagebox

# Conditional imports for System Tray support
HAS_TRAY = False
try:
    from PIL import Image, ImageDraw
    import pystray
    from pystray import MenuItem as item
    import threading
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# Configuration path
CONFIG_FILE = os.path.join(os.path.expanduser('~'), '.world_clock_overlay.json')

# Timezones config
TIMEZONES = {
    'venezuela': {'tz': 'America/Caracas', 'name': 'Venezuela', 'flag': 'venezuela'},
    'ksa': {'tz': 'Asia/Riyadh', 'name': 'Saudi Arabia', 'flag': 'ksa'},
    'spain': {'tz': 'Europe/Madrid', 'name': 'Spain', 'flag': 'spain'}
}

# Design Themes
THEMES = {
    'dark': {
        'bg': '#010101',           # Transparent key color
        'card_bg': '#16161a',
        'card_border': '#2d2d30',
        'text_main': '#ffffff',
        'text_muted': '#a0a0a5',
        'accent': '#3a86ff'
    },
    'light': {
        'bg': '#010101',           # Transparent key color
        'card_bg': '#f4f4f7',
        'card_border': '#d1d1d6',
        'text_main': '#1c1c1e',
        'text_muted': '#636366',
        'accent': '#007aff'
    },
    'cyberpunk': {
        'bg': '#010101',           # Transparent key color
        'card_bg': '#0a0810',
        'card_border': '#ff007f',
        'text_main': '#00ffff',
        'text_muted': '#8b9bb4',
        'accent': '#ff007f'
    },
    'nordic': {
        'bg': '#010101',           # Transparent key color
        'card_bg': '#2e3440',
        'card_border': '#4c566a',
        'text_main': '#d8dee9',
        'text_muted': '#9fa8b8',
        'accent': '#88c0d0'
    }
}

class WorldClockApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("World Clock Overlay")
        
        # Load state/settings
        self.load_settings()
        
        # Setup window properties
        self.root.overrideredirect(True)  # Frameless window
        self.root.attributes('-topmost', True)  # Always on top
        
        # Apply window transparency
        self.is_windows = platform.system() == 'Windows'
        self.apply_transparency()
        
        # UI variables
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
        
        # Listen for window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)
        
        # Start System Tray Icon
        if HAS_TRAY:
            self.tray_thread = threading.Thread(target=self.start_tray_icon, daemon=True)
            self.tray_thread.start()

    def load_settings(self):
        default_settings = {
            'layout': 'horizontal',  # 'horizontal' or 'vertical'
            'format': '12h',         # '12h' or '24h'
            'show_seconds': True,
            'opacity': 0.85,
            'theme': 'dark',
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
            # Store current window position
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
            # Make the background color transparent and click-through on Windows
            self.root.wm_attributes("-transparentcolor", theme['bg'])
            # Overall window opacity
            self.root.attributes('-alpha', self.settings['opacity'])
        else:
            # Linux / macOS: set overall transparency
            self.root.attributes('-alpha', self.settings['opacity'])

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
                
        # Fallback to single primary screen bounds
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        return 0, 0, screen_w, screen_h

    def constrain_coordinates(self, x, y, w, h):
        left, top, right, bottom = self.get_current_monitor_workarea()
        
        # Constrain x
        if x < left:
            x = left
        elif x + w > right:
            x = right - w
            
        # Constrain y
        if y < top:
            y = top
        elif y + h > bottom:
            y = bottom - h
            
        return x, y

    def restore_position(self):
        # Calculate size based on layout
        w, h = self.get_window_size()
        
        x = self.settings['x']
        y = self.settings['y']
        
        if x is None or y is None:
            # Default to bottom right corner
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            x = screen_w - w - 40
            y = screen_h - h - 80
            
        x, y = self.constrain_coordinates(x, y, w, h)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def get_window_size(self):
        show_sec = self.settings['show_seconds']
        if self.settings['layout'] == 'horizontal':
            w = 580 if show_sec else 550
            h = 100
        else:
            w = 200
            h = 280 if show_sec else 250
        return w, h

    def apply_layout_size(self):
        w_old = self.root.winfo_width()
        h_old = self.root.winfo_height()
        w_new, h_new = self.get_window_size()
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        
        # Calculate anchor relative to monitor workarea center
        left, top, right, bottom = self.get_current_monitor_workarea()
        cx = x + w_old / 2
        cy = y + h_old / 2
        mx = (left + right) / 2
        my = (top + bottom) / 2
        
        h_anchor = 'right' if cx > mx else 'left'
        v_anchor = 'bottom' if cy > my else 'top'
        
        # Maintain anchor coordinate constant
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

    def start_drag(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        # Visual feedback: set to 30% opacity during drag
        self.root.attributes('-alpha', 0.3)

    def stop_drag(self, event):
        # Restore user configured opacity
        self.apply_transparency()

    def do_drag(self, event):
        x = self.root.winfo_x() + (event.x - self.drag_start_x)
        y = self.root.winfo_y() + (event.y - self.drag_start_y)
        w, h = self.get_window_size()
        x, y = self.constrain_coordinates(x, y, w, h)
        self.root.geometry(f"+{x}+{y}")

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

    def draw_flag(self, country, x, y):
        w, h = 16, 10
        if country == 'venezuela':
            # Yellow, Blue, Red horizontal stripes
            self.canvas.create_rectangle(x, y, x+w, y+3, fill='#ffcc00', outline='')
            self.canvas.create_rectangle(x, y+3, x+w, y+6, fill='#00247d', outline='')
            self.canvas.create_rectangle(x, y+6, x+w, y+h, fill='#cf142b', outline='')
        elif country == 'ksa':
            # Green with a white line
            self.canvas.create_rectangle(x, y, x+w, y+h, fill='#006c35', outline='')
            self.canvas.create_line(x+3, y+7, x+w-3, y+7, fill='white', width=1)
        elif country == 'spain':
            # Red, Yellow, Red (Yellow is double thickness)
            self.canvas.create_rectangle(x, y, x+w, y+2, fill='#aa151b', outline='')
            self.canvas.create_rectangle(x, y+2, x+w, y+8, fill='#f1bf00', outline='')
            self.canvas.create_rectangle(x, y+8, x+w, y+h, fill='#aa151b', outline='')

    def get_offset_diff(self, target_tz_name):
        try:
            now = datetime.now()
            
            # Local offset in minutes
            local_offset_sec = -now.astimezone().utcoffset().total_seconds()
            local_offset_min = -int(local_offset_sec / 60)
            
            # Target offset in minutes
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

    def update_clocks(self):
        self.canvas.delete("all")
        theme = self.get_theme()
        
        # Redraw transparent canvas background
        w, h = self.get_window_size()
        self.canvas.config(bg=theme['bg'])
        
        # Layout details
        layout = self.settings['layout']
        show_sec = self.settings['show_seconds']
        use_24h = self.settings['format'] == '24h'
        
        cards = ['venezuela', 'spain', 'ksa']
        
        # Draw 3 Clock Cards
        for i, card_id in enumerate(cards):
            card_info = TIMEZONES[card_id]
            
            # Calculate card coordinates
            if layout == 'horizontal':
                card_w = 180 if show_sec else 170
                x1 = 10 + i * (card_w + 10)
                y1 = 10
                x2 = x1 + card_w
                y2 = h - 10
            else:
                card_h = 75 if show_sec else 65
                x1 = 10
                y1 = 10 + i * (card_h + 10)
                x2 = w - 10
                y2 = y1 + card_h
                
            # Draw Card Body
            self.draw_rounded_rect(
                x1, y1, x2, y2, 8, 
                fill=theme['card_bg'], 
                outline=theme['card_border'], 
                width=1
            )
            
            # Draw Flag
            flag_x = x1 + 10
            flag_y = y1 + 10
            self.draw_flag(card_info['flag'], flag_x, flag_y)
            
            # Label
            self.canvas.create_text(
                flag_x + 22, flag_y + 5,
                text=card_info['name'],
                fill=theme['text_muted'],
                font=('Outfit', 9, 'bold'),
                anchor='w'
            )
            
            # Time Offset
            offset = self.get_offset_diff(card_info['tz'])
            if offset:
                self.canvas.create_text(
                    x2 - 10, flag_y + 5,
                    text=offset,
                    fill=theme['accent'],
                    font=('Outfit', 8, 'bold'),
                    anchor='e'
                )
                
            # Compute Time
            try:
                tz = ZoneInfo(card_info['tz'])
                time_now = datetime.now(tz)
                
                # Format time
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
                time_text_id = self.canvas.create_text(
                    x1 + 10, time_y,
                    text=time_str,
                    fill=theme['text_main'],
                    font=('Courier New', time_font_size, 'bold') if self.is_windows else ('Outfit', time_font_size, 'bold'),
                    anchor='w'
                )
                
                # Draw AM/PM
                if period_str:
                    time_bbox = self.canvas.bbox(time_text_id)
                    period_x = time_bbox[2] + 4
                    self.canvas.create_text(
                        period_x, time_y + 2,
                        text=period_str.lower(),
                        fill=theme['accent'],
                        font=('Outfit', 8, 'bold'),
                        anchor='w'
                    )
                    
                # Date Formatting
                date_str = time_now.strftime("%a, %b %d")
                self.canvas.create_text(
                    x1 + 10, y2 - 12,
                    text=date_str,
                    fill=theme['text_muted'],
                    font=('Outfit', 8),
                    anchor='w'
                )
            except Exception as e:
                self.canvas.create_text(
                    x1 + 10, y1 + 35,
                    text="Error",
                    fill='red',
                    font=('Outfit', 10),
                    anchor='w'
                )
                
        # Trigger next update (every 200ms)
        self.root.after(200, self.update_clocks)

    # Context Menu Actions
    def create_context_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0, bg='#1c1c1e', fg='white', activebackground='#3a86ff')
        
        # Layouts
        self.menu.add_command(label="Toggle Layout (Double-Click)", command=self.toggle_layout)
        self.menu.add_separator()
        
        # Time format Submenu
        format_menu = tk.Menu(self.menu, tearoff=0, bg='#1c1c1e', fg='white', activebackground='#3a86ff')
        format_menu.add_command(label="12-Hour (AM/PM)", command=lambda: self.change_format('12h'))
        format_menu.add_command(label="24-Hour", command=lambda: self.change_format('24h'))
        self.menu.add_cascade(label="Time Format", menu=format_menu)
        
        # Seconds Submenu
        self.menu.add_command(
            label="Toggle Seconds", 
            command=self.toggle_seconds
        )
        
        # Opacity Submenu
        opacity_menu = tk.Menu(self.menu, tearoff=0, bg='#1c1c1e', fg='white', activebackground='#3a86ff')
        for op in [0.3, 0.5, 0.7, 0.85, 1.0]:
            opacity_menu.add_command(
                label=f"{int(op*100)}%", 
                command=lambda o=op: self.change_opacity(o)
            )
        self.menu.add_cascade(label="Translucency", menu=opacity_menu)
        
        # Themes Submenu
        theme_menu = tk.Menu(self.menu, tearoff=0, bg='#1c1c1e', fg='white', activebackground='#3a86ff')
        theme_menu.add_command(label="Frosted Dark", command=lambda: self.change_theme('dark'))
        theme_menu.add_command(label="Frosted Light", command=lambda: self.change_theme('light'))
        theme_menu.add_command(label="Cyberpunk Neon", command=lambda: self.change_theme('cyberpunk'))
        theme_menu.add_command(label="Nordic Frost", command=lambda: self.change_theme('nordic'))
        self.menu.add_cascade(label="Themes", menu=theme_menu)
        
        self.menu.add_separator()
        self.menu.add_command(label="Exit App", command=self.on_exit)
        
        # Bind right click to show menu
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

    def on_exit(self):
        self.save_settings()
        if HAS_TRAY and hasattr(self, 'tray_icon'):
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.destroy()
        sys.exit(0)

    def create_tray_icon_image(self):
        # Create an icon dynamically in memory
        image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        theme = self.get_theme()
        accent_color = theme['accent']
        
        # Draw a beautiful circular clock face
        draw.ellipse((4, 4, 60, 60), outline=accent_color, width=5)
        # Clock hands
        draw.line((32, 32, 32, 16), fill='white', width=5) # Hour
        draw.line((32, 32, 48, 32), fill='white', width=5) # Minute
        return image

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

        # Build context menu matching app's right click menu
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

if __name__ == "__main__":
    app = WorldClockApp()
    app.root.mainloop()
