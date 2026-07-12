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

    clock.PAUSE_HOLD_SEC = 0.4  # realistic threshold: a typing tap is ~0.1s
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
    clock.PAUSE_HOLD_SEC = 0.4

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
