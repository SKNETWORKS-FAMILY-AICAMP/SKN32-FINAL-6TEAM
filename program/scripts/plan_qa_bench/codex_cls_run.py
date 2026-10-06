# Codex(gpt-6-luna · gpt-6-sol)를 분류 시험 문장마다 한 번씩 불러 네 라벨(의도 · 감정 · 긴급도 · 대상 종류)을 받는다 — 학습 없는 제로샷, 서비스 지시문 그대로(fixtures/cls/product_prompt.txt).
#  Gemma 기준선(llm_cls_gemma4_e4b-it-qat.json)과 같은 지시문 · 같은 시험 문장. 대상 종류는 issue_code 의 접두(activity_ · dining_ …)로 푼다(`other` 는 other).
#  ★CX 400 은 Codex 가 쓴 문장이라 Codex 모델에 출제자 편향이 있다. G96(Claude 초안 라벨)을 주 비교로 읽는다.
# 사용: python codex_cls_run.py <모델> [g96|cx|both] [동시 수=4]   → results/_pull/cls/codex_cls_<모델>.json (이어 돌리기 가능)
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
from codex_percall import call  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
model = sys.argv[1]
which = sys.argv[2] if len(sys.argv) > 2 else 'both'
par = int(sys.argv[3]) if len(sys.argv) > 3 else 4
SYS = open(os.path.join(HERE, 'fixtures', 'cls', 'product_prompt.txt'), encoding='utf-8').read()
CODES = ('activity_cancel_or_change activity_other activity_time_conflict activity_weather_risk booking_cancel_request booking_change_request booking_mismatch booking_other '
         'booking_revert_request dining_conditions dining_hours dining_other flight_other lodging_other mobility_missed_or_disrupted mobility_other mobility_route_infeasible other').split()
SCHEMA = {'type': 'object', 'properties': {'sentiment': {'type': 'string', 'enum': ['positive', 'neutral', 'negative']},
                                           'intent': {'type': 'string', 'enum': ['adjust_reject', 'confirm_request', 'incident_report', 'itinerary_submit', 'other']},
                                           'issue_code': {'type': 'string', 'enum': CODES}, 'severity': {'type': 'string', 'enum': ['low', 'medium', 'high', 'critical']}}}
OUT = os.path.join(HERE, 'results', '_pull', 'cls', f'codex_cls_{model.replace("/", "-")}.json')
res = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
sets = [('test_g96.jsonl', 'g96'), ('test_cx.jsonl', 'cx')]
for fname, key in sets:
    if which not in ('both', key):
        continue
    rows = [json.loads(l) for l in open(os.path.join(HERE, 'fixtures', 'cls', fname), encoding='utf-8')]
    have = {p['id']: p for p in res.get(fname, {}).get('preds', []) if 'error' not in p}      # 호출 실패(메모리 부족 등 시스템 오류)는 다시 부른다
    todo = [r for r in rows if r['id'] not in have]
    print(fname, model, '남은', len(todo), '/', len(rows), flush=True)
    t0 = time.time()

    def one(r):
        val, sec, err = call(model, f"{SYS}\n\nMessage: {r['message']}\n\nReturn the JSON only. Do not create files or run commands.", SCHEMA)
        if val is None:
            return {'id': r['id'], 'error': err, 'sec': round(sec, 2)}
        code = val.get('issue_code', 'other')
        return {'id': r['id'], 'intent': val.get('intent'), 'sentiment': val.get('sentiment'), 'severity': val.get('severity'),
                'case_type': 'other' if code == 'other' else code.split('_')[0], 'issue_code': code, 'sec': round(sec, 2)}

    with ThreadPoolExecutor(par) as ex:
        for k, p in enumerate(ex.map(one, todo)):
            have[p['id']] = p
            if (k + 1) % 20 == 0:
                res[fname] = {'preds': [have[r['id']] for r in rows if r['id'] in have], 'n': len(rows)}
                json.dump(res, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
                print(fname, k + 1, '/', len(todo), round(time.time() - t0), '초', flush=True)
    res[fname] = {'preds': [have[r['id']] for r in rows if r['id'] in have], 'n': len(rows)}
    json.dump(res, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    errs = sum(1 for p in have.values() if 'error' in p)
    print(fname, '끝', model, '오류', errs, round(time.time() - t0), '초', flush=True)
