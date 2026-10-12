# 우리 과제 전용 소형 재평가 모델 학습 자료 만들기.
#  - 장소·문장은 Codex(출제자)가 썼다(places_1~8.json · oos.json). 시험 세트(heavy·mix4·ord)는 Claude 가 따로 썼고 이 자료와 장소가 겹치지 않는다.
#  - 여기서는 코드가 일정(항목 40~55개, 7일)을 무작위로 만들고, 문장마다 정답 항목(들)을 알고 있으므로 라벨은 만들어질 때 정해진다.
#  - 문제 종류: 이름·별칭·오타·채팅체·설명·요청·정보(정답 있음) / 일정에 없는 장소(정답 없음, 풀에서 뽑음) / 일정 무관 문장(정답 없음)
#  - 쌍: 정답 항목 + 어려운 오답(글자 겹침 상위 6개) + 무작위 오답 4개. 정답 없음은 어려운 오답 6 + 무작위 4 전부 라벨 0.
#  - 검증: 장소의 20% 를 학습에서 빼 두고(처음 보는 장소) 그 장소가 든 일정·문장으로 검증.
# 사용: python gen_train.py <places 폴더> → fixtures/train_pairs.json {'train': [...], 'val': [...]}
import glob, json, os, random, sys
from datetime import date, timedelta

SRC = sys.argv[1]                       # 자료 폴더(쉼표로 여러 개 가능 — 첫 폴더의 oos.json 을 쓴다)
OUTNAME = os.environ.get('OUT', 'train_pairs.json')
GRAPH = os.environ.get('GRAPH') == '1'       # 1 이면 문서에 그래프 이웃(앞·뒤 일정, 같은 장소 몇 번째 방문)을 덧붙인다(§42 V6). 난수는 쓰지 않아 문제·정답은 그대로다
HERE = os.path.dirname(os.path.abspath(__file__))
rnd = random.Random(20260930)
places = []
for _d in SRC.split(','):
    for f in sorted(glob.glob(os.path.join(_d, 'places_*.json'))):
        places += json.load(open(f, encoding='utf-8'))['places']
oos = [x['q'] for x in json.load(open(os.path.join(SRC.split(',')[0], 'oos.json'), encoding='utf-8'))['queries']]
W = '월화수목금토일'
EXCL = ['경복궁', '창덕궁', '덕수궁', '종묘', '서울역', '우래옥', '삼청동수제비', '서울공예박물관', '어니언', '청계천', '광장시장', '국립민속박물관',
        '토속촌', '통인시장', '블루보틀', '광화문광장', '하동관', '리움', '전쟁기념관', '이문설농탕', '국립중앙박물관', '명동교자', '남대문시장', '서울로7017',
        '여의도한강공원', '성수동카페거리', '서울숲', '뚝섬한강공원', '연남동', '홍대걷고싶은거리', '발우공양', '교보문고', '태극당', '인사동쌈지길', '북촌한옥마을',
        '에그슬럿', 'L7명동', '스테이서촌', '서울역사박물관',
        # mix5(새 독립 세트) 장소 — 학습에서 제외
        '미진', '청와대', '국립고궁박물관', '국립한글박물관', '을지면옥', '국립극장', '테라로사', '마로니에공원', '대학로곱창골목', '합정역', '절두산', '진주집', '상상마당',
        '앤트러사이트', '경의선책거리', '마포소금구이', '신라스테이', '용산역', '용산가족공원', '부대찌개골목', '디뮤지엄', '파르나스', '삼원가든', '양재시민의숲', '서래마을',
        '롯데월드몰', '이화벽화마을', '익선동', '북촌손만두', '효자베이커리', '광화문집', '서울역사편찬원', '센터커피서울숲']
seen, clean = set(), []
for p in places:
    n = p['name'].replace(' ', '')
    if n in seen or any(e in n for e in EXCL):
        continue                              # 중복 이름 · 시험 일정과 겹치는 장소 제외
    seen.add(n)
    toks = [t.replace(' ', '') for t in [p['name']] + p['aliases'] if len(t.replace(' ', '')) >= 2]
    p['questions'] = [q for q in p['questions'] if not (q['style'] == 'description' and any(t in q['q'].replace(' ', '') for t in toks))]
    clean.append(p)
print('걸러낸 장소', len(places) - len(clean), '→ 남은 장소', len(clean))
places = clean
# 어미 다양화: 이름·별칭 문장의 끝을 흔한 어미로 바꾼 변형을 더한다(Codex 문장이 「가요?」「ㄱㄱ」에 쏠려 있어서). 시험 문장과 똑같이 쓰지는 않는다.
SUF = ['몇 시야?', '몇 시에 가?', '시간 알려줘', '언제 가?', '예약했어?', '어디야?', '몇시임', '몇시얌?', '가는 거 맞아?', '시간 확인해줘', '일정에 있나요?', '취소할래요', '빼주세요',
       '시간 좀 바꿔줘', '늦춰줄래요', '얼마나 걸려?', '입장 마감 몇 시?', '언제쯤이에요?', '가기로 했었나?', '순서 뭐였지?']
for p in places:
    toks = [p['name']] + p['aliases']
    for _ in range(4):
        p['questions'].append({'q': f"{rnd.choice(toks)} {rnd.choice(SUF)}", 'style': 'aug'})
rnd.shuffle(places)
nval = max(1, len(places) // 5)
val_places, tr_places = places[:nval], places[nval:]
print('장소', len(places), '(학습', len(tr_places), '· 검증', len(val_places), ') · 일정 무관 문장', len(oos))
oos_val = oos[: len(oos) // 5]
oos_tr = oos[len(oos) // 5:]

VERB = {'dining': ['에서 점심', '에서 저녁', '에서 아침', '에서 간식'], 'activity': [' 관람', ' 구경', ' 산책', ' 둘러보기'],
        'lodging': [' 체크인', ' 체크인'], 'mobility': [' 이동', ' 도착']}
HRS = {'dining': ['08:30', '12:00', '12:30', '13:00', '15:30', '18:30', '19:00', '20:00'],
       'activity': ['09:00', '10:00', '11:00', '14:00', '14:30', '16:00', '17:30', '21:00'], 'lodging': ['16:00', '17:00'],
       'mobility': ['09:30', '10:30', '18:00']}


def make_itinerary(pool):
    n = rnd.randint(40, 52)
    chosen = rnd.sample(pool, min(n, len(pool)))
    start = date(2026, 11, 1) + timedelta(days=rnd.randint(0, 20))
    items = []
    for k, p in enumerate(chosen):
        d = start + timedelta(days=k * 7 // len(chosen))
        kind = p['kind']
        title = p['name'] + rnd.choice(VERB[kind])
        items.append({'place': p['name'], 'kind': kind, 'date': d, 'start': rnd.choice(HRS[kind]), 'title': title, 'p': p})
    items.sort(key=lambda i: (i['date'], i['start']))
    tot = {}
    for i in items:
        tot[i['place']] = tot.get(i['place'], 0) + 1
    seen_n = {}
    for k, i in enumerate(items):
        seen_n[i['place']] = seen_n.get(i['place'], 0) + 1
        i['prev'] = items[k - 1]['title'] if k > 0 else None
        i['next'] = items[k + 1]['title'] if k + 1 < len(items) else None
        i['nth'], i['total'] = seen_n[i['place']], tot[i['place']]
    return items


def graph_suffix(prev, nxt, nth, total):
    return (f' — 앞 일정 {prev}' if prev else '') + (f' — 뒤 일정 {nxt}' if nxt else '') + (f' — 같은 장소 {nth}/{total}번째 방문' if total > 1 else '')


def doc(i):
    d = i['date']
    base = f"{d.month}월 {d.day}일({W[d.weekday()]}) {i['start']} {i['title']} — 장소 {i['place']} — 종류 {i['kind']}"
    if not GRAPH:
        return base
    return base + graph_suffix(i['prev'], i['next'], i['nth'], i['total'])


def grams(s):
    s = ''.join(s.split())
    return {s[k:k + 2] for k in range(len(s) - 1)}


def sample_docs(q, items, positives):
    qg = grams(q)
    neg = [i for i in items if i not in positives]
    neg.sort(key=lambda i: -len(qg & grams(i['title'] + i['place'])))
    hard = neg[:6]
    rest = [i for i in neg[6:]]
    rnd.shuffle(rest)
    return positives + hard + rest[:4]


def build(pool, oos_list, n_itin, gid0):
    out = []
    gid = gid0
    for _ in range(n_itin):
        items = make_itinerary(pool)
        inset = {i['place'] for i in items}
        outside = [p for p in pool if p['name'] not in inset]
        for _ in range(100):
            r = rnd.random()
            if r < 0.70:
                it = rnd.choice(items)
                p = it['p']
                q = rnd.choice(p['questions'])['q']
                pos = [i for i in items if i['place'] == it['place']]
            elif r < 0.90 and outside:
                p = rnd.choice(outside)
                q = rnd.choice(p['questions'])['q']
                pos = []
            else:
                q = rnd.choice(oos_list)
                pos = []
            gid += 1
            for i in sample_docs(q, items, pos):
                out.append({'g': gid, 'q': q, 'doc': doc(i), 'label': int(i in pos)})
    return out, gid


train, g = build(tr_places, oos_tr, 60, 0)
val, _ = build(val_places, oos_val, 12, g)
json.dump({'train': train, 'val': val}, open(os.path.join(HERE, 'fixtures', OUTNAME), 'w', encoding='utf-8'), ensure_ascii=False)
print('학습 쌍', len(train), '(정답', sum(x['label'] for x in train), ') · 검증 쌍', len(val), '(정답', sum(x['label'] for x in val), ')')
print('학습 문제', len({x['g'] for x in train}), '· 검증 문제', len({x['g'] for x in val}))
