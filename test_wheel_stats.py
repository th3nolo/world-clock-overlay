"""Tests for scroll-wheel translucency and monthly stats accounting.

Runs the real app against an isolated profile (USERPROFILE override), so the
user's config and work-tracker database are never touched. Run with a Python
that has Tkinter (e.g. Windows Python from WSL):

    python.exe '\\\\wsl.localhost\\Ubuntu\\home\\th3nolo\\world-clock-overlay\\test_wheel_stats.py'
"""
import os
import sys
import json
import time
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta

# Isolate config/DB before importing clock.py (it resolves paths at import)
PROFILE = os.path.join(tempfile.gettempdir(), 'wco_test_profile')
shutil.rmtree(PROFILE, ignore_errors=True)
os.makedirs(PROFILE)
os.environ['USERPROFILE'] = PROFILE
os.environ['HOME'] = PROFILE

with open(os.path.join(PROFILE, '.world_clock_overlay.json'), 'w') as f:
    json.dump({
        'layout': 'horizontal', 'format': '12h', 'show_seconds': True,
        'opacity': 0.85, 'theme': 'dark', 'x': 100, 'y': 100,
        'clocks': [
            {'tz': 'Local', 'name': 'Local Time', 'flag_code': 'local'},
            {'tz': 'Europe/Madrid', 'name': 'Spain', 'flag_code': 'spain'}
        ]
    }, f)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tkinter as tk
import clock

results = []

def check(name, cond):
    results.append((name, bool(cond)))

class FakeEvent:
    def __init__(self, num='??', delta='??'):
        self.num = num
        self.delta = delta

def run_tests(app):
    # --- Scroll wheel stepping ---
    app.is_pointer_over_window = lambda: True

    app.settings['opacity'] = 0.85
    app.on_mouse_wheel(FakeEvent(delta=120))          # Windows wheel up
    check('wheel up: 0.85 -> 1.0', app.settings['opacity'] == 1.0)

    app.on_mouse_wheel(FakeEvent(delta=120))
    check('wheel up clamps at 1.0', app.settings['opacity'] == 1.0)

    for _ in range(6):
        app.on_mouse_wheel(FakeEvent(delta=-120))     # Windows wheel down
    check('wheel down clamps at 0.3', app.settings['opacity'] == 0.3)

    app.on_mouse_wheel(FakeEvent(num=4))              # X11 wheel up
    check('X11 wheel up: 0.3 -> 0.5', app.settings['opacity'] == 0.5)

    app.on_mouse_wheel(FakeEvent(num=5))              # X11 wheel down
    check('X11 wheel down: 0.5 -> 0.3', app.settings['opacity'] == 0.3)

    app.is_pointer_over_window = lambda: False
    app.on_mouse_wheel(FakeEvent(delta=120))
    check('no change when pointer not over window', app.settings['opacity'] == 0.3)

    # --- Monthly stats: live session must not be counted twice ---
    month = datetime.now().strftime('%Y-%m')
    conn = sqlite3.connect(clock.DB_FILE)
    conn.execute(
        "INSERT INTO work_sessions (start_time, end_time, duration_seconds) VALUES (?, ?, ?)",
        (f"{month}-01T09:00:00", f"{month}-01T11:00:00", 7200)  # 2h past session
    )
    conn.commit()
    conn.close()

    app.session_start = datetime.now() - timedelta(seconds=3600)  # live session: 1h
    app.update_work_session()   # 60s autosave writes the live 1h into its DB row
    app.stats_cache = None      # force re-read of the DB

    days, hours, today_hours = app.get_monthly_stats()
    # Correct: 2h past + 1h live = 3h. The old code returned 4h here
    # (past 2h + saved live row 1h + live 1h again).
    check('monthly hours = 3.0, live session counted once', abs(hours - 3.0) < 0.02)
    check('unique days = 2 (past day + today)', days == 2)
    # The live 1h session started today, so it lands in the today total.
    # The 2h past session on the 1st only counts if today IS the 1st.
    expected_today = 3.0 if datetime.now().day == 1 else 1.0
    check(f'today hours = {expected_today}', abs(today_hours - expected_today) < 0.02)

    # --- Today clipping: overnight session counts only its today portion ---
    # (skipped on the 1st: yesterday belongs to the previous month there)
    if datetime.now().day != 1:
        day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        conn = sqlite3.connect(clock.DB_FILE)
        conn.execute(
            "INSERT INTO work_sessions (start_time, end_time, duration_seconds) VALUES (?, ?, ?)",
            ((day_start - timedelta(hours=2)).isoformat(),
             (day_start + timedelta(hours=1)).isoformat(), 10800)  # 22:00 -> 01:00
        )
        conn.commit()
        conn.close()
        app.stats_cache = None
        days, hours, today_hours = app.get_monthly_stats()
        check('overnight session adds 3h to the month total', abs(hours - 6.0) < 0.02)
        check('but only its 1h after midnight to today',
              abs(today_hours - (expected_today + 1.0)) < 0.02)

    # --- Pause/resume: paused time never lands in the DB or the totals ---
    app.toggle_pause()
    check('pause sets the flag and closes the session',
          app.paused and app.session_id is None)
    conn = sqlite3.connect(clock.DB_FILE)
    open_rows = conn.execute(
        "SELECT COUNT(*) FROM work_sessions WHERE end_time IS NULL").fetchone()[0]
    conn.close()
    check('no open session rows while paused', open_rows == 0)
    _, hours_paused, _ = app.get_monthly_stats()
    check('totals frozen while paused', abs(hours_paused - hours) < 0.02)

    app.toggle_pause()
    check('resume opens a new live session',
          not app.paused and app.session_id is not None)
    _, hours_resumed, _ = app.get_monthly_stats()
    check('resume continues from the frozen total', abs(hours_resumed - hours) < 0.02)

    # --- Space HELD over the overlay toggles pause; quick taps never do ---
    app.is_pointer_over_window = lambda: True
    clock.PAUSE_HOLD_SEC = 0.05  # shrink the hold threshold for the test

    app.is_space_down = lambda: True
    app.poll_pause_hotkey()   # hold starts
    check('press alone does not toggle yet', not app.paused)
    time.sleep(0.1)
    app.poll_pause_hotkey()   # threshold reached
    check('held space over overlay pauses', app.paused)
    time.sleep(0.1)
    app.poll_pause_hotkey()
    check('keeping it held does not toggle again', app.paused)

    app.is_space_down = lambda: False
    app.poll_pause_hotkey()   # release
    app.is_space_down = lambda: True
    app.poll_pause_hotkey()
    time.sleep(0.1)
    app.poll_pause_hotkey()
    check('release then hold again resumes', not app.paused)
    app.is_space_down = lambda: False
    app.poll_pause_hotkey()

    clock.PAUSE_HOLD_SEC = 0.5  # realistic threshold: a typing tap is ~0.1s
    app.is_space_down = lambda: True
    app.poll_pause_hotkey()
    time.sleep(0.1)
    app.poll_pause_hotkey()
    app.is_space_down = lambda: False
    app.poll_pause_hotkey()
    check('quick tap (typing) never toggles', not app.paused)

    clock.PAUSE_HOLD_SEC = 0.05
    app.is_pointer_over_window = lambda: False
    app.is_space_down = lambda: True
    app.poll_pause_hotkey()
    time.sleep(0.1)
    app.poll_pause_hotkey()
    check('held space away from the overlay does nothing', not app.paused)
    app.is_space_down = lambda: False
    app.poll_pause_hotkey()

    # --- Hold progress bar on the status divider ---
    clock.PAUSE_HOLD_SEC = 10  # long threshold so the hold stays mid-way
    app.is_pointer_over_window = lambda: True
    app.is_space_down = lambda: True
    app.poll_pause_hotkey()
    check('hold draws the two converging bar segments',
          len(app.canvas.find_withtag('hold_bar')) == 2)
    app.is_space_down = lambda: False
    app.poll_pause_hotkey()
    check('early release clears the progress bar',
          not app.canvas.find_withtag('hold_bar'))
    clock.PAUSE_HOLD_SEC = 0.05
    app.is_space_down = lambda: True
    app.poll_pause_hotkey()
    time.sleep(0.1)
    app.poll_pause_hotkey()
    check('completed hold toggles and clears the bar',
          app.paused and not app.canvas.find_withtag('hold_bar'))
    app.toggle_pause()  # leave the app running
    app.is_space_down = lambda: False
    app.poll_pause_hotkey()
    app.is_pointer_over_window = lambda: False
    clock.PAUSE_HOLD_SEC = 0.5

    # --- Click on the timer: coordinate hit-test in the drag handlers ---
    app.force_redraw()  # ensure pause_btn_bbox reflects the current frame
    bx1, by1, bx2, by2 = app.pause_btn_bbox

    def fake_click(x, y):
        return type('E', (), {
            'x': x, 'y': y,
            'x_root': app.root.winfo_x() + x,
            'y_root': app.root.winfo_y() + y})

    on_btn = fake_click(int((bx1 + bx2) / 2), int((by1 + by2) / 2))
    off_btn = fake_click(2, 2)

    app.start_drag(on_btn)
    app.stop_drag(on_btn)
    check('click on the timer pauses', app.paused)
    app.start_drag(on_btn)
    app.stop_drag(on_btn)
    check('click on the timer again resumes', not app.paused)

    app.start_drag(off_btn)
    app.stop_drag(off_btn)
    check('click elsewhere does not toggle', not app.paused)

    app.start_drag(on_btn)
    moved = fake_click(on_btn.x + 40, on_btn.y)
    app.do_drag(moved)
    app.stop_drag(moved)
    check('drag starting on the timer moves, never toggles', not app.paused)

    # --- Hide to tray, peek, and tray click timing ---
    app.hide_overlay()
    check('hide withdraws the window',
          app.hidden and app.root.state() == 'withdrawn')

    app.on_tray_activate()
    app.on_tray_activate()  # second click inside the 350ms window
    check('tray double-click shows permanently',
          not app.hidden and not app.peeking and app.root.state() == 'normal')

    app.hide_overlay()
    app._tray_single_click()
    check('tray single click peeks', not app.hidden and app.peeking)
    app.is_pointer_over_window = lambda: True
    app.peek_watch()   # mouse arrives on the overlay
    check('peek stays while hovered', not app.hidden)
    app.is_pointer_over_window = lambda: False
    app.peek_watch()   # mouse leaves -> fade starts
    check('leaving starts the fade, not an instant hide', not app.hidden)
    app.fade_out_and_hide(0.5)
    check('mid-fade the window dims',
          float(app.root.attributes('-alpha')) < app.settings['opacity'])
    app.is_pointer_over_window = lambda: True
    app.fade_out_and_hide(0.7)  # mouse returns mid-fade
    check('re-entering cancels the fade',
          not app.hidden
          and abs(float(app.root.attributes('-alpha')) - app.settings['opacity']) < 0.01)
    app.is_pointer_over_window = lambda: False
    app.fade_out_and_hide(1.0)  # jump to the fade's end
    check('completed fade hides the overlay', app.hidden)

    app.hide_overlay()
    app._tray_single_click()
    app.is_pointer_over_window = lambda: False
    app.peek_hovered = False
    app.peek_start -= clock.PEEK_TIMEOUT_SEC + 1  # pretend time passed
    app.peek_watch()
    app.fade_out_and_hide(1.0)
    check('peek times out if the mouse never arrives', app.hidden)

    app.show_overlay()
    check('show restores the window',
          not app.hidden and app.root.state() == 'normal')

    # --- Tray tooltip mirrors the hours ---
    if clock.HAS_TRAY and hasattr(app, 'tray_icon'):
        app.tray_tooltip_counter = 9
        app.force_redraw()
        check('tray tooltip carries the hours',
              'Today' in app.tray_icon.title and 'hrs' in app.tray_icon.title)

    # --- Tapping H over the overlay hides it instantly ---
    app.is_pointer_over_window = lambda: True
    app.h_was_down = False
    app.is_h_down = lambda: True
    app.poll_pause_hotkey()
    check('H tap hides instantly', app.hidden)
    app.poll_pause_hotkey()
    app.is_h_down = lambda: False
    app.poll_pause_hotkey()

    app.is_h_down = lambda: True   # H must be inert while hidden
    app.poll_pause_hotkey()
    check('H is ignored while hidden', app.hidden)
    app.is_h_down = lambda: False
    app.poll_pause_hotkey()
    app.show_overlay()
    check('overlay shows at full configured opacity',
          abs(float(app.root.attributes('-alpha')) - app.settings['opacity']) < 0.01)
    app.is_pointer_over_window = lambda: False

    # --- Custom themed context popup (replaces native tk.Menu) ---
    class FakeClick:
        x_root = 150
        y_root = 150

    theme = clock.THEMES[app.settings['theme']]
    app.show_context_menu(FakeClick())
    popup = app.context_popup
    check('context popup opens', popup is not None)
    body = popup.win.winfo_children()[0]
    labels = [w for w in body.winfo_children() if isinstance(w, tk.Label)]
    seps = [w for w in body.winfo_children() if isinstance(w, tk.Frame)]
    check('10 items and 2 separators', len(labels) == 10 and len(seps) == 2)
    check('popup body and items use theme card_bg',
          body.cget('bg') == theme['card_bg']
          and labels[0].cget('bg') == theme['card_bg'])
    check('popup border uses theme card_border',
          body.cget('highlightbackground') == theme['card_border'])
    check('separators use theme divider', seps[0].cget('bg') == theme['divider'])
    check('first item is Pause when running',
          labels[0].cget('text') == 'Pause Work Timer')

    themes_label = [l for l in labels if l.cget('text').startswith('Themes')][0]
    themes_sub = [it for it in app.context_menu_items()
                  if it[0] == 'cascade' and it[1] == 'Themes'][0][2]
    popup.open_child(themes_label, themes_sub)
    check('cascade opens a themed submenu',
          popup.child is not None
          and popup.child.win.winfo_children()[0].cget('bg') == theme['card_bg'])
    popup.close_all()
    check('close_all clears popup and submenu', app.context_popup is None)

    app.pause_work()
    app.show_context_menu(FakeClick())
    body2 = app.context_popup.win.winfo_children()[0]
    first = [w for w in body2.winfo_children() if isinstance(w, tk.Label)][0]
    check('first item flips to Resume while paused',
          first.cget('text') == 'Resume Work Timer')
    app.context_popup.close_all()
    app.resume_work()

    # --- Timezone-pinned reminders ---
    from datetime import timezone as _utc
    check('reminders list exists in settings',
          isinstance(app.settings.get('reminders'), list))
    app.settings['reminders'] = []
    now_utc = datetime.now(_utc.utc)
    ry = now_utc.astimezone(clock.ZoneInfo('Asia/Riyadh')) + timedelta(minutes=5)
    app.settings['reminders'].append({
        'label': 'TZ probe', 'tz': 'Asia/Riyadh',
        'date': ry.strftime('%Y-%m-%d'), 'time': ry.strftime('%H:%M'),
        'lead': 10, 'warned': False, 'fired': False})
    past = (now_utc - timedelta(minutes=2)).astimezone()
    app.settings['reminders'].append({
        'label': 'Due now', 'tz': 'Local',
        'date': past.strftime('%Y-%m-%d'), 'time': past.strftime('%H:%M'),
        'lead': 0, 'warned': True, 'fired': False})
    if app._rem_after is not None:
        app.root.after_cancel(app._rem_after)
        app._rem_after = None
    app.check_reminders()
    r_tz, r_due = app.settings['reminders'][0], app.settings['reminders'][1]
    check('future reminder in lead window warns without firing',
          r_tz['warned'] and not r_tz['fired'])
    check('due reminder fires an alarm card',
          r_due['fired'] and app._last_alarm is not None
          and app._last_alarm.winfo_exists())
    check('tray tooltip gains a next-reminder line',
          app.next_reminder_text is not None
          and 'TZ probe' in app.next_reminder_text)
    app._last_alarm.dismiss()
    if app._rem_after is not None:
        app.root.after_cancel(app._rem_after)
        app._rem_after = None
    app.check_reminders()
    check('dismissed alarm leaves the list',
          all(r.get('label') != 'Due now'
              for r in app.settings['reminders']))

    app.show_reminder_dialog()
    rd = app._rd
    rd['label'].delete(0, 'end')
    rd['label'].insert(0, 'Dialog probe')
    future = datetime.now() + timedelta(hours=2)
    rd['date'].delete(0, 'end')
    rd['date'].insert(0, future.strftime('%Y-%m-%d'))
    rd['time'].delete(0, 'end')
    rd['time'].insert(0, future.strftime('%H:%M'))
    count_before = len(app.settings['reminders'])
    rd['save']()
    check('dialog adds a Pacific-pinned reminder',
          len(app.settings['reminders']) == count_before + 1
          and app.settings['reminders'][-1]['tz'] == 'America/Los_Angeles')
    app.settings['reminders'] = []
    app.save_settings()

    # --- Raycast and Liquid Glass themes ---
    required = {'bg', 'card_bg', 'card_border', 'divider', 'text_main',
                'text_muted', 'text_faded', 'text_shadow', 'accent',
                'sun', 'moon'}
    check('raycast and glass themes are complete',
          all(required <= set(clock.THEMES[t]) for t in ('raycast', 'glass')))
    check('glass card_bg is a real color (key-colored pixels swallow clicks)',
          clock.THEMES['glass']['card_bg'] != clock.THEMES['glass']['bg'])
    app.change_theme('glass')
    check('glass theme applies without error',
          app.settings['theme'] == 'glass')
    check('glass live pipeline engaged', app.glass_live)
    if app.glass_live:
        frame = app.render_glass(force=True)
        check('glass renders a live backdrop frame', frame is not None)
        app.apply_glass_frame(frame)   # first frame on screen
        app.force_redraw()             # image item lands on the canvas
        photo_before = app.glass_photo
        app.apply_glass_frame(app.render_glass(force=True))  # paste in place
        check('glass frames update in place (same PhotoImage, item intact)',
              app.glass_photo is photo_before
              and len(app.canvas.find_withtag('glass_bg')) == 1)
        from PIL import Image as PILImage
        orig_grab = clock.grab_region_fast
        clock.grab_region_fast = (
            lambda x, y, w, h: PILImage.new('RGB', (w, h), '#123456'))
        app.render_glass(force=True)  # prime the signature, constant backdrop
        check('unchanged backdrop render is skipped (returns None)',
              app.render_glass() is None)
        clock.grab_region_fast = orig_grab
    app.show_context_menu(FakeClick())
    check('context menu opens on glass',
          app.context_popup is not None)
    import ctypes

    def window_affinity(win):
        hwnd = (ctypes.windll.user32.GetParent(win.winfo_id())
                or win.winfo_id())
        aff = ctypes.c_uint()
        ctypes.windll.user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(aff))
        return aff.value

    if app.glass_live:
        check('context menu is capture-excluded on glass',
              window_affinity(app.context_popup.win) == 0x11)
    app.context_popup.close_all()
    app.change_opacity(0.5)
    check('glass pins window alpha to 1.0 (wheel drives the tint)',
          abs(float(app.root.attributes('-alpha')) - 1.0) < 0.001)
    app.change_theme('raycast')
    check('raycast theme applies without error',
          app.settings['theme'] == 'raycast')
    check('non-glass themes take alpha from opacity again',
          abs(float(app.root.attributes('-alpha')) - 0.5) < 0.001)
    app.change_opacity(0.85)
    app.change_theme('dark')
    app.show_context_menu(FakeClick())
    check('context menu is capturable on non-glass themes',
          window_affinity(app.context_popup.win) == 0)
    app.context_popup.close_all()

    # --- Text shadow: draw_text paints a shadow copy behind the text ---
    before = len(app.canvas.find_all())
    text_id = app.draw_text(50, 50, text='probe', fill='#ffffff', font=('Outfit', 8))
    check('draw_text adds two canvas items', len(app.canvas.find_all()) == before + 2)
    check('returned id is the foreground text', app.canvas.itemcget(text_id, 'fill') == '#ffffff')
    shadow_color = clock.THEMES[app.settings['theme']]['text_shadow']
    check('shadow color and 1px offset',
          app.canvas.itemcget(text_id - 1, 'fill') == shadow_color
          and app.canvas.coords(text_id - 1) == [51.0, 51.0])

def main():
    app = clock.WorldClockApp()

    def run_and_exit():
        code = 0
        try:
            run_tests(app)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print('ERROR:', repr(e))
            code = 1
        for name, ok in results:
            print(('PASS' if ok else 'FAIL'), '-', name)
        if any(not ok for _, ok in results):
            code = 1
        print('RESULT:', 'OK' if code == 0 else 'FAILED')
        sys.stdout.flush()
        try:
            app.root.destroy()
        except Exception:
            pass
        shutil.rmtree(PROFILE, ignore_errors=True)
        os._exit(code)  # skip tray thread shutdown

    app.root.after(700, run_and_exit)
    app.root.mainloop()

if __name__ == '__main__':
    main()
