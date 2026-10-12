# 서버에서: Jev 계열 소형 결정 모델(학습 없이, 영점)이 여행 고객 메시지 네 가지 라벨(의도 · 감정 · 긴급도 · 대상 종류)을 얼마나 맞히는지 잰다.
#  한 메시지에 질문 4개를 한 번에 보낸다(Jev 계열의 「한 상태 · 여러 질문」 방식 — 선택지 설명을 criteria 로 준다). 모델에게 우리 학습 자료는 주지 않는다.
#  출력은 llm_cls_*.json 과 같은 모양({시험파일: {preds:[{id,intent,sentiment,severity,case_type}], lat_median_s, n}}) + 확률(probs)이라 cls_report.py 가 그대로 읽는다.
# 사용: python3 jev_cls_run.py <백엔드> <태그> <시험파일,...> [--lang ko|en] [--model <모델id>] [--url <systemone주소>] [--device cpu|cuda]
#   백엔드: laya(laya.load) · opendecider(opendecider.load) · systemone(llama.cpp /v1/systemone — Winnow-E4B 등)
import json, os, sys, time, urllib.request
if os.environ.get('JEV_THREADS'):   # 서버 코어가 많고 다른 작업이 겹치면 스레드 과다 경쟁으로 크게 느려진다 — 개수를 제한한다
    import torch
    torch.set_num_threads(int(os.environ['JEV_THREADS']))

BACK, TAG, TESTS = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
a = sys.argv[4:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
LANG, MODEL, URL, DEVICE = opt('--lang', 'ko'), opt('--model'), opt('--url'), opt('--device', 'cpu')

DEF = {
    'ko': {
        'intent': ('고객 메시지의 요청 종류는 무엇인가?', {
            'itinerary_submit': '여행 일정을 보내거나 등록·검증해 달라는 말',
            'incident_report': '이미 일어난 문제(늦음·휴무·매진·날씨·길 막힘·분실·사고)를 알리는 말',
            'confirm_request': '영업시간·이동 시간·예약 상태 등을 묻거나 확인해 달라는 말',
            'adjust_reject': '일정을 바꿔 달라·취소해 달라·원래대로 되돌려 달라, 또는 제안을 거절하는 말',
            'other': '인사·잡담·감사·의미 없는 말·서비스 범위 밖 요청'}),
        'case_type': ('고객 메시지가 말하는 대상은 무엇인가?', {
            'activity': '관광·체험·공연·쇼핑 등 여행지에서 하는 활동',
            'dining': '식당·카페',
            'mobility': '지하철·버스·택시·도보·공항 이동',
            'booking': '예약·결제·취소·변경 같은 예약 기록',
            'lodging': '숙소',
            'flight': '항공편',
            'other': '대상이 없거나 전체 일정·잡담'}),
        'sentiment': ('고객의 감정은 무엇인가?', {
            'positive': '만족·기쁨·감사',
            'neutral': '감정 표현 없이 사실을 말하거나 요청',
            'negative': '불만·불안·짜증·걱정·당황'}),
        'severity': ('이 메시지는 얼마나 급한가?', {
            'low': '급하지 않다. 일반 문의·여유 있는 변경·잡담',
            'medium': '곧 처리해야 하지만 당장 일정이 깨지지는 않는다(오늘 안·내일 일정 확인/변경, 약간의 지연)',
            'high': '지금~1~2시간 안의 일정에 지장이 생기고 있거나 곧 생긴다(이미 늦음·문 닫음·길 막힘·매진 직전)',
            'critical': '안전·건강·귀국편 놓침·여권 분실·사고처럼 즉시 조치가 필요하다'}),
    },
    'en': {
        'intent': ('What kind of request is this travel customer message?', {
            'itinerary_submit': 'sending or registering a trip itinerary and asking to register/validate it',
            'incident_report': 'reporting a problem that already happened (running late, closed, sold out, weather, blocked road, lost item, accident)',
            'confirm_request': 'asking or requesting confirmation (opening hours, travel time, booking status)',
            'adjust_reject': 'asking to change, cancel or revert the plan, or rejecting a proposal',
            'other': 'greeting, small talk, thanks, meaningless input, or a request outside the service'}),
        'case_type': ('What is the message about?', {
            'activity': 'sightseeing, experiences, shows, shopping — things to do at the destination',
            'dining': 'restaurants and cafes',
            'mobility': 'subway, bus, taxi, walking, airport transfer',
            'booking': 'reservation, payment, cancellation or change records',
            'lodging': 'accommodation',
            'flight': 'flights',
            'other': 'no particular target, the whole itinerary, or small talk'}),
        'sentiment': ('What is the customer feeling?', {
            'positive': 'satisfaction, joy, gratitude',
            'neutral': 'no emotion, just facts or a request',
            'negative': 'complaint, anxiety, irritation, worry, panic'}),
        'severity': ('How urgent is this message?', {
            'low': 'not urgent: general question, relaxed change, small talk',
            'medium': 'needs handling soon but the schedule is not breaking right now (today/tomorrow checks or changes, slight delay)',
            'high': 'the schedule within the next 1-2 hours is being or about to be disrupted (already late, closed, blocked road, almost sold out)',
            'critical': 'safety, health, missing the return flight, lost passport, accident — immediate action needed'}),
    },
}[LANG]
HEADS = ['intent', 'sentiment', 'severity', 'case_type']


def questions():
    return {h: {'type': 'choice', 'instructions': DEF[h][0], 'criteria': DEF[h][1]} for h in HEADS}


if BACK == 'laya':
    import laya
    agent = laya.load(MODEL or 'convaiinnovations/laya-multilingual', device=DEVICE)

    def ask(msg):
        r = agent.predict(msg, questions())['answers']
        return {h: (r[h].get('probabilities') or {}) for h in HEADS}
elif BACK == 'opendecider':
    from opendecider import Choice, load
    model = load(MODEL or 'manjunathshiva/opendecider-small', device=DEVICE if DEVICE != 'cpu' else None, dtype='bfloat16' if (DEVICE != 'cpu' and 'nano' in (MODEL or '')) else None)

    def ask(msg):
        qs = {h: Choice(DEF[h][0], dict(DEF[h][1])) for h in HEADS}
        r = model.system_one({'message': msg}, qs)['answers']
        return {h: (r[h].get('probabilities') or {}) for h in HEADS}
elif BACK == 'systemone':
    def ask(msg):
        body = {'state': {'customer_message': msg}, 'questions': questions()}
        if MODEL:
            body['model'] = MODEL
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        r = json.load(urllib.request.urlopen(req, timeout=600))
        r = r.get('answers') or r
        return {h: (r[h].get('probabilities') or {}) for h in HEADS}
else:
    raise SystemExit('백엔드는 laya · opendecider · systemone 중 하나')

try:
    ask('안녕하세요')   # 예열
except Exception as e:  # noqa: BLE001
    print('예열 실패(첫 호출 오류):', repr(e)[:300], flush=True)

out, errs = {}, 0
for t in TESTS:
    rows = [json.loads(l) for l in open(t, encoding='utf-8')]
    res, lat = [], []
    for r in rows:
        t0 = time.perf_counter()
        try:
            pr = ask(r['message'])
        except Exception as e:  # noqa: BLE001
            pr, errs = {h: {} for h in HEADS}, errs + 1
            if errs <= 3:
                print('오류:', repr(e)[:200], flush=True)
        lat.append(time.perf_counter() - t0)
        if len(lat) % 25 == 0:
            print(TAG, t, f'{len(lat)}/{len(rows)}', '건당 중앙', round(sorted(lat)[len(lat) // 2], 2), '초', flush=True)
        res.append({'id': r['id'], **{h: (max(pr[h], key=pr[h].get) if pr[h] else None) for h in HEADS}, 'probs': pr})
    out[t] = {'preds': res, 'lat_median_s': sorted(lat)[len(lat) // 2], 'n': len(rows), 'errors': errs}
    print(TAG, t, len(rows), '중앙 지연', round(out[t]['lat_median_s'], 3), '초 · 오류', errs, flush=True)
json.dump(out, open(f'jev_cls_{TAG}.json', 'w', encoding='utf-8'), ensure_ascii=False)
