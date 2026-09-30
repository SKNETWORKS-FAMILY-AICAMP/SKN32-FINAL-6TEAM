# 「문장에서 뽑은 자리표(day·pos·kind·meal·rel·anchor·kw·nextday)로 일정 관계를 따라가 항목을 확정」하는 코드. 모델은 값을 만들지 않고 자리표만 낸다.
#  resolve() 결과: ('item', id, 근거) 확정 · ('none', None, 근거) 일정 밖 · ('fallback', None, 근거) 자리표만으로는 안 정해짐(모델에게 넘김)
#                 · ('clarify', [id…], 근거) 후보가 2~5개로 남음 — 모델이 찍지 않고 후보를 보여 주며 되묻는다(latweave=True 일 때만)
#  latweave=True (LatWeave 2609.27225 의 「구조적 기권」 반영): ① 조건을 걸었는데 후보가 0개면 모델 없이 「일정에 없음」 ② 날짜가 있고 후보가 2~5개면 되묻기.
#  세 번째 값은 답의 근거(어떤 조건으로 후보 몇 개가 남았는지) — 그대로 기록해 두면 답을 재현·검토할 수 있다.
#  pos 는 이름('first'…'seventh'·'last', 모델이 냄) 또는 정수(1부터, 규칙이 냄)
POS = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'sixth': 6, 'seventh': 7}
MEAL = {'breakfast': (0, 1100), 'lunch': (1100, 1500), 'dinner': (1700, 2400)}   # 시작 시각(HHMM) 창


def _hhmm(s):
    return int(s.replace(':', ''))


def _norm(v):
    return None if v in (None, 'none') else v


def resolve(items, slots, latweave=False):
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
        return ('none', None, f'날짜 {len(days)}일 밖')

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
                return ('none', None, '기준 항목의 순서가 후보 범위 밖')
            a = it['id']
        elif a is None:
            c = cand() if has_filter else []
            if len(c) != 1:
                return ('fallback', None, f'앞뒤 관계인데 기준 항목 불명(조건 후보 {len(c)}개)')
            a = c[0]['id']
        j = ids.index(a) + (1 if rel == 'next' else -1)
        why = f"기준 항목 {a} 의 {'다음' if rel == 'next' else '앞'}"
        return ('item', ids[j], why) if 0 <= j < len(ids) else ('none', None, why + ' — 끝이라 없음')
    if pos:
        if not has_filter:
            return ('fallback', None, '순서만 있고 조건 없음')
        c = cand()
        it = pick(c)
        why = f"조건(날={day} 종류={kind} 끼니={meal} 키워드={kw}) 후보 {len(c)}개 중 {pos}번째"
        return ('item', it['id'], why) if it else ('none', None, why + ' — 범위 밖')
    if not has_filter:
        return ('fallback', None, '구조 조건 없음')
    c = cand()
    why = f"조건(날={day} 종류={kind} 끼니={meal} 키워드={kw}) 후보 {len(c)}개"
    if len(c) == 1:
        return ('item', c[0]['id'], why)
    if latweave and not c:
        return ('none', None, why + ' — 후보 0개(구조적 기권)')
    if latweave and day and 2 <= len(c) <= 5:
        return ('clarify', [i['id'] for i in c], why + ' — 되묻기')
    return ('fallback', None, why)
