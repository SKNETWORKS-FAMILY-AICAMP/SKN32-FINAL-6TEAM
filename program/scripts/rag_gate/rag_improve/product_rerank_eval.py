# 규정 질문 재순위 + 검증 단계의 **제품 코드**(`policy_rerank.PolicyRerank` + `trip_replies.question_reply`)를 연결 전후로 잰다. (2026-10-15)
#
#  무엇을 재나: 같은 질문 세트에서 「지금 제품」(운영 색인, 상위 3개, 문턱 0.55)과 「재순위를 켠 제품」(후보 20개를 모델이 다시 고름 + 문턱)을 비교한다.
#   · 독립 질문 B(답 있음 48 · 답 없음 50 · 근접 62) — 양식 목표 Recall@3 0.90 의 판정 세트
#   · 보류 세트 H(답 있음 68 · 답 없음 47 · 근접 25) — 2026-10-07 에 12B 재순위로 한 번 쟀다(이번에 다른 모델로 두 번째라 「순수 보류」는 아니다)
#   · 오응답 풀 2,340문장 — 제품 경로(결정 단위 → ask_policy 일 때만 규정 검색). 결정 단위 결과는 저장된 `results/misanswer/decisions.json` 을 그대로 쓴다
#     (이번 작업이 안 바꾸는 앞 단계라 다시 안 돌린다 — 결정 단위는 gemma4:12b 로 한 번 돌린 값이고 지금 제품 모델이 아니다: 한계로 적는다)
#  어떻게: 제품 클래스를 그대로 부르되 DB 와 임베딩 서버만 바꿔 끼운다 — 검색은 규정 조각 130개(`fixtures/policy_chunks.json`) + 저장된 bge-m3 벡터 캐시(운영 색인과 같은 코사인),
#   고객 문장 색인은 제품의 `CustomerTextIndex` 그대로. 모델 호출만 단계로 나눈다:
#     plan   제품 코드가 만드는 재순위 프롬프트(지시문 + 질문 + 번호 붙인 후보)를 모아 prompts.json 으로 쓴다 — 모델은 안 부른다
#     (GPU 서버 대기열의 runner 가 prompts.json 을 제품 `OllamaChat` 으로 부려 d_test_*.jsonl 을 만든다 — `product_rerank_runner.py`)
#     score  d_test_*.jsonl 의 모델 답을 제품 코드에 되먹여(같은 프롬프트면 같은 답) 상위 3 · 보이는 줄 · 오응답 · 지연을 센다
#     score --oracle  모델 대신 정답 번호를 돌려주는 가짜 재순위기 — 후보 안에 정답이 있는 비율(천장)과 이 도구의 배선을 확인한다(모델 성능이 아니다)
# 사용: python product_rerank_eval.py plan          → ../results/misanswer/product_rerank/{prompts.json,plan_meta.json}
#       python product_rerank_eval.py score --outputs d_test_X.jsonl [--tag X]  → …/report_X.md
import argparse
import hashlib
import json
import os
import sys
import time
from types import SimpleNamespace

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RG = os.path.abspath(os.path.join(HERE, '..'))
CS = os.path.abspath(os.path.join(RG, '..', '..', '..', 'final_project_cs'))
OUT_DIR = os.path.join(RG, 'results', 'misanswer', 'product_rerank')      # results/misanswer/ 는 git 밖(AI Hub 문장 원문이 들어 있다)
sys.path[:0] = [CS, HERE, os.path.join(RG, '..', 'eval_kit')]
sys.stdout.reconfigure(encoding='utf-8')

import retr_lib  # noqa: E402
from retr_lib import CH, IDX, embed, load_sets, text_A  # noqa: E402
from stats import wilson  # noqa: E402
from app.core.context import PolicyChunk  # noqa: E402
from app.domains.travel_ops.components.conversation import policy_rerank as pr  # noqa: E402
from app.domains.travel_ops.components.conversation import trip_replies  # noqa: E402
from app.domains.travel_ops.instances._shared import itinerary_team  # noqa: E402
from eval.decision_unit.replay import load_trips  # noqa: E402

SCOPES = list(trip_replies.QUESTION_SCOPES)
NOW_GATE = 0.55                      # 지금 제품의 `travel.question.min_policy_score`
GATES = (0.55, 0.50, 0.45)
TARGET = 0.90                        # 양식 목표 Recall@3
MIS = os.path.join(RG, 'results', 'misanswer')
os.makedirs(OUT_DIR, exist_ok=True)

# ───────────── 입력: 질문 세트 ─────────────
SETS = load_sets()
H_ROWS = json.load(open(os.path.join(HERE, 'holdout', 'holdout_questions.json'), encoding='utf-8'))['questions']
QSETS = {'B': SETS['B'], 'H': H_ROWS}
POOL = json.load(open(os.path.join(MIS, 'pool.json'), encoding='utf-8'))['pool']
DEC = json.load(open(os.path.join(MIS, 'decisions.json'), encoding='utf-8'))
TRIPS = load_trips(__import__('pathlib').Path(CS) / 'eval' / 'decision_unit' / 'trips.json')
ITEMS = TRIPS[sorted(TRIPS)[0]][0]
AP = [x for x in POOL if DEC.get(x['q'], {}).get('action') == 'ask_policy']

# ───────────── 제품 클래스에 끼우는 DB · 임베딩 대역 ─────────────
ROWS = [(c['source'].split('#c')[0], int(c['source'].split('#c')[1]), c['scope'], c['content']) for c in CH]
SECT = {k: v for k, v in itinerary_team.customer_sections().items() if k in IDX}      # 규정 문서의 고객 문장(제품 로더 그대로)
DA = embed([text_A(c) for c in CH])


def _chunk(i, score):
    doc, no = CH[i]['source'].split('#c')
    return PolicyChunk(document_id=doc, chunk_no=int(no), content=CH[i]['content'], score=float(score), scope=CH[i]['scope'])


def base_search(tenant_id, query, allowed_scopes, top_k=None):
    """제품 `search_policy` 의 대역 — 운영 색인(직원용 본문 벡터)과 질문 벡터의 코사인 상위 top_k(기본 3)."""
    sc = DA @ embed([query])[0]
    allowed = set(allowed_scopes)
    order = [i for i in np.argsort(-sc) if CH[i]['scope'] in allowed]
    return [_chunk(i, sc[i]) for i in order[: (top_k or 3)]]


def make_index():
    idx = pr.CustomerTextIndex(
        sections=lambda: SECT, fetch_rows=lambda t, s: [r for r in ROWS if r[2] in s],
        embed_query=lambda q: embed([q])[0].tolist(), embed_texts=lambda ts: embed(list(ts)).tolist(),
        model_key=lambda: 'bge-m3', provider_ok=lambda: True)
    idx.warm()
    return idx


INDEX = None


def index():
    global INDEX
    if INDEX is None:
        INDEX = make_index()
    return INDEX


def key_of(system, user):
    return hashlib.sha1((system + '\x00' + user).encode('utf-8')).hexdigest()[:16]


class PlanChat:
    """모델을 안 부르고 프롬프트만 모은다."""

    def __init__(self, store):
        self.store = store

    def json(self, system, user):
        self.store[key_of(system, user)] = {'i': key_of(system, user), 'system': system, 'user': user}
        return {'ranking': []}


class OracleChat:
    """정답 번호를 돌려주는 가짜 — 프롬프트에서 후보 번호를 읽어 정답 줄을 앞에 둔다. 이름은 질문 → 정답 줄 표(`gold_by_q`)로 안다."""

    def __init__(self, gold_by_line):
        self.gold_by_line = gold_by_line
        self.missing = set()

    def json(self, system, user):
        query = user.split('\n\n후보 안내 문장:\n')[0].replace('고객 질문: ', '', 1)
        lines = user.split('\n\n후보 안내 문장:\n')[1].split('\n')
        golds = self.gold_by_line.get(query, set())
        picks = [k + 1 for k, ln in enumerate(lines) if ln.split('. ', 1)[1].split('] ', 1)[1] in golds]
        return {'ranking': picks[:3]}


class ReplayChat:
    """GPU 서버 runner 가 모은 모델 답(d_test_*.jsonl)을 같은 프롬프트에 돌려준다. 없으면 `missing` 에 적고 실패로 올린다(→ 점수 보고서가 막는다)."""

    def __init__(self, outputs):
        self.outputs = outputs
        self.missing = set()
        self.used = {}

    def json(self, system, user):
        key = key_of(system, user)
        rec = self.outputs.get(key)
        if rec is None:
            self.missing.add(key)
            raise RuntimeError('missing model output')
        self.used[key] = rec
        if rec.get('error'):
            raise RuntimeError(rec['error'])
        value = json.loads(rec['raw'])
        if not isinstance(value, dict):
            raise ValueError('JSON 객체가 아니다')
        return value


def settings(stage, gate, mode='on'):
    return pr.RerankSettings(mode=mode, first_stage=stage, candidates=20, max_picks=3, min_score=gate, model='', timeout_seconds=5.0,
                             min_remaining_seconds=0.0, total_seconds=15.0, failures=10 ** 9, open_seconds=1.0, embed_timeout_seconds=30.0)


def build(stage, gate, chat):
    app = SimpleNamespace(ollama_base_url='http://replay', ollama_model='replay', ollama_keep_alive='', ollama_num_ctx=8192)
    return pr.PolicyRerank(base_search=base_search, settings_loader=lambda: settings(stage, gate), index_factory=index, sections=lambda: SECT,
                           chat_factory=lambda cfg, t: chat, prior_seconds=lambda: 0.0, app_settings=lambda: app)


def reply(search, q, items, min_score=NOW_GATE):
    """제품 `question_reply` 를 그대로 — (상태, 답, 근거). 보이는 규정 줄 = 근거의 sources."""
    return trip_replies.question_reply(message=q, items=items, tenant_id='t', policy_search=search, scopes=SCOPES, min_score=min_score, now=None)


# ───────────── plan ─────────────
def all_queries():
    texts = [r['q'] for rows in QSETS.values() for r in rows] + [x['q'] for x in AP]
    # 일정 항목이 문장에 나오면 제품은 「항목 제목 + 문장」을 검색어로 쓴다(question_reply) — 그 검색어도 미리 임베딩해 둔다
    extra = []
    for x in AP:
        item = itinerary_team.mentioned_item(ITEMS, x['q'])
        if item is not None:
            extra.append(f'{item.title} {x["q"]}')
    return list(dict.fromkeys(texts + extra))


def plan():
    texts = all_queries()
    miss = [t for t in texts if retr_lib._key(t) not in retr_lib._CACHE]
    print('질문 임베딩', len(texts), '· 캐시에 없는 것', len(miss), flush=True)
    if miss:
        print('  (없는 것은 OLLAMA_URL 의 bge-m3 로 임베딩한다 — 접속이 안 되면 여기서 멈춘다)', flush=True)
    embed(texts)
    e_texts = [pr.CustomerTextIndex.text_of(e) for e in SECT.values()]
    print('고객 문장 색인 텍스트', len(e_texts), '· 캐시에 없는 것', sum(1 for t in e_texts if retr_lib._key(t) not in retr_lib._CACHE), flush=True)
    index()                                            # 색인을 미리 만든다(제품은 예열이 하는 일 — 요청 시간 예산을 먹지 않게)
    store = {}
    chat = PlanChat(store)
    for stage in ('operating', 'customer_text'):
        rr = build(stage, NOW_GATE, chat)
        for rows in QSETS.values():
            for r in rows:
                rr.search_detailed('t', r['q'], SCOPES, top_k=3)
        for x in AP:
            reply(rr, x['q'], ITEMS)
    rows = sorted(store.values(), key=lambda r: r['i'])
    path = os.path.join(OUT_DIR, 'prompts.json')
    json.dump(rows, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
    meta = {'created': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'rows': len(rows), 'prompts_sha256': hashlib.sha256(open(path, 'rb').read()).hexdigest(),
            'system_sha256': hashlib.sha256(pr.SYSTEM.encode('utf-8')).hexdigest(), 'sets': {k: len(v) for k, v in QSETS.items()}, 'pool_ask_policy': len(AP),
            'candidates': 20}
    json.dump(meta, open(os.path.join(OUT_DIR, 'plan_meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('프롬프트', len(rows), '개 →', path, '· sha256', meta['prompts_sha256'][:12])


# ───────────── score ─────────────
def groups(x):
    if x['src'].startswith('합성'):
        return {'answerable': 'REG+', 'uncovered': 'REG-', 'offtopic': 'REG-', 'near_miss': 'NEAR'}[x['label']]
    return 'NON'


def tally(flags):
    return sum(1 for f in flags if f)


def rate(k, n):
    lo, hi = wilson(k, n)
    return f'{k}/{n} = {100 * k / n:.1f}% ({100 * lo:.1f}~{100 * hi:.1f})' if n else '—'


def lower(k, n):
    return wilson(k, n)[0] if n else 0.0


def run_variants(chat):
    """변형 → 세트 → 질문별 결과. 변형: now(지금 제품) · text(고객 문장 색인만, 모델 없음) · op/ct + 재순위 × 문턱."""
    variants = {'now': base_search, 'text': lambda tenant_id, query, allowed_scopes, top_k=None: [c.chunk for c in index().search(tenant_id, query, allowed_scopes, top_k or 3)]}
    for stage, tag in (('operating', 'op'), ('customer_text', 'ct')):
        for g in GATES:
            variants[f'{tag}@{g:.2f}'] = (stage, g)
    res = {}
    for name, v in variants.items():
        search = v if callable(v) else build(v[0], v[1], chat)
        res[name] = {'ranking': {}, 'e2e': {}, 'pool': {}, 'info': {}}
        for sname, rows in QSETS.items():
            for r in rows:
                q = r['q']
                status, _ans, ev = reply(search, q, [])
                res[name]['e2e'][(sname, q)] = list(ev.get('sources') or [])
                if not callable(v):
                    res[name]['info'][(sname, q)] = (ev.get('rerank') or {}).get('status')
                if r['type'] == 'answerable':
                    if callable(v):
                        top = [f'{c.document_id}#c{c.chunk_no}' for c in search(tenant_id='t', query=q, allowed_scopes=SCOPES, top_k=3)]
                        res[name]['ranking'][(sname, q)] = {'strict': top, 'fill': top}
                    else:
                        chunks, info = search.search_detailed('t', q, SCOPES, top_k=3)
                        picks = [f'{c.document_id}#c{c.chunk_no}' for c in chunks]
                        cands = search._candidates(settings(v[0], v[1]), 't', q, SCOPES, {})
                        order = [c.chunk.source_id for c in cands]
                        ok_llm = info and info['status'] in ('ok', 'empty')
                        fill = (picks + [s for s in order if s not in picks])[:3] if ok_llm else picks
                        res[name]['ranking'][(sname, q)] = {'strict': picks, 'fill': fill}
        for x in AP:
            _s, _a, ev = reply(search, x['q'], ITEMS)
            res[name]['pool'][x['q']] = list(ev.get('sources') or [])
            if not callable(v):
                res[name]['info'][('pool', x['q'])] = (ev.get('rerank') or {}).get('status')
    return res


def report(res, tag, meta_lines, latency_lines):
    out = [f'# 규정 질문 재순위 + 검증 단계 — 연결 전후 측정 ({tag})\n']
    out += meta_lines
    out.append('\n**읽는 법.** 「지금 제품」 = 운영 색인 · 상위 3 · 문턱 0.55(스위치 off). 「op」 = 지금 색인에서 후보 20개를 뽑아 모델이 다시 고름, 「ct」 = 고객 문장 색인에서 후보 20개를 뽑아 모델이 다시 고름. '
               '`@` 뒤는 고른 줄을 보이는 점수 문턱. 구간은 Wilson 95%. 목표 판정은 **구간 아래 끝** 이 0.90 이상일 때만 「달성」이다.\n')
    for sname in ('B', 'H'):
        rows = QSETS[sname]
        pos = [r for r in rows if r['type'] == 'answerable']
        neg = [r for r in rows if r['type'] in ('uncovered', 'offtopic')]
        near = [r for r in rows if r['type'] == 'near_miss']
        out.append(f'\n## 세트 {sname} — 답 있음 {len(pos)} · 답 없음 {len(neg)} · 근접 {len(near)}\n')
        out.append('| 변형 | 상위3 정답(모델 고른 줄만) | 상위3 정답(안 고른 자리는 1단계 순서로 채움) | 보이는 줄에 정답 | 답 없는 질문에 규정을 보임(새어 나감) | 틀린 규정을 보임 | 모델 호출 실패→지금 방식 |')
        out.append('|---|---|---|---|---|---|---|')
        for name, d in res.items():
            gold = {r['q']: {g for g in r['gold']} for r in pos}
            strict = tally(set(d['ranking'][(sname, r['q'])]['strict']) & gold[r['q']] for r in pos)
            fill = tally(set(d['ranking'][(sname, r['q'])]['fill']) & gold[r['q']] for r in pos)
            shown_ok = tally(set(d['e2e'][(sname, r['q'])]) & gold[r['q']] for r in pos)
            wrong = tally(d['e2e'][(sname, r['q'])] and not (set(d['e2e'][(sname, r['q'])]) & gold[r['q']]) for r in pos)
            leak = tally(d['e2e'][(sname, r['q'])] for r in neg)
            fb = sum(1 for r in rows if str(d['info'].get((sname, r['q'])) or '').startswith('plain'))
            out.append(f'| {name} | {rate(strict, len(pos))} | {rate(fill, len(pos))} | {rate(shown_ok, len(pos))} | {rate(leak, len(neg))} | {wrong}건 | {fb}건 |')
    # 오응답 풀
    n_pos = sum(1 for x in POOL if groups(x) == 'REG+')
    n_neg = sum(1 for x in POOL if groups(x) in ('REG-', 'NON'))
    out.append(f'\n## 오응답 풀 {len(POOL)}문장 — 제품 경로(결정 단위가 ask_policy 로 보낸 {len(AP)}문장만 규정 검색, 나머지 {len(POOL) - len(AP)}문장은 규정을 안 붙인다)\n')
    out.append(f'규정 질문(답 있음) {n_pos} · 규정이 아닌 말·답 없는 말 {n_neg}(합성 답 없음 {sum(1 for x in POOL if groups(x) == "REG-")} + 일상 대화·구어체·관광지·여행 대화 {sum(1 for x in POOL if groups(x) == "NON")}). 결정 단위는 저장된 gemma4:12b 결과를 그대로 썼다.\n')
    out.append('| 변형 | 재현율(규정 질문 중 정답 규정을 보임) | 정밀도(보인 답 중 정답) | **규정 오응답률** | 틀린 규정을 붙임(규정 질문에) | 근접·부분 답에 규정을 보임(참고) | 모델 호출 실패→지금 방식 |')
    out.append('|---|---|---|---|---|---|---|')
    for name, d in res.items():
        tp = fpw = fpn = near_show = 0
        for x in POOL:
            g, shown = groups(x), d['pool'].get(x['q'], [])
            if g == 'REG+':
                if set(shown) & set(x['gold']):
                    tp += 1
                elif shown:
                    fpw += 1
            elif g in ('REG-', 'NON') and shown:
                fpn += 1
            elif g == 'NEAR' and shown:
                near_show += 1
        fb = sum(1 for x in AP if str(d['info'].get(('pool', x['q'])) or '').startswith('plain'))
        out.append(f'| {name} | {rate(tp, n_pos)} | {rate(tp, tp + fpw + fpn)} | **{rate(fpn, n_neg)}** | {fpw}건 | {near_show}건 | {fb}건 |')
    out += latency_lines
    return '\n'.join(out)


def load_outputs(paths):
    outputs = {}
    for p in paths:
        for line in open(p, encoding='utf-8'):
            rec = json.loads(line)
            outputs[rec['i']] = rec
    return outputs


def latency_section(outputs, used_keys):
    recs = [outputs[k] for k in used_keys if k in outputs and not outputs[k].get('error')]
    if not recs:
        return ['\n## 지연\n', '모델 호출 기록이 없다.']
    s = sorted(r['seconds'] for r in recs)

    def pct(p):
        return s[min(len(s) - 1, int(round(p * (len(s) - 1))))]
    toks = [r.get('prompt_tokens') for r in recs if r.get('prompt_tokens')]
    out = ['\n## 지연 — 재순위 호출 한 건(GPU 서버 B 의 x600 재현 올라마, 제품 `OllamaChat` 호출)\n',
           f'호출 {len(recs)}건: 중앙 {pct(.5):.2f}초 · p95 {pct(.95):.2f}초 · 최대 {s[-1]:.2f}초. 입력 토큰 중앙 {sorted(toks)[len(toks) // 2] if toks else "—"}. '
           '★GPU 는 서버 B(RTX A4000)이고 x600(RTX 4070 SUPER 12GB)이 아니다 — x600 실측이 아니라 **재현 환경 값**이다.']
    return out


def score(args):
    t0 = time.time()
    index()
    if args.oracle:
        gold_by_line = {}
        for rows in QSETS.values():
            for r in rows:
                gold_by_line[r['q']] = {SECT[g]['line'] for g in r['gold'] if g in SECT}
        for x in AP:
            gold_by_line.setdefault(x['q'], {SECT[g]['line'] for g in x['gold'] if g in SECT})
        chat = OracleChat(gold_by_line)
        outputs = {}
        tag = args.tag or 'oracle'
        meta = ['**⚠ 정답 번호를 돌려주는 가짜 재순위기(오라클) 결과다 — 모델 성능이 아니라 「후보 20개 안에 정답이 있는 비율(천장)」과 도구 배선 확인용이다.**']
    else:
        outputs = load_outputs(args.outputs)
        chat = ReplayChat(outputs)
        tag = args.tag or 'run'
        meta = [f'- 모델 답 파일: {", ".join(os.path.basename(p) for p in args.outputs)} · 기록 {len(outputs)}건']
    res = run_variants(chat)
    if getattr(chat, 'missing', None):
        print('★모델 답이 없는 프롬프트', len(chat.missing), '개 — 이 보고서는 실패→지금 방식으로 센 값이 섞여 믿을 수 없다. GPU 서버 결과를 다시 받아 오라.', flush=True)
        meta.append(f'- **★모델 답이 없는 프롬프트 {len(chat.missing)}개 — 아래 수치는 불완전하다.**')
    lat = [] if args.oracle else latency_section(outputs, getattr(chat, 'used', {}).keys())
    text = report(res, tag, meta, lat)
    path = os.path.join(OUT_DIR, f'report_{tag}.md')
    open(path, 'w', encoding='utf-8').write(text)
    print(text)
    print(f'\n→ {path}  ({time.time() - t0:.0f}초)')
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=['plan', 'score'])
    ap.add_argument('--outputs', nargs='*', default=[])
    ap.add_argument('--tag', default='')
    ap.add_argument('--oracle', action='store_true')
    a = ap.parse_args()
    plan() if a.phase == 'plan' else score(a)
