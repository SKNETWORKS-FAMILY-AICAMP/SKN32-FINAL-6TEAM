# Claude 모델(하위 작업)이 세트 하나를 한 번에 푸는 과제 파일을 만든다 — 클로드 CLI 로그인이 막혔을 때의 대체 경로.
#  질의문은 올라마 직접 짚기와 같은 문장이다. 정답은 넣지 않고, 유형 묶음(같은 유형 16개가 붙어 있음)이 힌트가 되지 않게 문제 순서를 시드로 섞는다.
# 사용: python claude_batch_tasks.py <출력 폴더> <세트들,쉼표>   → <출력 폴더>/task_<세트>.md · perm_<세트>.json(섞은 순서 → 원래 번호)
import json, os, random, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
OUT, SETS = sys.argv[1], sys.argv[2].split(',')
os.makedirs(OUT, exist_ok=True)
W = '월화수목금토일'
for name in SETS:
    _f = os.path.join(HERE, 'fixtures', f'{name}.json')
    if not os.path.exists(_f):
        _f = os.path.join(HERE, 'fixtures', 'distill', f'{name}.json')
    job = json.load(open(_f, encoding='utf-8'))['sets'][name]
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in items})

    def lab(i):
        d = date.fromisoformat(i['date'])
        return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"
    perm = list(range(len(job['qs'])))
    random.Random(20261004).shuffle(perm)
    L = [f"# 과제 — 여행 일정 질문 분류 ({len(perm)}문제)", '',
         f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):", '', *[lab(i) for i in items], '',
         '아래 고객 질문들은 서로 관계가 없다. **각 질문을 따로 독립적으로** 풀어라(다른 질문의 답을 참고하지 않는다). 질문마다 그 질문이 가리키는 일정 항목 번호 하나를 고른다.',
         '질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null. 질문에 「앞 대화」가 있으면 그 대화를 읽고 푼다.', '']
    for n, k in enumerate(perm):
        x = job['qs'][k]
        L.append(f'## 문제 {n}')
        if x.get('history'):
            L.append('앞 대화:')
            L += [f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']]
        L += [f"고객 질문: {x['q']}", '']
    open(os.path.join(OUT, f'task_{name}.md'), 'w', encoding='utf-8').write('\n'.join(L))
    json.dump(perm, open(os.path.join(OUT, f'perm_{name}.json'), 'w'))
    print(name, len(perm), '문제 · 항목', len(items))
