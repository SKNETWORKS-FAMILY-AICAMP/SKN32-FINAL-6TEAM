from pathlib import Path
import subprocess, sys

wt = Path(r'C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/pastguard-final-20261106/wt/final_project_cs')
for name in ('tests/e2e/test_intake_interpretations_api.py', 'tests/e2e/test_intake_reading_prefs.py'):
    p = wt / name
    subprocess.run([sys.executable, str(wt.parent.parent / 'resolve.py'), str(p), '0:ours'], check=True)
    raw = p.read_bytes()
    crlf = b'\r\n' in raw
    s = raw.decode('utf-8')
    old = '"date": D_2026_10_15, "date_quote": D_2026_10_15, "start"'
    new = '"date": D_2026_10_15, "date_quote": D_2026_10_15, "year_quote": D_2026_10_15[:4], "date_form": "explicit_year", "start"'
    assert s.count(old) == 2, s.count(old)
    s = s.replace(old, new)
    p.write_bytes(s.encode('utf-8'))
    print(name, 'crlf' if crlf else 'lf')
