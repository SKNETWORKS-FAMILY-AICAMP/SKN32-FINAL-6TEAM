from pathlib import Path
import json, xml.etree.ElementTree as ET
BASE = Path(__file__).resolve().parent
paths = ['final-gate-v4/result.xml', 'verify55/after.xml',
         'wiring-offline-v2/after.xml', 'taxi-fallback-offline-v1/after.xml',
         'remaining-gate-v6/result.xml']
cases = {}
runs = []
def status(case):
    if case.find('failure') is not None or case.find('error') is not None:
        return 'failed'
    return 'skipped' if case.find('skipped') is not None else 'passed'
for rel in paths:
    raw = ET.parse(BASE / rel).getroot().findall('.//testcase')
    runs.append({'path': rel, 'tests': len(raw),
                 **{s: sum(status(c)==s for c in raw) for s in ['passed','failed','skipped']}})
    for c in raw:
        key = (c.get('classname'), c.get('name'))
        cases[key] = {'class': key[0], 'name': key[1], 'status': status(c), 'latest_run': rel}
result = {'scope': '複数実行の同一classname/nameを最新結果で置換。単一全件再実行ではありません。',
          'runs': runs, 'unique_tests': len(cases),
          **{s: sum(c['status']==s for c in cases.values()) for s in ['passed','failed','skipped']},
          'mobility_full_deselected_in_initial_v4': 220,
          'harness_policy_tests_excluded': 4, 'cases': list(cases.values())}
result['scope'] = '여러 실행의 같은 classname/name을 최신 결과로 교체했습니다. 단일 전건 재실행 결과가 아닙니다.'
(BASE / 'combined-validation-v1.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=False,indent=2))
