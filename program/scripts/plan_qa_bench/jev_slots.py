# Jev 로 자리표(day·pos·kind·meal·rel·anchor)를 뽑는다. slot_lookup.resolve 가 항목을 확정하고, 확정 못 하면 「직접 짚기」 결과로 대신한다(eval_ord2.py).
#  한 문장에 질문 6개를 한 요청으로 보낸다(Jev 문서: 묶음이 개별 호출보다 싸고 빠름). 키는 jev_run.py 와 같은 방식(값은 출력·저장 안 함).
# 사용: python jev_slots.py <job 이름>   → results/jev_slots_<job>.json (문제별 자리표 + 선택 확률)
import json, os, sys, time, urllib.request, urllib.error
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
jobname = sys.argv[1]


def load_key():
    k = os.environ.get('ACOP_JEV_API_KEY', '').strip()
    if k:
        return k
    p = os.path.join(HERE, '..', '..', '..', 'final_project_cs', '.env')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            line = line.strip()
            if line.startswith('ACOP_JEV_API_KEY') and '=' in line:
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''


key = load_key() or sys.exit('키가 없습니다')
job = json.load(open(os.path.join(HERE, 'fixtures', jobname + '.json'), encoding='utf-8'))['sets']


def call(body):
    for a in range(6):
        req = urllib.request.Request('https://api.typesafe.ai/v1/systemone', data=json.dumps(body).encode(),
                                     headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
        try:
            return json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            if e.code in (429, 529) and a < 5:
                time.sleep(2 ** a)
                continue
            sys.exit(f'HTTP {e.code}: {e.read().decode()[:200]}')


W = '월화수목금토일'
out = {}
for s, st in job.items():
    items = sorted(st['items'], key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in items})
    dcrit = {}
    for k, d in enumerate(days):
        dd = date.fromisoformat(d)
        tail = ', 첫날' if k == 0 else (', 마지막 날' if k == len(days) - 1 else '')
        dcrit[f'd{k + 1}'] = f"{k + 1}일차 ({dd.month}/{dd.day} {W[dd.weekday()]}요일{tail})"
    dcrit['beyond'] = f'여행 기간({len(days)}일) 밖의 날짜·일차'
    dcrit['none'] = '몇째 날인지·요일·날짜를 말하지 않음'
    acrit = {f"item_{i['id']}": f"{i['date'][5:]} {i['start']} {i['title']} @ {i['place']}" for i in items}
    acrit['none'] = '메시지에 이름이나 설명으로 언급된 기준 일정이 없음'
    rows = []
    for x in st['qs']:
        qn = {
            'day': {'type': 'choice', 'instructions': '고객 메시지가 말하는 여행 날짜(몇째 날·요일·첫날·마지막 날)는?', 'criteria': dcrit},
            'pos': {'type': 'choice', 'instructions': '그 날(또는 조건에 맞는 일정들) 안에서 몇 번째를 말하는가? 순서를 말하지 않으면 none', 'criteria': {
                'first': '첫 번째·처음·첫', 'second': '두 번째', 'third': '세 번째', 'fourth': '네 번째', 'fifth': '다섯 번째', 'sixth': '여섯 번째',
                'seventh': '일곱 번째', 'last': '마지막', 'none': '순서를 말하지 않음'}},
            'kind': {'type': 'choice', 'instructions': '고객이 말하는 일정의 종류는? 종류를 말하지 않으면 none', 'criteria': {
                'dining': '식사·식당·카페', 'activity': '관광·활동·관람·산책', 'lodging': '숙소·체크인·체크아웃', 'mobility': '이동·이동수단', 'none': '종류를 말하지 않음'}},
            'meal': {'type': 'choice', 'instructions': '끼니를 말하는가? 말하지 않으면 none', 'criteria': {
                'breakfast': '아침 식사', 'lunch': '점심 식사', 'dinner': '저녁 식사', 'none': '끼니를 말하지 않음'}},
            'rel': {'type': 'choice', 'instructions': '기준 일정의 앞뒤 관계를 묻는가? (「~ 다음」「~ 끝나고」「~ 뒤」 = next, 「~ 전」「~ 앞」「~ 가기 전」 = prev)', 'criteria': {
                'next': '기준 일정 바로 다음', 'prev': '기준 일정 바로 전', 'none': '앞뒤 관계를 묻지 않음'}},
            'anchor': {'type': 'choice', 'instructions': '고객 메시지에 이름이나 설명으로 언급된 기준 일정 항목은 어느 것인가?', 'criteria': acrit},
        }
        r = call({'model': 'jev-latest', 'state': {'today': st['today'], 'customer_message': x['q']}, 'questions': qn})
        a = r.get('answers') or r
        sl, pr = {}, {}
        for k in qn:
            v = a[k]
            c = v.get('choice')
            sl[k] = int(c.split('_')[1]) if (k == 'anchor' and c and c != 'none') else c
            pr[k] = round(max(v.get('probabilities', {}).values() or [0]), 3)
        rows.append({'slots': sl, 'p': pr})
    out[s] = rows
res = os.path.join(HERE, 'results', f'jev_slots_{jobname}.json')
json.dump(out, open(res, 'w', encoding='utf-8'), ensure_ascii=False)
print('저장', res, sum(len(v) for v in out.values()), '문제')
