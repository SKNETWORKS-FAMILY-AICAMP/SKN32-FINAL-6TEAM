# 오응답(규정이 아닌 말에 규정을 붙이거나, 일정과 무관한 말에 일정을 짚는 것)을 **제품의 실제 채팅 경로**로 잰다.
#  제품 경로(travel.decision_unit.mode = "on", 2026-10-07 코드 확인): 고객 문장 → 결정 단위(`decision_unit.decide` — 모델 gemma4:12b 한 번이 할 일 · 대상 · 사실 종류를 고름)
#   → 할 일이 ask_policy 일 때만 `trip_replies.question_reply`(규정 검색 → 점수 문턱 0.55 → 저장된 고객용 문장 인용). 옛 「의도 분류기 → 규칙」 경로는 꺼져 있다.
#  이 도구는 제품 코드를 고치지 않고 같은 함수를 그대로 부른다(`replay.py` 와 같은 방식 — 여행은 파일에 적힌 모양, DB 를 안 건드린다).
#  1단계(결정)는 색인과 무관하므로 한 번만 돌려 캐시한다 → 2단계(규정 답)는 색인 A(운영) · E(개선) 각각.
# 사용: python misanswer_product_path.py [--limit N]   (final_project_cs 의 DB · 로컬 11434 포트포워딩 필요)  → results/misanswer/{decisions,replies_A,replies_E}.json
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv_backup = list(sys.argv)
sys.argv = [sys.argv[0]]                       # rag_metrics_live 가 --index 를 읽으므로 비운다
sys.path.insert(0, HERE)
import rag_metrics_live as R                   # noqa: E402  (설정 · DB · 검색 · 질문 세트 · 섞은 입력 만들기를 그대로 쓴다)
sys.argv = sys.argv_backup
sys.stdout.reconfigure(encoding='utf-8')
from app.core.settings import get_settings  # noqa: E402
from app.domains.travel_ops.components.conversation import trip_replies  # noqa: E402
from app.domains.travel_ops.components.conversation.decision_unit import DecisionFailed, decide, fact_first, stops_of  # noqa: E402
from app.infrastructure.ollama_chat import from_settings  # noqa: E402
from eval.decision_unit.replay import load_trips  # noqa: E402

OUT = os.path.join(HERE, 'results', 'misanswer')
os.makedirs(OUT, exist_ok=True)
LIMIT = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None
CS = R.CS
trips = load_trips(__import__('pathlib').Path(CS) / 'eval' / 'decision_unit' / 'trips.json')
TRIP_NAME = sorted(trips)[0]
ITEMS, CHANGES = trips[TRIP_NAME]
STOPS = stops_of(ITEMS)
chat = from_settings(get_settings())
pool, info = R.build_mixed()
if LIMIT:
    pool = pool[:LIMIT]
print('문장', len(pool), '· 여행', TRIP_NAME, '· 일정', len(STOPS), flush=True)

# ── 1단계: 결정 단위(모델) — 캐시
DP = os.path.join(OUT, 'decisions.json')
DEC = json.load(open(DP, encoding='utf-8')) if os.path.exists(DP) else {}


def decide_one(x):
    q = x['q']
    if q in DEC:
        return q, DEC[q]
    t0 = time.perf_counter()
    try:
        got = fact_first(decide(chat, stops=STOPS, changes=CHANGES, history=[], selected_item_id=None, message=q))
        alias_of = {s.item.item_id: s.alias for s in STOPS}
        rec = {'action': got.action, 'item': alias_of.get(getattr(got.item, 'item_id', None), 'none'), 'fact': got.fact, 'error': None}
    except DecisionFailed as exc:
        rec = {'action': None, 'item': None, 'fact': None, 'error': str(exc)[:100]}
    except Exception as exc:  # noqa: BLE001
        rec = {'action': None, 'item': None, 'fact': None, 'error': f'{type(exc).__name__}: {str(exc)[:80]}'}
    rec['seconds'] = round(time.perf_counter() - t0, 2)
    return q, rec


t0 = time.time()
todo = [x for x in pool if x['q'] not in DEC]
print('결정 단위 호출', len(todo), '건(캐시 제외)', flush=True)
with ThreadPoolExecutor(3) as ex:
    for k, (q, rec) in enumerate(ex.map(decide_one, todo)):
        DEC[q] = rec
        if (k + 1) % 50 == 0:
            json.dump(DEC, open(DP, 'w', encoding='utf-8'), ensure_ascii=False)
            print(' ', k + 1, '/', len(todo), round(time.time() - t0), '초', flush=True)
json.dump(DEC, open(DP, 'w', encoding='utf-8'), ensure_ascii=False)

# ── 2단계: 규정 답 — ask_policy 로 고른 문장만 question_reply 로(색인 A · E)
INDEXES = {'A': R.search, 'E': R.make_search_E()}
for name, search in INDEXES.items():
    rp = os.path.join(OUT, f'replies_{name}.json')
    REP = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) else {}

    def reply_one(x):
        q = x['q']
        d = DEC[q]
        if d['action'] != 'ask_policy' or q in REP:
            return q, REP.get(q)
        t1 = time.perf_counter()
        try:
            st, ans, ev = trip_replies.question_reply(message=q, items=ITEMS, tenant_id=R.TENANT, policy_search=search, scopes=R.SCOPES, min_score=R.MIN_SCORE, now=None)
            return q, {'status': st, 'sources': ev.get('sources') or [], 'policy_hits': ev.get('policy_hits'), 'answer': ans[:400], 'ms': round((time.perf_counter() - t1) * 1000)}
        except Exception as exc:  # noqa: BLE001
            return q, {'status': 'exception', 'sources': [], 'error': f'{type(exc).__name__}: {str(exc)[:80]}'}

    with ThreadPoolExecutor(4) as ex:
        for q, rec in ex.map(reply_one, pool):
            if rec is not None:
                REP[q] = rec
    json.dump(REP, open(rp, 'w', encoding='utf-8'), ensure_ascii=False)
    print('규정 답 끝 색인', name, '·', len(REP), '건', flush=True)

json.dump({'pool': pool, 'info': info, 'trip': TRIP_NAME}, open(os.path.join(OUT, 'pool.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('끝')
