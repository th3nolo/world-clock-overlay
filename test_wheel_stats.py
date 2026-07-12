"""Tests for scroll-wheel translucency and monthly stats accounting.

Runs the real app against an isolated profile (USERPROFILE override), so the
user's config and work-tracker database are never touched. Run with a Python
that has Tkinter (e.g. Windows Python from WSL):

    python.exe '\\\\wsl.localhost\\Ubuntu\\home\\th3nolo\\world-clock-overlay\\test_wheel_stats.py'
"""
import os
import sys
import json
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

    days, hours = app.get_monthly_stats()
    # Correct: 2h past + 1h live = 3h. The old code returned 4h here
    # (past 2h + saved live row 1h + live 1h again).
    check('monthly hours = 3.0, live session counted once', abs(hours - 3.0) < 0.02)
    check('unique days = 2 (past day + today)', days == 2)

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
