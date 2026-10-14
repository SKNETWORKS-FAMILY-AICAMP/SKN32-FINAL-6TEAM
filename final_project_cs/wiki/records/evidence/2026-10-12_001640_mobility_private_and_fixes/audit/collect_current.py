from pathlib import Path
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[3]
out = Path(__file__).resolve().parent
temp = out / 'pytest-temp'
temp.mkdir(exist_ok=True)
env = dict(os.environ, TEMP=str(temp), TMP=str(temp), PYTHONIOENCODING='utf-8')
result = subprocess.run([sys.executable, '-m', 'pytest', 'tests/unit/travel/mobility', '--collect-only', '-q', '-m', 'not live and (mobility_full or not mobility_full)'], cwd=root / 'final_project_cs', env=env, capture_output=True)
(out / 'collection-v2.log').write_bytes(result.stdout + result.stderr)
(out / 'collection-v2-exit.txt').write_text(str(result.returncode))
print(result.returncode, result.stdout.decode('utf-8', errors='replace')[-900:])
