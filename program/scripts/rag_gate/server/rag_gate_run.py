# 서버에서: 규정 질문 경로의 「검색 결과 거르기」 시험 — Self-RAG 의 [Retrieve]·[IsRel] 에 해당하는 일을 작은 로컬 모델이 추론 때 하게 한다(학습 없음).
#  1) bge-m3(올라마)로 규정 130절 본문과 질문을 임베딩해 질문마다 절 130개의 코사인 점수를 저장(rag_sims.json) — 운영 검색(retriever.py)과 같은 방식(본문 임베딩, 질문 원문)
#  2) 질문마다 점수 상위 5개 「고객용 문장이 있는 절」을 뽑아, 모델에게 「이 문장이 질문의 답이 되는가」를 묻는다 (judge) — 답 토큰 확률 p_true 저장
#  3) 질문마다 「규정 검색이 필요한 질문인가」를 묻는다 (gate)
# 사용: python3 rag_gate_run.py 모델...   → rag_judge_<모델>.json   (입력: policy_chunks.json · rag_questions.json)
import json, math, os, re, sys, time, urllib.request

CH = json.load(open('policy_chunks.json', encoding='utf-8'))
QS = json.load(open('rag_questions.json', encoding='utf-8'))['questions']
OLL = 'http://127.0.0.1:11434'
TOPN = int(os.environ.get('TOPN', '5'))


def post(path, body, timeout=1800):
    for n in range(3):
        try:
            r = urllib.request.Request(OLL + path, data=json.dumps(body).encode(), headers={'content-type': 'application/json'})
            return json.loads(urllib.request.urlopen(r, timeout=timeout).read())
        except Exception as e:  # noqa: BLE001
            if n == 2:
                return {'error': str(e)[:200]}
            time.sleep(3)


def embed(texts):
    out = []
    for k in range(0, len(texts), 16):
        r = post('/api/embed', {'model': 'bge-m3', 'input': texts[k:k + 16]})
        out += r['embeddings']
    return out


def cos(a, b):
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


if os.path.exists('rag_sims.json'):
    sims = json.load(open('rag_sims.json'))
else:
    cv = embed([c['content'] for c in CH])
    qv = embed([q['q'] for q in QS])
    sims = {'sources': [c['source'] for c in CH], 'sims': [[cos(q, c) for c in cv] for q in qv]}
    json.dump(sims, open('rag_sims.json', 'w'))
    print('임베딩 저장', len(QS), '문제 ×', len(CH), '절', flush=True)

LINE = {c['source']: c['line'] for c in CH if c['line']}
SCH_J = {'type': 'object', 'properties': {'answers': {'type': 'boolean'}}, 'required': ['answers']}
SCH_G = {'type': 'object', 'properties': {'needs_policy': {'type': 'boolean'}}, 'required': ['needs_policy']}


def ask(model, text, schema, key):
    body = {'model': model, 'stream': False, 'format': schema, 'think': False, 'options': {'temperature': 0},
            'logprobs': True, 'top_logprobs': 2, 'messages': [{'role': 'user', 'content': text}]}
    r = post('/api/chat', body)
    try:
        v = bool(json.loads(r['message']['content']).get(key))
    except Exception:  # noqa: BLE001
        return None, None
    toks = r.get('logprobs') or []
    p = None
    for t in toks:
        piece = t.get('token', '').strip().lower()
        if piece in ('true', 'false'):
            lp = math.exp(t.get('logprob', 0.0))
            p = lp if piece == 'true' else 1 - lp
            break
    return v, p


def judge_prompt(q, line):
    return (f"고객 질문: {q}\n\n후보 답변(고객에게 그대로 보여 줄 문장): {line}\n\n"
            "이 후보 답변이 고객 질문의 핵심에 직접 답이 됩니까? 같은 주제어가 나오더라도 질문이 묻는 것(금액·방법·가능 여부 등)에 답하지 못하면 false, "
            "질문에 답이 되면 true 로 답하세요. JSON {\"answers\": true|false}")


def gate_prompt(q):
    return (f"고객 질문: {q}\n\n이 질문은 여행 규정·조건(취소·환불·변경, 날씨로 인한 순연, 식사 예약, 교통 중단·지연, 아이·고령·식이 등 동행 조건)을 "
            "묻는 질문입니까? 일정 사실 조회·잡담·규정과 무관한 정보 질문이면 false. JSON {\"needs_policy\": true|false}")


for model in sys.argv[1:]:
    t0 = time.time()
    res = {'judge': {}, 'gate': {}}
    for qi, q in enumerate(QS):
        order = sorted(range(len(CH)), key=lambda i: -sims['sims'][qi][i])
        cand = [CH[i]['source'] for i in order if CH[i]['line']][:TOPN]
        res['judge'][str(qi)] = []
        for s in cand:
            v, p = ask(model, judge_prompt(q['q'], LINE[s]), SCH_J, 'answers')
            res['judge'][str(qi)].append([s, v, p])
        res['gate'][str(qi)] = ask(model, gate_prompt(q['q']), SCH_G, 'needs_policy')
    res['_sec'] = time.time() - t0
    name = model.replace(':', '_').replace('/', '_')
    json.dump(res, open(f'rag_judge_{name}.json', 'w'), ensure_ascii=False)
    print(model, f"{res['_sec']:.0f}s", flush=True)
