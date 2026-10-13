# 결정 단위 재생 시험(172사례)을 Codex(gpt-6-luna · gpt-6-sol)로 같은 조건에서 돌린다 — 제품의 지시문 · 스키마 · 검증(`decision_unit.decide` · `fact_first`)을 그대로 쓰고
#  모델 호출 자리(`chat.structured`)만 Codex CLI 로 바꾼다(사례 하나에 CLI 한 번). 같은 사례를 3번(반복) 돌려 3번 평균 · pass^3 을 낼 수 있게 한다.
#  ★사례 · 정답 표기자는 Claude 계열 세션이다(cases_real · long7 = claude, fact · ui25 = cs/ui 세션). Codex 모델에는 출제자 편향이 없지만, 제품 지시문(SYSTEM)이 이 사례로 다듬어져 있어 gemma4:12b 쪽이 유리할 수 있다.
# 사용: python codex_du_run.py <모델> <반복 번호 1..3> [동시 수=3]   → results/codex_du/<모델>_rep<번호>.json
import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
CS = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'final_project_cs'))
os.chdir(CS)
sys.path.insert(0, CS)
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
sys.stdout.reconfigure(encoding='utf-8')
import app.core.settings as _settings_mod  # noqa: E402
_settings_mod.Settings.model_config['extra'] = 'ignore'
_settings_mod.Settings.model_rebuild(force=True)
from app.domains.travel_ops.components.conversation.decision_unit import DecisionFailed, decide, fact_first, stops_of  # noqa: E402
from codex_percall import CodexChat  # noqa: E402
from eval.decision_unit.replay import CHANGING, load_trips  # noqa: E402

model, rep = sys.argv[1], int(sys.argv[2])
par = int(sys.argv[3]) if len(sys.argv) > 3 else 3
D = Path(CS) / 'eval' / 'decision_unit'
FILES = [('cases_real.jsonl', 'trips_real.json'), ('cases_fact.jsonl', 'trips.json'), ('cases_long7.jsonl', 'trips.json'), ('cases_ui25.jsonl', 'trips.json')]
OUT = os.path.join(HERE, 'results', 'codex_du')
os.makedirs(OUT, exist_ok=True)
dst = os.path.join(OUT, f'{model.replace("/", "-")}_rep{rep}.json')
done = {}
if os.path.exists(dst):
    for r in json.load(open(dst, encoding='utf-8'))['rows']:
        if not r['got'].get('error'):
            done[(r['_file'], r['_n'])] = r
jobs = []
for cf, tf in FILES:
    trips = load_trips(D / tf)
    for n, line in enumerate([l for l in (D / cf).read_text(encoding='utf-8').splitlines() if l.strip()]):
        jobs.append((cf, n, json.loads(line), trips))
chat = CodexChat(model, os.path.join(OUT, '_tmp'))
print(model, '반복', rep, '남은', sum(1 for j in jobs if (j[0], j[1]) not in done), '/', len(jobs), flush=True)


def one(job):
    cf, n, case, trips = job
    if (cf, n) in done:
        return done[(cf, n)]
    items, changes = trips[case['trip']]
    stops = stops_of(items)
    alias_of = {s.item.item_id: s.alias for s in stops}
    selected = next((s.item.item_id for s in stops if s.alias == case.get('selected')), None)
    history = [{'role': 'customer' if who == '고객' else 'assistant', 'text': text} for who, text in case.get('history', [])]
    t0 = time.monotonic()
    try:
        got = fact_first(decide(chat, stops=stops, changes=changes, history=history, selected_item_id=selected, message=case['message']))
        action, item = got.action, alias_of.get(getattr(got.item, 'item_id', None), 'none')
        change, fact = (got.change.alias if got.change else 'none'), got.fact
        choices = [(c['action'], alias_of.get(getattr(c['item'], 'item_id', None), 'none')) for c in got.choices]
        error = None
    except Exception as exc:  # noqa: BLE001  (DecisionFailed · 호출 실패 모두 — 시스템 오류는 다시 부른다)
        action = item = change = fact = None
        choices = []
        error = f'{type(exc).__name__}: {str(exc)[:120]}'
    sec = time.monotonic() - t0
    wanted = case['action'] if isinstance(case['action'], list) else [case['action']]
    ok_action = action in wanted
    ok_item = case.get('item') is None or action == 'clarify' or item == case['item']
    ok_change = case.get('change') is None or change == case['change']
    ok_fact = case.get('fact') is None or fact == case['fact']
    good = bool(ok_action and ok_item and ok_change and ok_fact)
    wrong_target_change = bool(action in CHANGING and case.get('item') not in (None, 'none') and item not in ('none', case.get('item')))
    return {**case, '_file': cf, '_n': n, 'got': {'action': action, 'item': item, 'change': change, 'fact': fact, 'error': error, 'choices': choices}, 'good': good,
            'wrong_target_change': wrong_target_change, 'seconds': round(sec, 2)}


rows = []
t00 = time.time()
with ThreadPoolExecutor(par) as ex:
    for k, r in enumerate(ex.map(one, jobs)):
        rows.append(r)
        if (k + 1) % 20 == 0:
            json.dump({'model': model, 'rep': rep, 'rows': rows}, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, default=str)
            print(k + 1, '/', len(jobs), round(time.time() - t00), '초', flush=True)
errs = sum(1 for r in rows if r['got']['error'])
secs = sorted(r['seconds'] for r in rows if not r['got']['error'])
summary = {'cases': len(rows), 'good': sum(r['good'] for r in rows), 'errors': errs, 'wrong_target_changes': sum(r['wrong_target_change'] for r in rows),
           'p50': round(statistics.median(secs), 1) if secs else None, 'p95': round(secs[min(len(secs) - 1, int(round(0.95 * (len(secs) - 1))))], 1) if secs else None}
json.dump({'model': model, 'rep': rep, 'summary': summary, 'rows': rows}, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, default=str)
print('끝', json.dumps(summary, ensure_ascii=False))
