from pathlib import Path
import json
import subprocess
import sys

workspace = Path(__file__).resolve().parents[2]
scratch = workspace/'.tmp/mobility_complete_20261008'
previous = json.loads((scratch/'walk-departure-regression-command.json').read_text(encoding='utf8'))
files = {arg for arg in previous if arg.startswith('tests/') and arg.endswith('.py')}
files.add('tests/unit/travel/mobility/test_car_turn_restrictions_v1.py')
command = [sys.executable, '-m', 'pytest', *sorted(files), '-q', '-m', 'not mobility_full and not live',
           '-o', 'faulthandler_timeout=45', f'--junitxml={scratch/"car-turn-regression-v1.xml"}',
           f'--basetemp={scratch/"pytest_car_turn_regression_v1"}']
with (scratch/'car-turn-regression-command.json').open('x', encoding='utf8') as out:
    json.dump(command, out, indent=2)
with (scratch/'car-turn-regression-v1.log').open('x', encoding='utf8') as out:
    done = subprocess.run(command, cwd=workspace/'final_project_cs', stdout=out, stderr=subprocess.STDOUT)
print((scratch/'car-turn-regression-v1.log').read_text(encoding='utf8')[-2500:])
sys.exit(done.returncode)
