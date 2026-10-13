# MX 시험 세트 — 「잡담 속에 일정 질문 · 변경 요청이 섞여 들어온 입력」에서 항목 짚기 모델이 (a) 알맞은 항목을 짚는지 (b) 일정 낱말이 섞인 잡담 · 일정 밖 질문에 항목을 안 고르는지를 잰다.
#  설계 합의(2026-10-07): Claude(코드 이어 붙이기 대량 + LLM 소량) · Codex 솔 6.1(같은 선택 C, 세부 보강) — 기록 scratchpad/consensus/20261007_2150_mixed_testset/ (결정 문서 program/research/시험세트_MX_설계_2026-10-07.md).
#  구성: 요청 문장(일정마다 솔 6.1 이 잡담 없이 씀 + 루나 6.0 이 따로 라벨, 합의분만) × 잡담 조각(로컬 말뭉치: D 잡담 1,300 · D2 1,000 · Claude 합성 240 — AI Hub · KoCulture 문장은 외부로 보내지 않고 코드로만 이어 붙임)
#        + LLM 이 자연스럽게 섞어 쓴 소량(솔 6.1, 힌트는 Claude 합성 잡담뿐 · 루나 6.0 이 따로 라벨). 모든 섞인 문장에는 「요청만 있는 대조 짝」이 붙는다 → 섞임 효과를 짝지어 잰다.
#  일정: D 시험의 일정 89개 중 H 시험(어려운 세트)이 쓴 30개를 뺀 59개(학습에는 안 쓴 일정). ★AI Hub · KoCulture 문장이 들어간 결과 파일은 git 밖 datasets/travel/mx_testset/ 에 둔다.
# 단계: gen(요청 문장, 솔) → label(루나) → nat(자연 혼합, 솔) → natlabel(루나) → build(조립)
# 사용: python build_mx_set.py gen|label|nat|natlabel|build [--workers 3] [--seed 20261018]
import argparse
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
sys.stdout.reconfigure(encoding='utf-8')
from codex_percall import call  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('step', choices=['gen', 'label', 'nat', 'natlabel', 'build'])
ap.add_argument('--workers', type=int, default=3)
ap.add_argument('--seed', type=int, default=20261018)
ap.add_argument('--gen-model', default='gpt-6.1-sol')
ap.add_argument('--label-model', default='gpt-6-luna')
a = ap.parse_args()

OUT = os.path.join(os.path.abspath(os.path.join(HERE, '..', '..', '..')), 'datasets', 'travel', 'mx_testset')   # 저장소 루트의 datasets/(git 밖). ★ROOT 는 program/ 이라 거기에 만들면 git 이 못 막는다 — 2026-10-07 바로잡음
os.makedirs(OUT, exist_ok=True)
EP = os.path.join(HERE, 'results', 'empty_probe')
P = json.load(open(os.path.join(EP, 'all_prompts.json'), encoding='utf-8'))
heads, tail = {}, None
for p in P:
    h, rest = p['prompt'].split('고객 질문: ', 1)
    heads[h] = heads.get(h, 0) + 1
    tail = tail or rest.split('\n\n', 1)[1]
HEADS = sorted(heads)
H_USED = {json.loads(l)['k'] for l in open(os.path.join(HERE, 'results', 'hard_set', 'gen_test_30_20261015.jsonl'), encoding='utf-8') if 'error' not in json.loads(l)}
SEL = [(k, HEADS[k]) for k in range(len(HEADS)) if k not in H_USED]   # H 시험이 쓴 일정 30개를 뺀 나머지(59개)
GEN, LAB, NAT, NLAB = (os.path.join(OUT, f'{n}.jsonl') for n in ('gen', 'label', 'nat', 'natlabel'))
QRE = re.compile(r'고객 질문: (.*?)\n\n', re.S)

CATS = {  # (개수, 정의, 정답 종류)
    'MX1': (9, '일정의 항목 **하나**에 대한 정보 · 확인 질문(시간 · 장소 · 주차 · 영업시간 · 예약 · 입장료 · 환불 · 준비물 등). 항목은 이름 · 별칭 · 날짜 · 순서 · 시각 · 내용 설명 중 하나로 정해져야 한다 — 이 중 3개 이상은 날짜 · 순서 · 시각(예: 「둘째 날 점심」 「세 번째 일정」 「오후 2시 거」)으로 가리킬 것', 'item'),
    'MX2': (8, '일정의 항목 하나를 특정해 시간 변경 · 취소 · 순서 바꾸기 · 다른 곳으로 교체를 요청하는 말. 항목은 이름 · 날짜 · 순서 · 시각 · 설명 중 하나로 특정되어야 한다 — 이 중 3개 이상은 날짜 · 순서 · 시각으로 가리킬 것', 'item'),
    'MX3': (7, '이 일정에 **없는** 장소(일정의 항목과 이름이 비슷한 다른 곳 포함)에 대한 질문, 또는 어떤 항목과도 무관한 일반 여행 규정 · 서비스 질문(환불 일반 규정 · 날씨 · 교통카드 · 환전 등)', 'null'),
    'MX4': (8, '일정에 나온 장소 · 음식 낱말을 말하지만 **아무것도 묻거나 요청하지 않는** 말(감상 · 기대 · 추억 · 사진 본 이야기)', 'null'),
    'MX5a': (3, '새 항목을 **추가**하고 싶다거나 일정 **전체**를 바꾸자는 요청(어느 기존 항목도 지정하지 않음)', 'null'),
    'MX5b': (3, '일정 전체에 대한 감정 · 불만 · 걱정 표현(특정 항목 지정 없음)', 'null'),
    'MX6a': (1, '두 항목의 이름을 함께 말하지만 **최종 요청은 한 항목**에 대한 것인 말', 'item'),
    'MX6b': (1, '실제로 **두 항목을 함께** 묻거나 바꾸라는 말(도전용 — 정답을 하나로 정할 수 없다)', 'challenge'),
}
STY = ['정중한 존댓말', '짧은 반말투 구어체', '메신저 말투(줄임말 가능)', '급한 말투', '여행 온 외국인 같은 서툰 한국어']
REQ_SCHEMA = {'type': 'object', 'properties': {'reqs': {'type': 'array', 'items': {'type': 'object', 'properties': {'cat': {'type': 'string'}, 'q': {'type': 'string'}, 'item': {'type': ['integer', 'null']}}}}}}
LAB_SCHEMA = {'type': 'object', 'properties': {'answers': {'type': 'array', 'items': {'type': 'object', 'properties': {'id': {'type': 'integer'}, 'item': {'type': ['integer', 'null']}}}}}}
NAT_SCHEMA = {'type': 'object', 'properties': {'blends': {'type': 'array', 'items': {'type': 'object', 'properties': {'cat': {'type': 'string'}, 'blend': {'type': 'string'}, 'request_only': {'type': 'string'}, 'item': {'type': ['integer', 'null']}}}}}}

# Claude 가 쓴 합성 잡담(D3 의 synth_chat_A/B) — LLM 자연 혼합의 말투 힌트로만 보낸다(AI Hub · KoCulture 원문은 안 보낸다)
D3 = json.load(open(os.path.join(EP, 'all_prompts_d3.json'), encoding='utf-8'))
CLAUDE_CHAT = [QRE.search(x['prompt']).group(1).strip() for x in D3 if x['type'].startswith('synth_chat')]


def jl(path, key='k'):
    out = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            r = json.loads(line)
            if 'error' not in r:
                out[r[key]] = r
    return out


def run_pool(todo, fn, path, label):
    f = open(path, 'a', encoding='utf-8')
    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as ex:
        for n, rec in enumerate(ex.map(fn, todo)):
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            f.flush()
            print(label, n + 1, '/', len(todo), round(time.time() - t0), '초', 'ERR' if 'error' in rec else 'ok', flush=True)


def gen_prompt(head, k):
    sty = ', '.join(random.Random(a.seed + k).sample(STY, 3))
    cats = '\n'.join(f'- {k} ({n}개): {d}' for k, (n, d, _) in CATS.items())
    return (f'{head}\n\n위는 여행 일정 안내 챗봇이 가진 고객의 일정이다. 챗봇은 고객 말이 일정의 **항목 하나**를 가리키면 그 번호를, 아니면 「없음」(null)을 고른다.\n'
            f'당신의 일은 시험 문장 「요청 부분」을 만드는 것이다. **잡담은 넣지 말고** 그 요청 한 문장만 쓴다(나중에 다른 잡담을 앞뒤에 붙인다). 한국어, 10~50자, 서로 완전히 다르게, 말투는 다음을 섞어라: {sty}.\n\n'
            f'## 범주와 개수\n{cats}\n\n'
            '조건: ①정답이 항목 하나인 문장(MX1 · MX2 · MX6a)은 item 에 그 번호를 쓰고, 사람이 봐도 그 항목 하나로 정해져야 한다. 일정에 같은 장소가 두 번 이상 나오면 그 장소 항목은 날짜 · 순서 · 시각으로 방문을 특정하거나 아예 쓰지 마라 '
            '②정답 없음 범주(MX3 · MX4 · MX5a · MX5b)는 일정의 어떤 항목도 가리키지 않아야 하고 item 은 null ③MX6b 는 item 을 null 로 ④각 문장에 cat 을 정확히 적어라 ⑤같은 문장 · 같은 구조를 반복하지 마라. 파일을 만들거나 명령을 실행하지 말고 JSON 한 개로만 답하라.')


def run_gen():
    done = jl(GEN)
    todo = [(k, h) for k, h in SEL if k not in done]
    print('gen', a.gen_model, '남은', len(todo), '/', len(SEL), flush=True)

    def one(kh):
        k, h = kh
        val, sec, err = call(a.gen_model, gen_prompt(h, k), REQ_SCHEMA, timeout=900)
        return {'k': k, 'error': err, 'sec': round(sec, 1)} if val is None else {'k': k, 'sec': round(sec, 1), 'reqs': val['reqs']}
    run_pool(todo, one, GEN, 'gen')


def req_list(g):
    out, seen = [], set()
    for x in g['reqs']:
        q = x['q'].strip()
        if q and q not in seen and x['cat'] in CATS:
            seen.add(q)
            out.append((x['cat'], q, x['item']))
    random.Random(a.seed + 7).shuffle(out)
    return [(i, c, q, it) for i, (c, q, it) in enumerate(out)]


LAB_RULE = ('위 일정을 가진 고객이 챗봇에게 아래 문장들을 각각 따로 보냈다. 각 문장이 가리키는 일정 항목 번호 하나를 item 에 넣어라. 문장이 이 일정에 없는 장소 · 일반 정보 · 다른 식당 · 다른 명소를 묻거나, '
            '아무것도 묻지 않거나, 새 항목 추가 · 일정 전체 변경이거나, 어느 항목인지 하나로 정할 수 없으면 null. 확실하지 않으면 null.')


def run_label():
    G, done = jl(GEN), jl(LAB)
    todo = [(k, h) for k, h in SEL if k in G and k not in done]
    print('label', a.label_model, '남은', len(todo), '/', len(SEL), flush=True)

    def one(kh):
        k, h = kh
        U = req_list(G[k])
        lines = '\n'.join(f'{i}. {q}' for i, _, q, _ in U)
        val, sec, err = call(a.label_model, f'{h}\n\n{LAB_RULE}\n\n{lines}\n\n문장마다 {{"id": 문장 번호, "item": 번호 또는 null}} 을 answers 배열에 담아 JSON 한 개로만 답하라. 파일을 만들거나 명령을 실행하지 마라.', LAB_SCHEMA, timeout=900)
        if val is None:
            return {'k': k, 'error': err}
        return {'k': k, 'sec': round(sec, 1), 'answers': {str(x['id']): x['item'] for x in val['answers']}, 'utts': [[i, c, q, it] for i, c, q, it in U]}
    run_pool(todo, one, LAB, 'label')


NAT_CATS = [('MX1', 1), ('MX2', 1), ('MX3', 1), ('MX4', 1), ('MX5a', 1)]


def nat_prompt(head, k):
    hints = random.Random(a.seed + k).sample(CLAUDE_CHAT, 10)
    hint = '\n'.join(f'- {x}' for x in hints)
    cats = '\n'.join(f'- {c}: {CATS[c][1]}' for c, _ in NAT_CATS)
    return (f'{head}\n\n위는 여행 일정 안내 챗봇이 가진 고객의 일정이다. 챗봇은 고객 말이 일정의 항목 하나를 가리키면 그 번호를, 아니면 null 을 고른다.\n'
            f'**잡담이 섞인 자연스러운 한 문장**(혼합 문장) 5개를 만들어라 — 고객이 잡담(날씨 · 기분 · 일상 · 농담 등)을 하다가 같은 말 안에서 요청이나 질문을 섞는다. 잡담은 아래 예시 말투를 참고하되 베끼지 말고, 앞 · 뒤 · 중간 어디든 자연스러운 곳에 둔다. 한국어, 25~90자.\n'
            f'잡담 말투 예시:\n{hint}\n\n범주(각 1개씩):\n{cats}\n\n'
            '각 항목에 blend(혼합 문장), request_only(그 문장에서 잡담을 빼고 요청만 남긴 한 문장), cat, item(정답 항목 번호 또는 null)을 적어라. 조건: 정답이 항목 하나인 범주는 사람이 봐도 그 항목 하나로 정해져야 하고, '
            '정답 없음 범주는 일정의 어떤 항목도 가리키지 않아야 한다. 같은 장소가 일정에 두 번 이상 나오면 날짜 · 순서 · 시각으로 방문을 특정하거나 쓰지 마라. 파일을 만들거나 명령을 실행하지 말고 JSON 한 개로만 답하라.')


def run_nat():
    done = jl(NAT)
    todo = [(k, h) for k, h in SEL if k not in done]
    print('nat', a.gen_model, '남은', len(todo), '/', len(SEL), flush=True)

    def one(kh):
        k, h = kh
        val, sec, err = call(a.gen_model, nat_prompt(h, k), NAT_SCHEMA, timeout=900)
        return {'k': k, 'error': err, 'sec': round(sec, 1)} if val is None else {'k': k, 'sec': round(sec, 1), 'blends': val['blends']}
    run_pool(todo, one, NAT, 'nat')


def run_natlabel():
    N, done = jl(NAT), jl(NLAB)
    todo = [(k, h) for k, h in SEL if k in N and k not in done]
    print('natlabel', a.label_model, '남은', len(todo), '/', len(SEL), flush=True)

    def one(kh):
        k, h = kh
        U = []
        for j, b in enumerate(N[k]['blends']):
            U.append((2 * j, 'blend', b['blend'].strip(), b['cat'], b['item']))
            U.append((2 * j + 1, 'req', b['request_only'].strip(), b['cat'], b['item']))
        random.Random(a.seed + k).shuffle(U)
        lines = '\n'.join(f'{i}. {q}' for i, _, q, _, _ in U)
        val, sec, err = call(a.label_model, f'{h}\n\n{LAB_RULE}\n\n{lines}\n\n문장마다 {{"id": 문장 번호, "item": 번호 또는 null}} 을 answers 배열에 담아 JSON 한 개로만 답하라. 파일을 만들거나 명령을 실행하지 마라.', LAB_SCHEMA, timeout=900)
        if val is None:
            return {'k': k, 'error': err}
        return {'k': k, 'sec': round(sec, 1), 'answers': {str(x['id']): x['item'] for x in val['answers']}, 'utts': [list(u) for u in U]}
    run_pool(todo, one, NLAB, 'natlabel')


# ---------------------------------------------------------------- 조립
def tri(t):
    t = re.sub(r'\s+', '', t)
    return {t[i:i + 3] for i in range(max(1, len(t) - 2))}


def jac(x, y):
    return len(x & y) / max(1, len(x | y))


CONN = ['', '', '아 맞다, ', '그건 그렇고 ', '참, ', '근데 ', '그나저나 ', '아 그리고 ', '그런데 ']


def build():
    rnd = random.Random(a.seed)
    L, NL = jl(LAB), jl(NLAB)
    N = jl(NAT)
    # 잡담 조각(로컬): D 잡담 · D2 · Claude 합성. 길이 8~45자
    pool = []
    for p in P:
        if p['type'] == 'chitchat':
            pool.append((QRE.search(p['prompt']).group(1).strip(), 'D(AI Hub·KoCulture)'))
    for x in json.load(open(os.path.join(EP, 'all_prompts_d2.json'), encoding='utf-8')):
        pool.append((QRE.search(x['prompt']).group(1).strip(), 'D2(AI Hub·KoCulture)'))
    for x in D3:
        if x['type'].startswith('synth_chat'):
            pool.append((QRE.search(x['prompt']).group(1).strip(), 'Claude 합성'))
    pool = [(t, s) for t, s in pool if 8 <= len(t) <= 45 and '\n' not in t]
    print('잡담 조각', len(pool), {s: sum(1 for _, x in pool if x == s) for s in {s for _, s in pool}})
    items, drop = [], {'nolabel': 0, 'dispute': 0, 'overlap_item': 0}
    disputes = []
    n = 1200000
    pid = 0
    stats = {}

    def item_toks(head):
        toks = set()
        for ln in head.split('\n'):
            if re.match(r'^\d+\. ', ln):
                toks |= tri(ln.split('] ', 1)[-1])
        return toks

    def add(kind, cat, q, gold, k, head, src, pair, chat=None, pos=None, req=None):
        nonlocal n
        n += 1
        items.append({'i': n, 'set': 'mx', 'qi': len(items), 'type': f'mx_{cat}_{kind}', 'cat': cat, 'kind': kind, 'gold': gold, 'itin': k, 'src': src, 'pair': pair, 'chat_src': chat, 'pos': pos, 'q': q, 'req': req,
                      'prompt': head + '고객 질문: ' + q + '\n\n' + tail})

    # 1) 코드 이어 붙이기
    for k, h in SEL:
        if k not in L:
            continue
        itk = item_toks(h)
        for i, cat, q, gold in L[k]['utts']:
            lab = L[k]['answers'].get(str(i), 'missing')
            if cat == 'MX6b':
                pid += 1
                add('challenge', cat, q, None, k, h, 'code', pid)
                continue
            if lab == 'missing':
                drop['nolabel'] += 1
                continue
            if lab != gold:
                drop['dispute'] += 1
                disputes.append({'k': k, 'cat': cat, 'q': q, 'gen_item': gold, 'luna_item': lab, 'src': 'code'})
                continue
            cands = [(t, s) for t, s in pool if len(tri(t) & itk) <= 1 or jac(tri(t), itk) < 0.04]   # 잡담이 일정 항목 낱말과 겹치면 정답이 흐려지므로 거른다
            if not cands:
                drop['overlap_item'] += 1
                continue
            chat, csrc = rnd.choice(cands)
            conn = rnd.choice(CONN)
            pos = rnd.choice(['pre', 'post'])
            mixed = f'{chat} {conn}{q}'.replace('  ', ' ') if pos == 'pre' else f'{q} {conn.strip() + " " if conn.strip() else ""}{chat}'.replace('  ', ' ')
            pid += 1
            add('mixed', cat, mixed, gold, k, h, 'code', pid, csrc, pos, q)
            add('control', cat, q, gold, k, h, 'code', pid, None, None, q)
    # 2) LLM 자연 혼합: 혼합 문장과 요청만 문장을 둘 다 루나가 라벨해 둘이 모두 의도와 같을 때만
    for k, h in SEL:
        if k not in NL or k not in N:
            continue
        U = {u[0]: u for u in NL[k]['utts']}
        for u in NL[k]['utts']:
            pass
        ans = NL[k]['answers']
        by_pair = {}
        for i, kind, q, cat, gold in NL[k]['utts']:
            by_pair.setdefault((cat, gold, q if kind == 'req' else None), None)
        # 문장 짝 복원: nat 원본의 순서로
        for b in N[k]['blends']:
            bl, rq = b['blend'].strip(), b['request_only'].strip()
            ib = next((i for i, kind, q, c, g in NL[k]['utts'] if kind == 'blend' and q == bl), None)
            ir = next((i for i, kind, q, c, g in NL[k]['utts'] if kind == 'req' and q == rq), None)
            if ib is None or ir is None:
                drop['nolabel'] += 1
                continue
            if ans.get(str(ib), 'm') != b['item'] or ans.get(str(ir), 'm') != b['item']:
                drop['dispute'] += 1
                disputes.append({'k': k, 'cat': b['cat'], 'q': bl, 'req': rq, 'gen_item': b['item'], 'luna_blend': ans.get(str(ib)), 'luna_req': ans.get(str(ir)), 'src': 'llm'})
                continue
            pid += 1
            add('mixed', b['cat'], bl, b['item'], k, h, 'llm', pid, 'Claude 합성 말투(솔 6.1 작성)', 'natural', rq)
            add('control', b['cat'], rq, b['item'], k, h, 'llm', pid, None, None, rq)
    # 3) 학습 · 다른 시험 문장과 겹침 검사(요청 부분 기준, 자카드 0.6 이상이면 격리)
    seen_q = []
    for f in (os.path.join(HERE, 'results', 'hard_set', 'h_set_test_30_20261015.json'),):
        seen_q += [x['q'] for x in json.load(open(f, encoding='utf-8'))]
    ht = os.path.join(HERE, 'results', 'hard_set', 'h_set_train_60_20261016.json')
    if os.path.exists(ht):
        seen_q += [x['q'] for x in json.load(open(ht, encoding='utf-8'))]
    seen_t = [tri(q) for q in seen_q]
    quarantined = set()
    for it in items:
        if it['kind'] == 'control' and it['req']:
            t = tri(it['req'])
            if max((jac(t, s) for s in seen_t), default=0) >= 0.6:
                quarantined.add(it['pair'])
    for it in items:
        it['quarantine'] = it['pair'] in quarantined
    main = [x for x in items if x['kind'] in ('mixed', 'control') and not x['quarantine']]
    chal = [x for x in items if x['kind'] == 'challenge']
    json.dump(disputes, open(os.path.join(OUT, 'mx_disputes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)   # 사람 골든셋 후보(솔과 루나가 갈린 것)
    json.dump(items, open(os.path.join(OUT, 'mx_all.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(main, open(os.path.join(OUT, 'mx_main_prompts.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    # 사람 점검용 표본(층화 300, 혼합 문장만): 생성 방식 · 유형별
    mixed = [x for x in main if x['kind'] == 'mixed']
    rnd.shuffle(mixed)
    sample, cnt = [], {}
    for x in mixed:
        key = (x['src'], x['cat'])
        if cnt.get(key, 0) < (14 if x['src'] == 'code' else 12):
            cnt[key] = cnt.get(key, 0) + 1
            sample.append(x)
    import csv
    with open(os.path.join(OUT, 'mx_human_check_sample.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['id', '유형', '생성 방식', '고객 입력(혼합)', '요청만(대조)', '일정 번호(일정 파일)', '기계 정답(번호/없음)', '사람 판정(번호/없음/애매)', '메모'])
        for x in sample:
            w.writerow([x['i'], x['cat'], x['src'], x['q'], x['req'], x['itin'], x['gold'] if x['gold'] is not None else '없음', '', ''])
    by = {}
    for x in main:
        by.setdefault((x['src'], x['cat'], x['kind']), 0)
        by[(x['src'], x['cat'], x['kind'])] += 1
    print('항목', len(items), '/ 시험 입력(혼합+대조, 격리 제외)', len(main), '/ 격리 쌍', len(quarantined), '/ 도전', len(chal), '/ 버린 것', drop)
    for key in sorted(by):
        print('  ', key, by[key])
    json.dump({'items': len(items), 'main': len(main), 'quarantined_pairs': len(quarantined), 'challenge': len(chal), 'dropped': drop,
               'by': {'|'.join(k): v for k, v in by.items()}, 'itineraries': len(SEL), 'seed': a.seed, 'human_sample': len(sample)},
              open(os.path.join(HERE, 'results', 'mx_set_report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


{'gen': run_gen, 'label': run_label, 'nat': run_nat, 'natlabel': run_natlabel, 'build': build}[a.step]()
