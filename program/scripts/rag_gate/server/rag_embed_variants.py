# 서버에서: 규정 검색이 「무엇을 임베딩하느냐」에 따라 얼마나 달라지나 — 운영은 직원용 본문(content)을 임베딩하지만 고객에게 보이는 것은 고객용 문장(line)이다.
#  변형: A 본문(운영) · B 고객용 문장 · C 절 제목 + 고객용 문장 · D 본문 + 고객용 문장 · E 문서 제목 + 절 제목 + 고객용 문장
#  지표: 정답 줄이 상위 k(고객용 문장이 있는 절 중) 안에 드는 비율 @1·@3·@5, 답 없음 질문의 1위 점수 평균(문턱 분리력)
#  주의: 질문을 고객용 문장을 보고 Codex 가 썼으므로 B·C·E 변형은 낱말이 겹쳐 유리하다(낙관적).
import json, math, sys, urllib.request
CH = json.load(open('policy_chunks.json', encoding='utf-8'))
QS = json.load(open('rag_questions.json', encoding='utf-8'))['questions']


def embed(texts):
    out = []
    for k in range(0, len(texts), 16):
        r = urllib.request.Request('http://127.0.0.1:11434/api/embed', data=json.dumps({'model': 'bge-m3', 'input': texts[k:k + 16]}).encode(), headers={'content-type': 'application/json'})
        out += json.loads(urllib.request.urlopen(r, timeout=600).read())['embeddings']
    return out


def cos(a, b):
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b)))


qv = embed([q['q'] for q in QS])
V = {
    'A_본문(운영)': lambda c: c['content'],
    'B_고객용문장': lambda c: c['line'] or c['content'],
    'C_절제목+고객용문장': lambda c: f"{c['section']}: {c['line'] or c['content']}",
    'D_본문+고객용문장': lambda c: c['content'] + ' ' + (c['line'] or ''),
    'E_문서제목+절제목+고객용문장': lambda c: f"{c['doc_title']} / {c['section']}: {c['line'] or c['content']}",
}
res = {}
for name, f in V.items():
    cv = embed([f(c) for c in CH])
    sims = [[cos(q, c) for c in cv] for q in qv]
    res[name] = sims
    ans = [i for i, q in enumerate(QS) if q['type'] == 'answerable']
    hit = {1: 0, 3: 0, 5: 0}
    for qi in ans:
        order = [CH[i]['source'] for i in sorted(range(len(CH)), key=lambda i: -sims[qi][i]) if CH[i]['line']]
        for k in hit:
            hit[k] += bool(set(order[:k]) & set(QS[qi]['gold']))
    none = [max(sims[i][j] for j in range(len(CH)) if CH[j]['line']) for i, q in enumerate(QS) if q['type'] in ('uncovered', 'offtopic')]
    pos = [max(sims[i][j] for j in range(len(CH)) if CH[j]['line']) for i in ans]
    print(f"{name}: @1 {hit[1]}/{len(ans)} @3 {hit[3]}/{len(ans)} @5 {hit[5]}/{len(ans)} · 1위 점수 평균 답 있음 {sum(pos) / len(pos):.3f} 답 없음(코퍼스에 없음·주제 밖) {sum(none) / len(none):.3f}", flush=True)
json.dump({'sources': [c['source'] for c in CH], 'variants': res}, open('rag_embed_variants.json', 'w'))
