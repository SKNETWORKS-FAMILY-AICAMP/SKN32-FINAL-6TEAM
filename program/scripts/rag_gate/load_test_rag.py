# 규정 질문(RAG) 답 경로의 부하 시험 — 처리량(TPS) · 지연 · 오류를 같은 시험에서 함께 잰다.
#  부르는 것: 제품의 question_reply(질문 임베딩 = x600 서버 Ollama bge-m3 · 검색 = 로컬 개발 DB pgvector). 제품 코드는 고치지 않는다.
#  방법(문헌 근거는 평가 설계서):
#   · 폐쇄 루프(closed loop): 동시 사용자 N 명이 응답을 받으면 바로 다음 질문을 보낸다 — N 을 1·2·4·8·16 으로 올리며 처리량이 더 안 늘고 지연만 느는 지점(포화점)을 찾는다.
#   · 개방 루프(open loop): 응답과 상관없이 일정한 도착률(건/초)로 요청을 보낸다 — 지연을 「보내기로 한 시각」부터 재서 조정된 누락(coordinated omission, Gil Tene)을 피한다.
#   · 단계마다 워밍업을 따로 두고(기록 안 함) 정상 상태만 잰다. 질문은 A·B 세트를 섞어 돌리고 호출마다 질문 임베딩 캐시를 비워 매번 새 계산이 되게 한다.
#  한계: 이 PC → 원격 임베딩 왕복이 지연에 들어간다. 운영(같은 기계)과 다르다. 부하를 주는 동안 같은 Ollama 에 다른 호출이 없어야 한다.
# 사용: final_project_cs 폴더에서  python <이 파일>  [--quick]   → results/load_test_rag.json
import concurrent.futures as cf
import json
import os
import random
import sys
import threading
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CS = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'final_project_cs'))
os.chdir(CS)
sys.path.insert(0, CS)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', 'eval_kit')))
sys.stdout.reconfigure(encoding='utf-8')
import app.core.settings as _settings_mod  # noqa: E402
_settings_mod.Settings.model_config['extra'] = 'ignore'      # 이 프로세스 안에서만(다른 세션이 환경 파일에 더한 키 때문에 설정 검사가 막히는 동안에도 측정이 돌게)
_settings_mod.Settings.model_rebuild(force=True)
from app.core.settings import get_guardrails  # noqa: E402
from app.domains.travel_ops.components.conversation import trip_replies  # noqa: E402
from app.infrastructure.db.session import get_connection  # noqa: E402
from app.infrastructure.rag import retriever  # noqa: E402
from stats import latency_summary, wilson  # noqa: E402

QUICK = '--quick' in sys.argv
WARM, MEASURE = (3, 10) if QUICK else (10, 45)
CLOSED = [1, 4] if QUICK else [1, 2, 4, 8, 16]
OPEN = [2] if QUICK else [1, 2, 4, 8]
J = lambda *a: json.load(open(os.path.join(HERE, *a), encoding='utf-8'))
QS = [x['q'] for x in J('fixtures', 'rag_questions.json')['questions']] + [x['q'] for x in J('blind', 'fixtures', 'rag_questions.json')['questions']]
random.Random(20261006).shuffle(QS)
MIN_SCORE = float(get_guardrails().get('travel.question.min_policy_score'))
SCOPES = list(trip_replies.QUESTION_SCOPES)
with get_connection() as c:
    cur = c.cursor()
    cur.execute('select tenant_id from knowledge_documents limit 1')
    TENANT = cur.fetchone()[0]
CNT = {'i': 0}
LOCK = threading.Lock()


def next_q():
    with LOCK:
        CNT['i'] += 1
        return QS[CNT['i'] % len(QS)]


def one_call():
    q = next_q()
    retriever._embed_query.cache_clear()
    t0 = time.perf_counter()
    try:
        trip_replies.question_reply(message=q, items=[], tenant_id=TENANT, policy_search=retriever.search_policy, scopes=SCOPES, min_score=MIN_SCORE, now=None)
        return (time.perf_counter() - t0) * 1000, True
    except Exception:  # noqa: BLE001
        return (time.perf_counter() - t0) * 1000, False


def closed_step(n_users):
    stop_warm = time.perf_counter() + WARM
    stop = stop_warm + MEASURE
    res = []
    lk = threading.Lock()

    def worker():
        while time.perf_counter() < stop:
            ms, ok = one_call()
            t = time.perf_counter()
            if t >= stop_warm:
                with lk:
                    res.append((ms, ok))
    with cf.ThreadPoolExecutor(max_workers=n_users) as ex:
        for _ in range(n_users):
            ex.submit(worker)
    return summarize(res, MEASURE, {'모드': '폐쇄 루프', '동시 사용자': n_users})


def open_step(rate):
    total = WARM + MEASURE
    n = int(rate * total)
    t_start = time.perf_counter() + 0.5
    res = []
    lk = threading.Lock()

    def job(k):
        sched = t_start + k / rate
        delay = sched - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        ms, ok = one_call()
        end = time.perf_counter()
        # 지연 = 보내기로 한 시각부터 끝날 때까지(밀려서 늦게 시작한 만큼도 지연으로 센다)
        lat = (end - sched) * 1000
        if sched - t_start >= WARM:
            with lk:
                res.append((lat, ok))
    with cf.ThreadPoolExecutor(max_workers=64) as ex:
        list(ex.map(job, range(n)))
    return summarize(res, MEASURE, {'모드': '개방 루프', '도착률(건/초)': rate})


def summarize(res, seconds, meta):
    lat_ok = [m for m, ok in res if ok]
    errs = sum(1 for _, ok in res if not ok)
    out = dict(meta)
    out.update({'완료 건수': len(res), '성공': len(lat_ok), '오류': errs, '오류율': errs / len(res) if res else None, '처리량(건/초)': round(len(res) / seconds, 2), '지연(ms)': latency_summary(lat_ok) if lat_ok else None})
    out['오류율 95% 구간'] = wilson(errs, len(res)) if res else None
    return out


results = {'meta': {'날짜': datetime.now().strftime('%Y-%m-%d %H:%M'), '워밍업(초)': WARM, '측정(초)': MEASURE, '질문 수': len(QS), '임베딩': 'ollama bge-m3(x600 서버, 포트포워딩 경유)', '검색': '로컬 개발 DB pgvector', '빠른 판': QUICK},
           '폐쇄 루프': [], '개방 루프': []}
for n in CLOSED:
    r = closed_step(n)
    results['폐쇄 루프'].append(r)
    print('폐쇄', n, r['처리량(건/초)'], '건/초 · p50', round(r['지연(ms)']['p50']) if r['지연(ms)'] else None, 'p95', round(r['지연(ms)']['p95']) if r['지연(ms)'] else None, '오류', r['오류'], '/', r['완료 건수'], flush=True)
for rate in OPEN:
    r = open_step(rate)
    results['개방 루프'].append(r)
    print('개방', rate, '건/초 → 완료', r['처리량(건/초)'], 'p50', round(r['지연(ms)']['p50']) if r['지연(ms)'] else None, 'p95', round(r['지연(ms)']['p95']) if r['지연(ms)'] else None, '오류', r['오류'], '/', r['완료 건수'], flush=True)
json.dump(results, open(os.path.join(HERE, 'results', 'load_test_rag' + ('_quick' if QUICK else '') + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('끝')
