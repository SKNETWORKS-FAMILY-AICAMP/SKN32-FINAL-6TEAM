# 문장에서 자리표(day·pos·kind·meal·rel·kw·nextday)를 규칙(정규식)으로 읽는다. 기준 항목(anchor)은 모델(Jev·Gemma)이 짚는다.
#  못 읽으면 None — 그때만 모델이 낸 자리표로 채우는 조합도 eval_ord.py 에서 잰다.
#  한국어 표현 전반(첫째·둘째 / 이틀째·사흘째 / 요일 / 번째 / 첫·마지막 / 다음·전·앞·끝나고)을 기준으로 썼고 특정 시험 문장에 맞추지 않았다.
import re
from datetime import date

NATIVE = {'첫': 1, '둘': 2, '셋': 3, '넷': 4, '다섯': 5, '여섯': 6, '일곱': 7, '여덟': 8, '아홉': 9, '열': 10}      # ~째
SPAN = {'이틀': 2, '사흘': 3, '나흘': 4, '닷새': 5, '엿새': 6, '이레': 7, '여드레': 8, '아흐레': 9, '열흘': 10}   # ~째(며칠째)
NUMW = {'한': 1, '두': 2, '세': 3, '네': 4, '다섯': 5, '여섯': 6, '일곱': 7, '여덟': 8, '아홉': 9, '열': 10}      # ~번째
POSNAME = {1: 'first', 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth', 6: 'sixth', 7: 'seventh'}
WD = '월화수목금토일'


def _pos_of(n):
    return n   # 정수(1부터) — slot_lookup 이 후보 개수와 견줘 일정 밖을 가른다


def rule_slots(q, items):
    its = sorted(items, key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in its})
    nd = len(days)
    s = q
    out = {'day': None, 'pos': None, 'kind': None, 'meal': None, 'rel': None, 'kw': None, 'nextday': False}

    def dayval(n):
        return f'd{n}' if 1 <= n <= nd else 'beyond'

    # ---- 날짜
    m = re.search(r'다음\s?날|이튿날|익일', s)
    if m:
        out['nextday'] = True
        s = s[:m.start()] + ' ' + s[m.end():]
    m = re.search(r'(첫날|첫째\s?날)', s)
    if m:
        out['day'] = 'd1'
        s = s[:m.start()] + ' ' + s[m.end():]
    if not out['day']:
        m = re.search(r'마지막\s?날|last day', s)
        if m:
            out['day'] = f'd{nd}'
            s = s[:m.start()] + ' ' + s[m.end():]
    if not out['day']:
        m = re.search(r'(첫|둘|셋|넷|다섯|여섯|일곱|여덟|아홉|열)째\s?날', s)
        if m:
            out['day'] = dayval(NATIVE[m.group(1)])
            s = s[:m.start()] + ' ' + s[m.end():]
    if not out['day']:
        m = re.search(r'(이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘)째', s)
        if m:
            out['day'] = dayval(SPAN[m.group(1)])
            s = s[:m.start()] + ' ' + s[m.end():]
    if not out['day']:
        m = re.search(r'(\d+)\s?(?:일\s?차|일째|째\s?날)', s)
        if m:
            out['day'] = dayval(int(m.group(1)))
            s = s[:m.start()] + ' ' + s[m.end():]
    if not out['day']:
        m = re.search(r'([월화수목금토일])요일', s)
        if m:
            wd = WD.index(m.group(1))
            hit = [k for k, d in enumerate(days) if date.fromisoformat(d).weekday() == wd]
            out['day'] = f'd{hit[0] + 1}' if hit else 'beyond'
            s = s[:m.start()] + ' ' + s[m.end():]

    # ---- 순서 (남은 문장에서. 「~째」 뒤에 「날」이 없는 서수는 순서로 본다)
    m = re.search(r'(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s?번째|(\d+)\s?번째|(첫|둘|셋|넷|다섯|여섯|일곱|여덟|아홉|열)째', s)
    if m:
        if m.group(1):
            out['pos'] = _pos_of(NUMW[m.group(1)])
        elif m.group(2):
            out['pos'] = _pos_of(int(m.group(2)))
        else:
            out['pos'] = _pos_of(NATIVE[m.group(3)])
        s = s[:m.start()] + ' ' + s[m.end():]
    elif re.search(r'마지막', s):
        out['pos'] = 'last'
    elif re.search(r'(?<![가-힣])첫(?![가-힣]*날)|처음|맨\s?앞|(?<![가-힣])시작', s):
        out['pos'] = 'first'

    # ---- 끼니·종류
    if re.search(r'아침', s):
        out['meal'] = 'breakfast'
    elif re.search(r'점심|브런치|런치', s):
        out['meal'] = 'lunch'
    elif re.search(r'저녁|디너|야식', s):
        out['meal'] = 'dinner'
    if re.search(r'체크\s?아웃', s):
        out['kind'], out['kw'] = 'lodging', '체크아웃'
    elif re.search(r'체크\s?인', s):
        out['kind'], out['kw'] = 'lodging', '체크인'
    elif re.search(r'숙소|호텔', s):
        out['kind'] = 'lodging'
    elif re.search(r'식사|식당|먹|밥|카페|간식', s):
        out['kind'] = 'dining'
    elif re.search(r'이동|지하철|공항철도|이동수단', s):
        out['kind'] = 'mobility'
    elif re.search(r'활동|관광|관람|산책|구경', s):
        out['kind'] = 'activity'

    # ---- 앞뒤
    if re.search(r'(?<![가-힣])(?:바로\s*)?(?:앞|직전)(?![가-힣])|가기\s?전|하기\s?전|(?<![가-힣])전(?:에|의|\s|$)', s):
        out['rel'] = 'prev'
    if re.search(r'다음|(?<![가-힣])뒤|끝나고|끝나면|끝난\s?뒤|이후|후에', s):
        out['rel'] = 'next' if not out['rel'] else out['rel']
    return out
