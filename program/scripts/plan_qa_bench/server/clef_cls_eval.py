# 서버에서: 올라마 Clef 계열 결정 모델로 cs 프로젝트의 여행 분류 평가 자료(golden 72)를 한 요청에 세 질문(요청 종류 5 · 담당 팀 접두 7(other 포함) · 감정 3)으로 푼다.
#  holdout 은 이 파일에서 다루지 않는다(프롬프트를 다 고친 뒤 마지막에 한 번만). 결정 모델이라 결과가 결정적이다(반복 편차 없음).
# 사용: DEC_MODEL=clef-flash DEC_URL=http://127.0.0.1:11434/v1/systemone python clef_cls_eval.py travel_golden.jsonl  → clef_cls_<모델>.json
import json, os, sys, time, urllib.request, collections

URL, MODEL = os.environ['DEC_URL'], os.environ['DEC_MODEL']
rows = [json.loads(l) for l in open(sys.argv[1], encoding='utf-8')]
INTENT = {'itinerary_submit': '고객이 여행 일정을 보내거나 등록한다', 'incident_report': '무언가 잘못됐다고 알린다(늦음·닫음·매진·날씨 같은 사건)',
          'confirm_request': '질문하거나 무엇을 확인해 달라고 한다', 'adjust_reject': '바꿔 달라고 하거나 다른 선택지를 달라고 하거나 바뀐 것을 되돌려 달라고 한다(예: 다른 데로 바꿔 줘, 원래대로 돌려 줘)',
          'other': '위 어느 것도 아니다'}
TEAM = {'activity': '여행지에서 하는 활동(관광·체험·쇼핑·공연)에 관한 일', 'dining': '식당·식사에 관한 일', 'mobility': '이동(교통·길찾기·택시·지하철)에 관한 일',
        'booking': '예약·결제·환불에 관한 일', 'lodging': '숙소에 관한 일', 'flight': '항공편에 관한 일', 'other': '위 어느 팀의 일도 아니다(인사·잡담·일반 질문)'}
SENT = {'positive': '고객 말투가 긍정적이다', 'neutral': '고객 말투가 중립적이다', 'negative': '고객 말투가 부정적이다(불만·걱정·화)'}


def ask(msg):
    body = {'model': MODEL, 'state': msg, 'questions': {
        'intent': {'type': 'choice', 'instructions': '이 여행 고객 메시지는 어떤 종류의 요청인가?', 'criteria': INTENT},
        'team': {'type': 'choice', 'instructions': '이 메시지는 어느 담당 팀의 일인가?', 'criteria': TEAM},
        'sentiment': {'type': 'choice', 'instructions': '고객의 감정은 어떤가?', 'criteria': SENT}}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    r = json.load(urllib.request.urlopen(req, timeout=600))
    out = {}
    for q, a in (r.get('answers') or {}).items():
        p = a.get('probabilities') or {}
        out[q] = {'pick': max(p, key=p.get) if p else None, 'probs': p}
    return out


res, t0 = [], time.time()
for r in rows:
    try:
        a = ask(r['message'])
    except Exception as e:  # noqa: BLE001
        a = {'error': str(e)[:120]}
    res.append({'case_id': r['case_id'], 'gold_intent': r['expected_intent'], 'gold_team': r['expected_issue_code'].split('_')[0], 'gold_sentiment': r['expected_sentiment'], 'pred': a})
sec = (time.time() - t0) / len(rows)
summ = {}
for key, gk in (('intent', 'gold_intent'), ('team', 'gold_team'), ('sentiment', 'gold_sentiment')):
    ok = sum(1 for x in res if (x['pred'].get(key) or {}).get('pick') == x[gk])
    summ[key] = f'{ok}/{len(res)}'
conf = collections.Counter((x['gold_intent'], (x['pred'].get('intent') or {}).get('pick')) for x in res)
json.dump({'model': MODEL, 'n': len(res), 'sec_per_case': sec, 'summary': summ, 'confusion_intent': {f'{a}->{b}': c for (a, b), c in conf.items()}, 'rows': res},
          open(f'clef_cls_{MODEL}.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(MODEL, summ, f'{sec:.2f}초/건', {f'{a}->{b}': c for (a, b), c in conf.items() if a != b})
