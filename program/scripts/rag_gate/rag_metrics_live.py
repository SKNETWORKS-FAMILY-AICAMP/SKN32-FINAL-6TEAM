# 규정 질문(RAG) 평가 지표 — 제품의 실제 코드 경로(trip_replies.question_reply → search_policy → Ollama bge-m3 임베딩 → pgvector)를 그대로 불러 잰다.
#  제품 코드는 고치지 않고 부르기만 한다. 실행: final_project_cs 폴더에서  python <이 파일 경로>   (로컬 개발 DB 와 x600 Ollama 로 가는 11434 포트포워딩이 필요하다)
#  질문 세트 둘(둘 다 Codex gpt-6-sol 이 쓴 합성 질문 — 사람이 쓴 질문이 아니다):
#   A = fixtures/rag_questions.json  180문제 — 규정 코퍼스의 고객용 문장 111개를 보고 쓴 질문(낱말이 겹쳐 쉽다 · 답 있음 100 · 코퍼스에 없음 40 · 비슷하지만 다름 20 · 주제 밖 20)
#   B = blind/fixtures/rag_questions.json 160문제 — 고객용 문장을 보여 주지 않고 쓴 질문(답 있음 48 · 부분 답 62 · 코퍼스에 없음 30 · 주제 밖 20), 정답 라벨은 다른 Codex 호출이 달고 Claude 가 표본 검수
#  출력: results/rag_live_metrics.json (문제별 순위·점수·답·출처·지연) — 표 계산은 rag_metrics_report.py
import json
import os
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CS = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'final_project_cs'))
os.chdir(CS)
sys.path.insert(0, CS)
sys.stdout.reconfigure(encoding='utf-8')
import app.core.settings as _settings_mod  # noqa: E402
# 다른 세션이 .env.apikeys 에 아직 설정 클래스에 없는 키를 더해 둔 동안에도 측정이 돌게, 이 프로세스 안에서만 「모르는 키 무시」로 바꾼다(제품 코드·.env 파일은 건드리지 않는다)
_settings_mod.Settings.model_config['extra'] = 'ignore'
_settings_mod.Settings.model_rebuild(force=True)
from app.core.settings import get_guardrails, get_settings  # noqa: E402
from app.domains.travel_ops.components.conversation import trip_replies  # noqa: E402
from app.infrastructure.db.session import get_connection  # noqa: E402
from app.infrastructure.rag import retriever  # noqa: E402

J = lambda *a: json.load(open(os.path.join(HERE, *a), encoding='utf-8'))
SETS = {'A': J('fixtures', 'rag_questions.json')['questions'], 'B': J('blind', 'fixtures', 'rag_questions.json')['questions']}
MIN_SCORE = float(get_guardrails().get('travel.question.min_policy_score'))
SCOPES = list(trip_replies.QUESTION_SCOPES)
with get_connection() as c:
    cur = c.cursor()
    cur.execute('select tenant_id from knowledge_documents limit 1')
    TENANT = cur.fetchone()[0]
    cur.execute('select count(*), count(embedding_1024) from knowledge_chunks')
    N_CHUNK, N_EMB = cur.fetchone()
cfg = get_settings()
META = {'날짜': datetime.now().strftime('%Y-%m-%d %H:%M'), '임베딩 제공자': cfg.embedding_provider, '임베딩 모델': cfg.ollama_embedding_model, '최소 점수': MIN_SCORE, '조각 수': N_CHUNK,
        '벡터 칸 채움': N_EMB, '범위': SCOPES, '검색 top_k(운영)': 3, '질문 수': {k: len(v) for k, v in SETS.items()}}
print(META, flush=True)
src_of = lambda ch: f'{ch.document_id}#c{ch.chunk_no}'
search = retriever.search_policy
SUFFIX = ''


def make_search_E():
    """「개선 후」 색인 변형 E(문서 제목 + 절 제목 + 고객용 문장)를 임베딩해 두고 같은 질문 임베딩(제품의 `_embed_query`)과 코사인으로 순위를 매기는 검색 — 운영 코드·DB 는 건드리지 않고 `question_reply` 의 policy_search 자리에만 끼운다."""
    import numpy as np
    import urllib.request
    from app.core.context import PolicyChunk
    CHK = J('fixtures', 'policy_chunks.json')
    texts = [f"{c['doc_title']} / {c['section']}: {c['line'] or c['content']}" for c in CHK]
    vecs = []
    for k in range(0, len(texts), 16):
        r = urllib.request.Request(cfg.ollama_base_url.rstrip('/') + '/api/embed', data=json.dumps({'model': cfg.ollama_embedding_model, 'input': texts[k:k + 16]}).encode(), headers={'content-type': 'application/json'})
        vecs += json.loads(urllib.request.urlopen(r, timeout=600).read())['embeddings']
    D = np.array(vecs, dtype=float)
    D /= np.linalg.norm(D, axis=1, keepdims=True)

    def search_E(tenant_id, query, allowed_scopes, top_k=None):
        q = np.array(retriever._embed_query(query), dtype=float)
        q /= np.linalg.norm(q)
        sc = D @ q
        out = []
        for i in np.argsort(-sc)[: (top_k or 3)]:
            doc, no = CHK[i]['source'].split('#c')
            out.append(PolicyChunk(document_id=doc, chunk_no=int(no), content=CHK[i]['content'], score=float(sc[i]), scope=CHK[i]['scope']))
        return out
    return search_E


if '--index' in sys.argv and sys.argv[sys.argv.index('--index') + 1] == 'E':
    SUFFIX = '_E'
    search = make_search_E()
    META['색인'] = 'E(문서 제목 + 절 제목 + 고객용 문장) — 개선 후'
else:
    META['색인'] = 'A(직원용 본문, 운영) — 개선 전'


def pass_correct():
    """정확도용 1회: 순위(전체 130)·점수 + 운영 답(question_reply) — 같은 질문의 임베딩은 캐시되어 두 번째 호출이 빠르다(지연은 따로 잰다). 질문마다 독립이라 스레드 4개로 돌린다."""
    from concurrent.futures import ThreadPoolExecutor
    out = {}
    errs = [0]

    def one(args):
        name, i, x = args
        if True:
            row = {'i': i, 'q': x['q'], 'type': x['type'], 'gold': x.get('gold') or [], 'partial': x.get('partial') or []}
            try:
                ch = search(TENANT, x['q'], SCOPES, top_k=N_CHUNK)
                row['rank'] = [[src_of(c), round(float(c.score), 5)] for c in ch]
            except Exception as e:  # noqa: BLE001
                errs[0] += 1
                row['rank'] = None
                row['rank_error'] = f'{type(e).__name__}: {str(e)[:100]}'
            try:
                st, ans, ev = trip_replies.question_reply(message=x['q'], items=[], tenant_id=TENANT, policy_search=search, scopes=SCOPES, min_score=MIN_SCORE, now=None)
                row.update({'status': st, 'answer': ans, 'sources': ev.get('sources') or [], 'policy_hits': ev.get('policy_hits'), 'policy': ev.get('policy'), 'unmatched': bool(ev.get('unmatched'))})
            except Exception as e:  # noqa: BLE001
                errs[0] += 1
                row.update({'status': 'exception', 'answer': None, 'sources': [], 'reply_error': f'{type(e).__name__}: {str(e)[:100]}'})
            return name, i, row

    jobs = [(name, i, x) for name, qs in SETS.items() for i, x in enumerate(qs)]
    got = {name: [None] * len(qs) for name, qs in SETS.items()}
    with ThreadPoolExecutor(4) as ex:
        for k, (name, i, row) in enumerate(ex.map(one, jobs)):
            got[name][i] = row
            if (k + 1) % 60 == 0:
                print(' ', k + 1, '/', len(jobs), flush=True)
    return got, errs[0]


def pass_latency(reps=3, n_per_set=60):
    """지연 3회 반복(표본: 각 세트 앞쪽에서 4문제마다 하나씩 n_per_set 개 = 120문제): 문제마다 ① 임베딩만(캐시 우회) ② search_policy(top_k=3, 임베딩+pgvector) ③ question_reply 전체 — 각 호출 앞에 캐시를 비운다. 한 줄씩(스레드 없음)."""
    emb, srch, reply = [], [], []
    errs = {'embed': 0, 'search': 0, 'reply': 0}
    for rep in range(reps):
        for name, qs in SETS.items():
            for x in qs[::max(1, len(qs) // n_per_set)][:n_per_set]:
                q = x['q']
                retriever._embed_query.cache_clear()
                t0 = time.perf_counter()
                try:
                    retriever._embed_query.__wrapped__(q)
                    emb.append((time.perf_counter() - t0) * 1000)
                except Exception:  # noqa: BLE001
                    errs['embed'] += 1
                retriever._embed_query.cache_clear()
                t0 = time.perf_counter()
                try:
                    search(TENANT, q, SCOPES, top_k=3)
                    srch.append((time.perf_counter() - t0) * 1000)
                except Exception:  # noqa: BLE001
                    errs['search'] += 1
                retriever._embed_query.cache_clear()
                t0 = time.perf_counter()
                try:
                    trip_replies.question_reply(message=q, items=[], tenant_id=TENANT, policy_search=search, scopes=SCOPES, min_score=MIN_SCORE, now=None)
                    reply.append((time.perf_counter() - t0) * 1000)
                except Exception:  # noqa: BLE001
                    errs['reply'] += 1
        print(' 지연 반복', rep + 1, '끝', flush=True)
    return {'embed_ms': emb, 'search_ms': srch, 'reply_ms': reply, 'errors': errs, 'reps': reps, 'calls_per_rep': 2 * n_per_set}


def db_only(n=300):
    """벡터 검색 SQL 만(임베딩 계산 없이) — 질문 하나의 벡터를 한 번 계산해 같은 SQL 을 반복."""
    from pgvector.psycopg import register_vector
    vec = retriever._embed_query.__wrapped__('취소하면 위약금 있어요?')
    ts = []
    with get_connection() as conn:
        register_vector(conn)
        cur = conn.cursor()
        for _ in range(n):
            t0 = time.perf_counter()
            cur.execute("""SELECT chunk_id, content, metadata_json, 1 - (embedding_1024 <=> %s::vector) AS score FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
                           WHERE kd.tenant_id = %s AND kd.scope = ANY(%s) AND embedding_1024 IS NOT NULL ORDER BY embedding_1024 <=> %s::vector LIMIT %s""", (vec, TENANT, SCOPES, vec, 3))
            cur.fetchall()
            ts.append((time.perf_counter() - t0) * 1000)
    return ts


def pass_itinerary():
    """일정 사실 질문(시각·장소를 묻는 말 — 「몇 시·언제·어디·시간」이 들어 있고 정답 항목이 있는 질문, 시험 세트 mix8~12 의 요청 둘 제외 281문제)을 제품 답변 함수에 일정과 함께 넣어,
    질문이 짚은 일정 항목(규칙: 이름 단어 겹침)과 답에 실린 일정 사실을 본다."""
    import re
    from datetime import datetime, timezone, timedelta
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo
    from concurrent.futures import ThreadPoolExecutor
    from app.domains.travel_ops.instances._shared.itinerary_team import mentioned_item
    kst = ZoneInfo('Asia/Seoul')
    pat = re.compile(r'몇 ?시|언제|어디|시간')
    rows_in = []
    for w in ('mix8', 'mix9', 'mix10', 'mix11', 'mix12'):
        job = json.load(open(os.path.join(HERE, '..', '..', '..', 'datasets', 'core', 'pointing', 'testset', 'itinerary_questions_v1', f'{w}.json'), encoding='utf-8'))['sets'][w]
        items = [SimpleNamespace(id=i['id'], kind=i['kind'], title=i['title'], place={'name': i['place']}, ends_at=None,
                                 starts_at=datetime.fromisoformat(f"{i['date']}T{i['start']}:00").replace(tzinfo=kst)) for i in job['items']]
        for qi, x in enumerate(job['qs']):
            if x['gold'] is not None and pat.search(x['q']) and x['type'] != 'compound_intent':
                rows_in.append((w, qi, x, items, job['items']))

    def one(a):
        w, qi, x, items, raw = a
        gold = next(i for i in raw if i['id'] == x['gold'])
        picked = mentioned_item(items, x['q'])
        st, ans, ev = trip_replies.question_reply(message=x['q'], items=items, tenant_id=TENANT, policy_search=search, scopes=SCOPES, min_score=MIN_SCORE, now=None)
        return {'set': w, 'qi': qi, 'type': x['type'], 'q': x['q'], 'gold_id': x['gold'], 'picked_id': picked.id if picked else None,
                'gold_time': gold['start'], 'time_in_answer': gold['start'] in (ans or ''), 'starts_with_fact': (ans or '').startswith('일정에서 찾은 것'), 'status': st}

    with ThreadPoolExecutor(4) as ex:
        return list(ex.map(one, rows_in))


def build_mixed(n_chat=1000, n_kocul=300, n_tour=400, n_wos=300, seed=20261006):
    """실제 입력에 가깝게: 우리 질문 세트 A·B(합성 340) + 일상 대화(AI Hub 카카오톡 구어체) + 신조어 구어체 대화(KoCulture) + 서울·경기 관광지 질문 모음 + KLUE-WoS 여행 대화의 사용자 발화를 한 줄로 섞고 무작위(seed 고정)로 순서를 섞는다.
    라벨: A·B 는 기존 라벨. 일상 대화·구어체는 규정과 무관한 말(답하면 오인). 관광지 질문·WoS 발화는 라벨 없음 — 규정 문장을 보인 비율만 센다."""
    import random
    D = os.path.join(HERE, '..', '..', '..', 'datasets', 'travel')
    rnd = random.Random(seed)

    def reservoir(path, k, key):
        got, n = [], 0
        with open(path, encoding='utf-8') as f:
            for line in f:
                n += 1
                x = json.loads(line)
                if len(got) < k:
                    got.append(x)
                else:
                    j = rnd.randrange(n)
                    if j < k:
                        got[j] = x
        return [(key(x)) for x in got], n

    pool = []
    for name, qs in SETS.items():
        for i, x in enumerate(qs):
            pool.append({'src': f'합성 {name}', 'q': x['q'], 'label': x['type'], 'gold': x.get('gold') or [], 'partial': x.get('partial') or []})
    chat, nchat = reservoir(os.path.join(D, '020.주제별 텍스트 일상 대화 데이터', 'processed', 'chat_utterances.jsonl'), n_chat * 3, lambda x: x['t'])
    chat = [t for t in chat if 3 <= len(t) <= 120][:n_chat]
    kocul, nk = reservoir(os.path.join(D, 'koculture_dialogues', 'processed', 'utterances.jsonl'), n_kocul, lambda x: x['question'])
    tour, nt = reservoir(os.path.join(D, 'tourist_attractions_qa_seoul_gyeonggi', 'processed', 'questions.jsonl'), n_tour, lambda x: x['input'])
    wos_rows, nw = reservoir(os.path.join(D, 'klue_wos', 'processed', 'dialogues.jsonl'), n_wos, lambda x: x)
    wos = []
    for d in wos_rows:
        turns = d['turns'] if isinstance(d['turns'], list) else json.loads(str(d['turns']).replace("'", '"')) if False else d['turns']
        try:
            import ast
            turns = turns if isinstance(turns, list) else ast.literal_eval(turns)
            cust = [t['text'] for t in turns if t.get('role') == 'customer']
            if cust:
                wos.append(rnd.choice(cust))
        except Exception:  # noqa: BLE001
            pass
    for t in chat:
        pool.append({'src': '일상 대화(AI Hub)', 'q': t, 'label': 'chitchat', 'gold': [], 'partial': []})
    for t in kocul:
        pool.append({'src': '구어체 대화(KoCulture)', 'q': t, 'label': 'chitchat', 'gold': [], 'partial': []})
    for t in tour:
        pool.append({'src': '관광지 질문(서울·경기 QA)', 'q': t, 'label': 'unlabeled', 'gold': [], 'partial': []})
    for t in wos:
        pool.append({'src': '여행 대화 발화(KLUE-WoS)', 'q': t, 'label': 'unlabeled', 'gold': [], 'partial': []})
    rnd.shuffle(pool)
    return pool, {'일상 대화 전체 줄 수': nchat, '구어체 전체': nk, '관광지 질문 전체': nt, 'WoS 대화 수': nw, 'seed': seed}


def pass_mixed():
    from concurrent.futures import ThreadPoolExecutor
    pool, info = build_mixed()
    errs = [0]

    def one(a):
        i, x = a
        row = dict(x, i=i)
        try:
            ch = search(TENANT, x['q'], SCOPES, top_k=3)
            row['rank'] = [[src_of(c), round(float(c.score), 5)] for c in ch]
            st, ans, ev = trip_replies.question_reply(message=x['q'], items=[], tenant_id=TENANT, policy_search=search, scopes=SCOPES, min_score=MIN_SCORE, now=None)
            row.update({'status': st, 'sources': ev.get('sources') or []})
        except Exception as e:  # noqa: BLE001
            errs[0] += 1
            row.update({'rank': None, 'status': 'exception', 'sources': [], 'error': f'{type(e).__name__}: {str(e)[:100]}'})
        return row

    with ThreadPoolExecutor(4) as ex:
        rows = []
        for k, r in enumerate(ex.map(one, list(enumerate(pool)))):
            rows.append(r)
            if (k + 1) % 300 == 0:
                print(' 섞은 스트림', k + 1, '/', len(pool), flush=True)
    return rows, info, errs[0]


def pass_multilang():
    """독립 세트 B 의 160문제를 영어·일본어·중국어(간체)로 옮긴 질문(번역은 Claude 하위 작업이 한 합성 번역, 사람 번역 아님)으로 같은 운영 경로를 돈다."""
    from concurrent.futures import ThreadPoolExecutor
    tr = J('multilang', 'translations_raw.json')
    qs = SETS['B']

    def one(args):
        lang, i = args
        q = tr[i][lang]
        row = {'i': i, 'lang': lang, 'q': q, 'type': qs[i]['type'], 'gold': qs[i].get('gold') or [], 'partial': qs[i].get('partial') or []}
        try:
            ch = search(TENANT, q, SCOPES, top_k=N_CHUNK)
            row['rank'] = [[src_of(c), round(float(c.score), 5)] for c in ch]
            st, ans, ev = trip_replies.question_reply(message=q, items=[], tenant_id=TENANT, policy_search=search, scopes=SCOPES, min_score=MIN_SCORE, now=None)
            row.update({'status': st, 'sources': ev.get('sources') or []})
        except Exception as e:  # noqa: BLE001
            row.update({'rank': None, 'status': 'exception', 'sources': [], 'error': f'{type(e).__name__}: {str(e)[:100]}'})
        return row

    jobs = [(lang, i) for lang in ('en', 'ja', 'zh') for i in range(len(qs))]
    with ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(one, jobs))
    return rows


if __name__ == '__main__':
    stage = sys.argv[1] if len(sys.argv) > 1 else 'correct'
    t0 = time.time()
    if stage == 'correct':
        correct, errs = pass_correct()
        print('정확도 패스 끝', round(time.time() - t0), '초 · 오류', errs, flush=True)
        json.dump({'meta': META, 'correct': correct, 'errors_correct_pass': errs}, open(os.path.join(HERE, 'results', f'rag_live_correct{SUFFIX}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    elif stage == 'mixed':
        rows, info, errs = pass_mixed()
        json.dump({'meta': META, 'info': info, 'errors': errs, 'rows': rows}, open(os.path.join(HERE, 'results', f'rag_live_mixed{SUFFIX}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    elif stage == 'itinerary':
        rows = pass_itinerary()
        json.dump({'meta': META, 'rows': rows}, open(os.path.join(HERE, 'results', f'rag_live_itinerary{SUFFIX}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    elif stage == 'multilang':
        rows = pass_multilang()
        json.dump({'meta': META, 'rows': rows}, open(os.path.join(HERE, 'results', f'rag_live_multilang{SUFFIX}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    else:
        lat = pass_latency(3)
        lat['db_only_ms'] = db_only()
        json.dump({'meta': META, 'latency': lat}, open(os.path.join(HERE, 'results', f'rag_live_latency{SUFFIX}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print('저장 끝', round(time.time() - t0), '초')
