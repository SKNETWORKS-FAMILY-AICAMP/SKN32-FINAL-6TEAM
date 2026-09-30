# 「문장에서 뽑은 자리표(day·pos·kind·meal·rel·anchor·kw·nextday)로 일정 관계를 따라가 항목을 확정」하는 코드. 모델은 값을 만들지 않고 자리표만 낸다.
#  resolve() 결과: ('item', id) 확정 · ('none',) 일정 밖 · ('fallback',) 자리표만으로는 하나로 안 정해짐(직접 짚기 결과를 쓴다)
#  pos 는 이름('first'…'seventh'·'last', 모델이 냄) 또는 정수(1부터, 규칙이 냄)
POS = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'sixth': 6, 'seventh': 7}
MEAL = {'breakfast': (0, 1100), 'lunch': (1100, 1500), 'dinner': (1700, 2400)}   # 시작 시각(HHMM) 창


def _hhmm(s):
    return int(s.replace(':', ''))


def _norm(v):
    return None if v in (None, 'none') else v


def resolve(items, slots):
    its = sorted(items, key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in its})
    ids = [i['id'] for i in its]
    byid = {i['id']: i for i in its}
    day, pos, kind, meal, rel, anchor, kw = (_norm(slots.get(k)) for k in ('day', 'pos', 'kind', 'meal', 'rel', 'anchor', 'kw'))
    nextday = bool(slots.get('nextday'))
    if anchor is not None and anchor not in byid:
        anchor = None
    # 기준 항목이 말한 날과 다른 날이면 모델이 잘못 짚은 것 — 버린다(날짜 규칙이 더 믿을 만하다)
    if anchor is not None and day and day != 'beyond' and byid[anchor]['date'] != days[int(day[1:]) - 1]:
        anchor = None
    if nextday and anchor is not None:            # 「~ 다음날 첫 일정」: 기준 항목의 다음 날
        k = days.index(byid[anchor]['date']) + 2
        day = f'd{k}' if k <= len(days) else 'beyond'
        anchor = None
        rel = None
    if day == 'beyond':
        return ('none',)

    def cand():
        c = its
        if day:
            c = [i for i in c if i['date'] == days[int(day[1:]) - 1]]
        if meal:
            lo, hi = MEAL[meal]
            c = [i for i in c if i['kind'] == 'dining' and lo <= _hhmm(i['start']) < hi]
        elif kind:
            c = [i for i in c if i['kind'] == kind]
        if kw:
            c = [i for i in c if kw in i['title']]
        return c

    def pick(c):                                  # pos 로 후보 목록에서 하나 고른다 (없으면 None)
        if pos == 'last':
            return c[-1] if c else None
        n = pos if isinstance(pos, int) else POS.get(pos)
        return c[n - 1] if (n and 0 < n <= len(c)) else None

    has_filter = bool(day or kind or meal or kw)
    if rel:
        a = anchor
        if pos and has_filter:                    # 「첫 체크인 바로 전」 「마지막 체크아웃 다음」 — 순서와 조건으로 기준 항목을 정한다
            it = pick(cand())
            if it is None:
                return ('none',)
            a = it['id']
        elif a is None:
            c = cand() if has_filter else []
            if len(c) != 1:
                return ('fallback',)
            a = c[0]['id']
        j = ids.index(a) + (1 if rel == 'next' else -1)
        return ('item', ids[j]) if 0 <= j < len(ids) else ('none',)
    if pos:
        if not has_filter:
            return ('fallback',)
        it = pick(cand())
        return ('item', it['id']) if it else ('none',)
    c = cand() if has_filter else []
    return ('item', c[0]['id']) if len(c) == 1 else ('fallback',)
