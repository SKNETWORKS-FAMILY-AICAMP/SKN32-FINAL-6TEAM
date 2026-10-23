# 작은 모델 전문가 호출용 과제 파일 만들기: 문제마다 절 분석(clauses.py)으로 대상 절·제외 절을 정하고, 서버에서 세 가지를 묻는다.
#  gate  : 이 메시지가 일정 항목에 관한 것인가(잡담·일반 정보면 false)          — 전체 문장 + 앞 대화
#  anchor: 글에 이름·설명으로 언급된 일정 항목은? (앞뒤 관계의 기준 항목)         — 대상 절 / (말고 문장이면) 제외 절
#  point : 대상 절이 가리키는 항목은? (없으면 null)                              — 대상 절 + 앞 대화
# 사용: python build_tasks.py <job 이름>  → fixtures/tasks_<job>.json (서버에 올린다)
import json, os, sys
from clauses import analyze
HERE = os.path.dirname(os.path.abspath(__file__))
job = sys.argv[1]
st = json.load(open(os.path.join(HERE, 'fixtures', job + '.json'), encoding='utf-8'))['sets'][job]
qs = []
for x in st['qs']:
    a = analyze(x['q'])
    qs.append({'full': x['q'], 'tt': a['tt'], 'excl': a['excl'], 'history': x.get('history') or []})
json.dump({'today': st['today'], 'items': st['items'], 'qs': qs}, open(os.path.join(HERE, 'fixtures', f'tasks_{job}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(job, len(qs), '문제 · 대상 절이 전체와 다른 문제', sum(q['tt'] != q['full'] for q in qs))
