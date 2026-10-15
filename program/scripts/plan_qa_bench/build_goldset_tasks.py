# 요청 둘(compound_intent) 66문제의 「말한 항목 목록」(gold_set)을 정하는 과제 파일 — 기존 정답(gold)은 보여 주지 않고 문제 문장과 일정만 준다.
#  채점 방식 B(말한 항목이면 모두 정답)·C(둘 다 찾기)의 정답 목록 재료. 하위 작업이 항목 번호 목록(말한 순서)을 JSON 으로 낸다.
# 사용: python build_goldset_tasks.py <출력 폴더>   → <출력 폴더>/goldset_task.md · goldset_index.json(과제 번호 → 세트·문제 번호)
import json, os, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
W = '월화수목금토일'
SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
L = ['# 과제 — 고객 문장이 가리키는 일정 항목을 모두 찾기', '',
     '각 문제는 서로 다른 세트(여행 일정)의 고객 채팅 한 줄이다. 한 문장에 요청이 둘 이상 들어 있다. 문제마다 **그 문장이 가리키는 일정 항목 번호를, 문장에서 말한 순서대로 전부** 적는다.',
     '규칙: ① 일정에 실제로 있는 항목만 쓴다(없는 장소는 쓰지 않는다) ② 문장이 가리키는 항목이 하나뿐이면 하나만 ③ 가리키는 항목이 일정에 하나도 없으면 빈 목록 ④ 같은 장소가 일정에 여러 번 나오면 문장이 말한 쪽(요일·순서 단서)을 고른다.', '']
idx = {}
n = 0
for w in SETS:
    job = json.load(open(fixture(f'{w}.json'), encoding='utf-8'))['sets'][w]
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in items})

    def lab(i):
        d = date.fromisoformat(i['date'])
        return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"
    L += [f'## 세트 {w} — 오늘은 {job["today"]}', '일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):', *[lab(i) for i in items], '']
    for k, q in enumerate(job['qs']):
        if q['type'] != 'compound_intent':
            continue
        n += 1
        idx[f'{w}:{k}'] = n
        L.append(f'### 문제 {w}-{k}')
        if q.get('history'):
            L += ['앞 대화:'] + [f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in q['history']]
        L += [f"고객 질문: {q['q']}", '']
open(os.path.join(OUT, 'goldset_task.md'), 'w', encoding='utf-8').write('\n'.join(L))
json.dump(idx, open(os.path.join(OUT, 'goldset_index.json'), 'w'), ensure_ascii=False)
print('요청 둘 문제', n)
