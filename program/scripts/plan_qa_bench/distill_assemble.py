# 증류 파일럿 학습 자료 조립 — 검증을 통과한 문제만 모아 학습용(train)·검증용(val) JSONL 로 만든다.
#  제외: ① 독립 풀이와 정답이 어긋난 문제(distill_verify.py 가 남긴 verify_<pid>.json) ② 평가 세트(heavy·mix4~12)와 문장이 같거나 거의 같은 문제
#        (공백 뺀 문장 일치, 또는 글자 2-gram 자카드 ≥ NEAR). 평가 장소와 겹치는 일정은 build_distill.py 가 이미 0 으로 확인했다.
#  분할: 여행자 단위 — VAL_P 에 든 여행자는 통째로 검증용(학습에 안 쓴 새 일정에서 되는지 본다). 나머지는 학습용.
#  프롬프트: server/llm_point_heavy.py 49~51행과 같은 문장(규칙 문장 없음) + 형식 지시 한 줄(SFX). 정답 형식 {"item": 번호|null}. 요청 둘(compound_intent)은 먼저 언급된 항목(gold)을 정답으로 한다.
# 사용: python distill_assemble.py [--no-compound] [--near 0.8]   → fixtures/distill/train.jsonl · val.jsonl · results/distill_assemble_report.json
import json, os, re, sys
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
D = os.path.join(HERE, 'fixtures', 'distill')
args = sys.argv[1:]
NO_COMPOUND = '--no-compound' in args
NEAR = float(args[args.index('--near') + 1]) if '--near' in args else 0.8
PIDS = [f'p{i:02d}' for i in range(1, 11)]
VAL_P = {'p09', 'p10'}
EVAL = ['heavy', 'mix4', 'mix5', 'mix6', 'mix7', 'mix8', 'mix9', 'mix10', 'mix11', 'mix12']
W = '월화수목금토일'
# 올라마는 JSON 형식을 서버가 강제하지만 직접 읽는 모델은 그렇지 않아, llm_point_var.py 의 SFX 와 같은 지시를 붙인다(학습·검증·평가·무학습 기준선 모두 같은 문장).
SFX = '\n\n답은 JSON 한 줄로만: {"item": 번호} 또는 {"item": null}'


def norm(s):
    return re.sub(r'\s+', '', s)


def grams(s):
    s = norm(s)
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


ev_exact, ev_grams = set(), []
for w in EVAL:
    f = fixture(f'{w}.json')
    if os.path.exists(f):
        for q in json.load(open(f, encoding='utf-8'))['sets'][w]['qs']:
            ev_exact.add(norm(q['q']))
            ev_grams.append(grams(q['q']))
print('평가 문장', len(ev_exact), '(공백 뺀 서로 다른 문장) ·', len(ev_grams), '(2-gram 집합)')


def near_eval(q):
    g = grams(q)
    for e in ev_grams:
        if len(g & e) / len(g | e) >= NEAR:
            return True
    return False


def prompt(job, items, x):
    def lab(i):
        d = date.fromisoformat(i['date'])
        return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"
    plan = '\n'.join(lab(i) for i in items)
    hist = ''
    if x.get('history'):
        hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
    return (f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n{hist}"
            f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
            "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null." + SFX)


rep = {'near_threshold': NEAR, 'no_compound': NO_COMPOUND, 'val_personas': sorted(VAL_P), 'per_persona': {}}
out = {'train': [], 'val': []}
for pid in PIDS:
    name = f'distill_{pid}'
    job = json.load(open(os.path.join(D, f'{name}.json'), encoding='utf-8'))['sets'][name]
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in items})
    mism = set(json.load(open(os.path.join(D, f'verify_{pid}.json')))['mismatch_idx'])
    split = 'val' if pid in VAL_P else 'train'
    c = Counter()
    for k, x in enumerate(job['qs']):
        if k in mism:
            c['제외_풀이불일치'] += 1
            continue
        if norm(x['q']) in ev_exact:
            c['제외_평가문장일치'] += 1
            continue
        if near_eval(x['q']):
            c['제외_평가문장유사'] += 1
            continue
        if NO_COMPOUND and x['type'] == 'compound_intent':
            c['제외_요청둘'] += 1
            continue
        out[split].append({'persona': pid, 'idx': k, 'type': x['type'], 'gold': x['gold'], 'prompt': prompt(job, items, x),
                           'completion': json.dumps({'item': x['gold']}, ensure_ascii=False)})
        c['사용'] += 1
    rep['per_persona'][pid] = {'split': split, **dict(c)}
    print(pid, split, dict(c))
for s in ('train', 'val'):
    with open(os.path.join(D, f'{s}.jsonl'), 'w', encoding='utf-8') as f:
        for r in out[s]:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    n = len(out[s])
    nn = sum(r['gold'] is None for r in out[s])
    rep[s] = {'n': n, 'null': nn, 'null_ratio': round(nn / max(1, n), 3), 'by_type': dict(Counter(r['type'] for r in out[s])),
              'avg_prompt_chars': round(sum(len(r['prompt']) for r in out[s]) / max(1, n))}
    print(s, rep[s])
json.dump(rep, open(os.path.join(HERE, 'results', 'distill_assemble_report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
