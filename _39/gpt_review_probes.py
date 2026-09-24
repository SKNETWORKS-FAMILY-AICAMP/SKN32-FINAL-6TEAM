"""39 GPT review: offline probes, no production edits or network calls."""
import json
import sys
import types
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pkg = types.ModuleType('mob')
pkg.__path__ = [str(ROOT / 'final_project_cs/app/modules/travel_ops/mobility_engine')]
sys.modules['mob'] = pkg
from mob import verify_time as vt
from mob.runtime import default_paths

P = default_paths()
rules = json.loads(P['rules'].read_text(encoding='utf-8'))
holidays = set(json.loads(P['holidays'].read_text(encoding='utf-8'))['holidays'])
tt = vt.Timetable.load(str(P['timetable']), {('02호선', '강변'), ('02호선', '잠실')})
lo = vt.LineOrder.load(str(P['order']))
v = vt.Verifier(tt, lo, rules, holidays)
case = dict(id='GPT-FIRST-RELIEF', date='2026-09-11', depart_at='05:36',
            arrive_by='05:40', no_alternatives=True,
            legs=[dict(line='02호선', **{'from': '강변', 'to': '잠실'})])
r = v.verify_case(case)
print('FIRST_TRAIN_RELIEF', json.dumps(r.out, ensure_ascii=False))
shifted = dict(case, depart_at=vt.to_service_min(case['depart_at']) + r.slack_min)
print('RELIEF_REPLAY', json.dumps(v.verify_case(shifted).out, ensure_ascii=False))
for ds in ('2026-09-12', '2026-09-26'):
    d = date.fromisoformat(ds)
    print('DAY_MAPPING', ds, 'registered_holiday=', ds in holidays,
          vt.Congestion.day_key(vt.day_type_of(d, holidays), d))
cg = vt.Congestion()
print('EMPTY_CONGESTION_BOOL', bool(cg), 'LOAD_MISSING', vt.Congestion.load([]))
cg.by_key[('02호선', '강변', 'U', 'weekday', 330)] = {'congestion': 110}
print('NONEMPTY_CONGESTION_BOOL', bool(cg))
selfcheck = (ROOT / 'scripts/selfcheck_mobility.py').read_text(encoding='utf-8')
print('SELFCHECK_CONGESTION_LOAD_PRESENT', 'Congestion.load(' in selfcheck)
print('SELFCHECK_CONGESTION_ARGUMENT_PRESENT', 'cg_data=' in selfcheck)
