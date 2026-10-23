# 어려운 보류 세트 H — Codex 솔 6.1 이 「오지목을 유발하는 말」(정답 없음)과 「정답 있는 대조 말」을 일정마다 만들고, 다른 모델(루나 6.0)이 같은 질의문 규칙으로 따로 라벨을 달아 둘이 맞은 것만 쓴다.
#  왜: D · D2 · D3 에서 잡담 오지목이 0~0.4% 로 바닥이라 더 줄이는 효과를 잴 수 없다 → 일부러 오지목이 나기 쉬운 문장으로 위쪽 여유를 만든다. 같은 도구로 나중에 지도셋(학습용)도 만든다(--split train).
#  외부 서비스(Codex)로는 **일정 프롬프트(우리가 합성한 일정)와 모델이 만든 문장만** 오간다 — AI Hub · KoCulture 문장은 보내지 않는다.
#  단계: gen(일정마다 솔이 문장 생성) → label(일정마다 루나가 50문장을 한꺼번에 라벨) → build(합의한 것만 H 세트 프롬프트로 조립).
# 사용: python build_hard_set.py gen|label|build [--n 30] [--seed 20261015] [--gen-model gpt-6.1-sol] [--label-model gpt-6-luna] [--split test|train]
import argparse
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture, TRAP_SENTENCES, TRAP_SENTENCES_TRAIN  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
sys.stdout.reconfigure(encoding='utf-8')
from codex_percall import call  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('step', choices=['gen', 'label', 'build'])
ap.add_argument('--n', type=int, default=30)
ap.add_argument('--seed', type=int, default=20261015)
ap.add_argument('--gen-model', default='gpt-6.1-sol')
ap.add_argument('--label-model', default='gpt-6-luna')
ap.add_argument('--split', default='test', choices=['test', 'train'])
ap.add_argument('--workers', type=int, default=3)
ap.add_argument('--heads-file', default='', help='일정 머리를 이 jsonl(행마다 prompt)의 고유 일정에서 고른다 — 학습용(--split train)은 D 시험과 겹치지 않는 학습 자료의 일정을 쓴다')
a = ap.parse_args()

OUT = str(TRAP_SENTENCES if a.split == 'test' else TRAP_SENTENCES_TRAIN)   # 시험용 · 학습용을 다른 폴더에
os.makedirs(OUT, exist_ok=True)
P = json.load(open(fixture('all_prompts.json'), encoding='utf-8'))
heads, tail = {}, None
for p in P:
    h, rest = p['prompt'].split('고객 질문: ', 1)
    heads.setdefault(h, 0)
    heads[h] += 1
    tail = tail or rest.split('\n\n', 1)[1]
if a.heads_file:   # 학습용: 학습 자료의 일정(D 시험의 일정과 겹치지 않음을 확인한 것만)
    _h = {}
    for _l in open(a.heads_file, encoding='utf-8'):
        _h[json.loads(_l)['prompt'].split('고객 질문: ', 1)[0]] = 1
    _ban = set(heads)
    heads = {k: 1 for k in _h if k not in _ban}
    assert heads, '학습 일정이 모두 D 시험 일정과 겹친다'
HEADS = sorted(heads)                       # 시험용: 89개 고유 일정(D 시험의 일정) · 학습용: 학습 자료의 일정(D 와 안 겹침)
rnd = random.Random(a.seed)
pick = rnd.sample(range(len(HEADS)), a.n)   # 시험용 일정 n개(나머지는 따로 둔다)
SEL = [(k, HEADS[k]) for k in sorted(pick)]
tag = f'{a.split}_{a.n}_{a.seed}'
GEN = os.path.join(OUT, f'gen_{tag}.jsonl')
LAB = os.path.join(OUT, f'label_{tag}.jsonl')
SET = os.path.join(OUT, f'h_set_{tag}.json')

CATS = {
    'N1': '일정에 나온 장소·음식 낱말을 가볍게 말하지만 그 항목에 대한 질문 · 요청이 아닌 잡담 · 감상 · 추억 (예: 「정동길 사진 봤는데 단풍 예쁘더라」). 항목을 묻지 않아야 한다',
    'N2': '이 일정에 **없는** 다른 장소 · 식당 · 명소를 묻는 말. 일정의 항목과 이름이나 종류가 비슷하되 다른 곳이어야 한다 (예: 일정에 「성북동면옥집」이 있으면 「성수동 냉면집은 어때요」)',
    'N3': '일정과 무관한 일반 여행 정보 · 서비스 질문 (날씨 · 환전 · 교통카드 · 팁 문화 · 심카드 · 공항 수하물 · 앱 사용법 등)',
    'N4': '지시어나 감탄만 있고 **어느 항목인지 알 수 없는** 짧은 말 (예: 「그거 얼마야」 「여기 괜찮아?」 「배고프다」). 일정만 봐서는 특정 항목 하나로 정할 수 없어야 한다',
    'N5': '일정 전체에 대한 감정 · 불만 · 변경 의사 표현으로 특정 항목을 지정하지 않은 말 (예: 「일정이 너무 빡빡해요」 「둘째 날은 좀 쉬고 싶네」)',
    'N6': '일정의 항목과 같은 종류의 활동을 하고 싶다는 말이지만 이미 있는 항목이 아니라 **새로 추가** 하고 싶다는 말 (예: 「박물관 하나 더 가고 싶은데」)',
}
POS = {
    'P1': '항목의 이름을 그대로 쓴 질문 · 요청 (시간 · 장소 · 변경 · 취소 · 정보)',
    'P2': '이름을 줄이거나 별칭 · 오타 · 구어체로 부른 질문 (예: 「배재학당 몇 시까지예요」)',
    'P3': '날짜 · 순서 · 시각으로 가리킨 질문 (예: 「둘째 날 점심」 「세 번째 일정」 「오후 2시 거」)',
    'P4': '이름 없이 내용 설명으로 가리킨 질문 (예: 「미술관 가는 거」 「호텔에서 먹는 아침」). 일정에서 하나로 정해져야 한다',
}
STY = ['정중한 존댓말', '짧은 반말투 구어체', '메신저 말투(줄임말 · ㅋㅋ 가능)', '급한 말투', '여행 온 외국인 같은 서툰 한국어']

GEN_SCHEMA = {'type': 'object', 'properties': {
    'negatives': {'type': 'array', 'items': {'type': 'object', 'properties': {'cat': {'type': 'string'}, 'q': {'type': 'string'}}}},
    'positives': {'type': 'array', 'items': {'type': 'object', 'properties': {'cat': {'type': 'string'}, 'q': {'type': 'string'}, 'item': {'type': 'integer'}}}}}}


def gen_prompt(head, seed_k):
    sty = ', '.join(rnd.sample(STY, 3))
    neg = '\n'.join(f'- {k}: {v}' for k, v in CATS.items())
    pos = '\n'.join(f'- {k}: {v}' for k, v in POS.items())
    return (f'{head}\n\n위는 여행 일정 안내 챗봇이 가진 고객의 일정이다. 챗봇은 고객 말이 일정의 **항목 하나**를 가리키면 그 번호를 고르고, 아니면 「없음」으로 답해야 한다.\n'
            f'당신의 일은 이 챗봇이 **헷갈리기 쉬운** 시험 문장을 만드는 것이다. 한국어로, 문장은 15~60자, 서로 완전히 다르게, 말투는 다음을 섞어라: {sty}.\n\n'
            f'## 정답이 「없음」인 문장(범주마다 5개, 총 30개)\n{neg}\n\n'
            f'## 정답이 항목 하나인 대조 문장(범주마다 4개, 총 16개) — item 에 그 항목 번호를 쓴다\n{pos}\n\n'
            '조건: ①정답 없음 문장은 일정의 어떤 항목도 가리키지 않아야 한다(사람이 봐도 「없음」이 분명하도록; 애매하면 만들지 마라) ②대조 문장은 사람이 봐도 그 항목 하나로 정해져야 한다 '
            '③예시 문장을 그대로 베끼지 마라 ④일정에 있는 이름을 정답 없음 문장에 일부러 섞어 챗봇을 유혹하라(N1 · N2 · N6). '
            '파일을 만들거나 명령을 실행하지 말고 JSON 한 개로만 답하라.')


def run_gen():
    done = set()
    if os.path.exists(GEN):
        for line in open(GEN, encoding='utf-8'):
            r = json.loads(line)
            if 'error' not in r:
                done.add(r['k'])
    todo = [(k, h) for k, h in SEL if k not in done]
    print('gen', a.gen_model, '남은', len(todo), '/', len(SEL), flush=True)
    f = open(GEN, 'a', encoding='utf-8')

    def one(kh):
        k, h = kh
        val, sec, err = call(a.gen_model, gen_prompt(h, k), GEN_SCHEMA, timeout=900)
        if val is None:
            return {'k': k, 'error': err, 'sec': round(sec, 1)}
        return {'k': k, 'sec': round(sec, 1), 'negatives': val['negatives'], 'positives': val['positives']}
    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as ex:
        for n, rec in enumerate(ex.map(one, todo)):
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            f.flush()
            print('gen', n + 1, '/', len(todo), round(time.time() - t0), '초', 'ERR' if 'error' in rec else len(rec.get('negatives', [])) + len(rec.get('positives', [])), flush=True)


LAB_SCHEMA = {'type': 'object', 'properties': {'answers': {'type': 'array', 'items': {'type': 'object', 'properties': {'id': {'type': 'integer'}, 'item': {'type': ['integer', 'null']}}}}}}


def load_gen():
    G = {}
    for line in open(GEN, encoding='utf-8'):
        r = json.loads(line)
        if 'error' not in r:
            G[r['k']] = r
    return G


def utts(g):
    """일정 하나의 문장 목록 → [(id, cat, q, gold)] (섞인 순서 · 중복 문장 제거)."""
    out, seen = [], set()
    for x in g['negatives']:
        q = x['q'].strip()
        if q and q not in seen:
            seen.add(q)
            out.append((x['cat'], q, None))
    for x in g['positives']:
        q = x['q'].strip()
        if q and q not in seen:
            seen.add(q)
            out.append((x['cat'], q, x['item']))
    random.Random(a.seed + 7).shuffle(out)
    return [(i, c, q, g_) for i, (c, q, g_) in enumerate(out)]


def run_label():
    G = load_gen()
    done = set()
    if os.path.exists(LAB):
        for line in open(LAB, encoding='utf-8'):
            r = json.loads(line)
            if 'error' not in r:
                done.add(r['k'])
    todo = [(k, h) for k, h in SEL if k in G and k not in done]
    print('label', a.label_model, '남은', len(todo), '/', len(SEL), flush=True)
    f = open(LAB, 'a', encoding='utf-8')

    def one(kh):
        k, h = kh
        U = utts(G[k])
        lines = '\n'.join(f'{i}. {q}' for i, _, q, _ in U)
        pr = (f'{h}\n\n위 일정을 가진 고객이 챗봇에게 아래 문장들을 각각 따로 보냈다. 각 문장이 가리키는 일정 항목 번호 하나를 item 에 넣어라. 문장이 이 일정에 없는 장소 · 일반 정보 · 다른 식당 · 다른 명소를 묻거나 어느 항목인지 정할 수 없으면 null. 확실하지 않으면 null.\n\n{lines}\n\n'
              '문장마다 {"id": 문장 번호, "item": 번호 또는 null} 을 answers 배열에 담아 JSON 한 개로만 답하라. 파일을 만들거나 명령을 실행하지 마라.')
        val, sec, err = call(a.label_model, pr, LAB_SCHEMA, timeout=900)
        if val is None:
            return {'k': k, 'error': err}
        return {'k': k, 'sec': round(sec, 1), 'answers': {str(x['id']): x['item'] for x in val['answers']}, 'utts': [[i, c, q, g_] for i, c, q, g_ in U]}
    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as ex:
        for n, rec in enumerate(ex.map(one, todo)):
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            f.flush()
            print('label', n + 1, '/', len(todo), round(time.time() - t0), '초', 'ERR' if 'error' in rec else len(rec['answers']), flush=True)


def run_build():
    L = {}
    for line in open(LAB, encoding='utf-8'):
        r = json.loads(line)
        if 'error' not in r:
            L[r['k']] = r
    items, stats = [], {}
    n = 900000 + (100000 if a.split == 'train' else 0) + 50000
    for k, h in SEL:
        if k not in L:
            continue
        for i, cat, q, gold in L[k]['utts']:
            lab = L[k]['answers'].get(str(i), 'missing')
            if lab == 'missing':
                status = 'nolabel'
            elif lab == gold:
                status = 'agree'
            else:
                status = 'dispute'
            key = (cat, status)
            stats[key] = stats.get(key, 0) + 1
            items.append({'i': n, 'set': 'h', 'qi': len(items), 'type': 'hard_' + cat, 'gold': gold, 'status': status, 'label_other': None if lab == 'missing' else lab, 'itin': k,
                          'q': q, 'prompt': h + '고객 질문: ' + q + '\n\n' + tail})
            n += 1
    json.dump(items, open(SET, 'w', encoding='utf-8'), ensure_ascii=False)
    agree = [x for x in items if x['status'] == 'agree']
    json.dump(agree, open(SET.replace('.json', '_agree.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(len(items), '문장 중 합의', len(agree), '/ 이견', sum(1 for x in items if x['status'] == 'dispute'))
    for c in list(CATS) + list(POS):
        print(c, {s: stats.get((c, s), 0) for s in ('agree', 'dispute', 'nolabel')})


{'gen': run_gen, 'label': run_label, 'build': run_build}[a.step]()
