# 일정 질문 인식 v2 — 모델이 문장을 쓰지 않는다. 규칙으로 좁히고, 여러 면의 임베딩으로 고르고, 신호 없으면 문턱.
import json, math, re, urllib.request, urllib.error
from datetime import date, timedelta

B = 'http://127.0.0.1:11434'


def post(p, b, t=300):
    import time as _t
    for n in range(4):
        try:
            req = urllib.request.Request(B + p, data=json.dumps(b).encode(), headers={'content-type': 'application/json'})
            return json.loads(urllib.request.urlopen(req, timeout=t).read())
        except urllib.error.HTTPError:
            if n == 3:
                raise
            _t.sleep(3)


def norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1
    return [x / n for x in v]


def emb(xs):
    return [norm(v) for v in post('/api/embed', {'model': 'bge-m3', 'input': xs})['embeddings']]


def cos(a, b):
    return sum(x * y for x, y in zip(a, b))


# 분류(카카오 category_name 조각) -> 같은 뜻의 말. 질문을 보지 않고 분류 기준으로 적었다.
LEX = {
    '고궁': '궁궐 고궁 궁 왕궁 palace royal palace 宮殿 王宮 故宫 皇宫', '궁': '궁궐 palace',
    '산': '산 등산 산행 하이킹 트레킹 hiking mountain trail 登山 山 爬山',
    '둘레길': '둘레길 걷기 트레킹 산책 trail walk hiking 散策 徒步', '도보여행': '걷기 도보 walking',
    '테마파크': '놀이공원 놀이동산 놀이기구 테마파크 amusement park theme park rides 遊園地 游乐园',
    '박물관': '박물관 전시 전시회 관람 museum exhibition 博物館 展示 博物馆 展览',
    '공연장,연극극장': '공연 쇼 연극 뮤지컬 극장 show performance theater musical 公演 劇場 演出 剧场',
    '전망대': '전망대 전망 야경 타워 view observatory tower 展望台 塔',
    '시장': '시장 재래시장 장보기 먹거리 market 市場 市场',
    '하천': '개천 하천 물길 산책 stream river walk 川 散歩 溪',
    '도시근린공원': '공원 강변 소풍 산책 park riverside 公園 公园',
    '도서관': '도서관 책 서점 library books 図書館 图书馆', '절,사찰': '절 사찰 템플 temple 寺 お寺 寺庙',
    '호텔': '호텔 숙소 체크인 hotel check-in ホテル 酒店 入住',
    '기차역': '기차 열차 기차역 공항철도 train station railway 駅 電車 火车 车站',
    '음식점': '식당 밥 식사 맛집 restaurant meal food 食事 レストラン 餐厅 吃饭',
    '카페': '카페 커피 디저트 쉬는 곳 cafe coffee カフェ コーヒー 咖啡',
    '국수': '국수 면 noodles 麺 面条', '냉면': '냉면 cold noodles 冷麺 冷面',
    '칼국수': '칼국수 만두 noodles dumplings 麺 面条 饺子', '수제비': '수제비 dough soup すいとん 面片汤',
    '닭요리': '닭 닭고기 chicken 鶏 鸡', '삼계탕': '삼계탕 보양식 ginseng chicken soup 参鶏湯 参鸡汤',
    '샤브샤브': '샤브샤브 전골 shabu hot pot しゃぶしゃぶ 火锅',
    '아시아음식': '중식 아시아 음식 asian chinese アジア料理 亚洲菜',
    '테마거리': '거리 골목 먹자골목 street alley 通り 街', '관광,명소': '관광 명소 구경 sightseeing 観光 景点',
    '문화유적': '유적 역사 historic heritage 史跡 古迹',
}
KINDW = {'dining': '식사', 'activity': '활동', 'lodging': '숙소', 'mobility': '이동'}


def views(it, cat):
    parts = [p.strip() for p in cat.split('>')] if cat else []
    lex = ' '.join(LEX[p] for p in parts if p in LEX)
    return [it['title'], it['place'], (' '.join(parts[1:]) or KINDW[it['kind']]), (lex or KINDW[it['kind']])]


WD = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6}
EN_WD = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
JA_WD = ['月曜', '火曜', '水曜', '木曜', '金曜', '土曜', '日曜']
ZH_WD = ['一', '二', '三', '四', '五', '六', '日']
ORD_KO = {'첫째': 1, '둘째': 2, '셋째': 3, '넷째': 4, '다섯째': 5, '여섯째': 6, '일곱째': 7, '이튿': 2}
ORD_EN = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, '1st': 1, '2nd': 2, '3rd': 3, '4th': 4}
ZH_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7}


def day_of(q, days, today):
    ql = q.lower()

    def nth(k):
        return days[k - 1] if 1 <= k <= len(days) else 'none'

    def weekday(i):
        return next((d for d in days if d.weekday() == i), 'none')

    if m := re.search(r'(\d{1,2})월\s*(\d{1,2})일', q):
        return date(days[0].year, int(m[1]), int(m[2]))
    if m := re.search(r'(?<![\d:])(\d{1,2})/(\d{1,2})(?!\d)', q):
        return date(days[0].year, int(m[1]), int(m[2]))
    if m := re.search(r'(\d)\s*일차', q):
        return nth(int(m[1]))
    if m := re.search(r'day\s*(\d)', ql):
        return nth(int(m[1]))
    if m := re.search(r'(\d)\s*日目', q):
        return nth(int(m[1]))
    if m := re.search(r'第([一二三四五六七\d])天', q):
        return nth(ZH_NUM.get(m[1]) or int(m[1]))
    if '初日' in q or re.search(r'첫\s*날|첫째\s*날', q):
        return days[0]
    for w, k in ORD_KO.items():
        if re.search(w + r'\s*날', q):
            return nth(k)
    for w, k in ORD_EN.items():
        if re.search(r'\b' + w + r'\s+day', ql):
            return nth(k)
    if re.search(r'마지막\s*날|last (day|morning|afternoon|evening|night)|final day|最終日|最后一天|最後の日', ql):
        return days[-1]
    if '모레' in q:
        return today + timedelta(2)
    if '내일' in q or 'tomorrow' in ql or '明日' in q or '明天' in q:
        return today + timedelta(1)
    if '오늘' in q or 'today' in ql or '今日' in q or '今天' in q:
        return today
    for i, w in enumerate(EN_WD):
        if w in ql:
            return weekday(i)
    for i, w in enumerate(JA_WD):
        if w in q:
            return weekday(i)
    if m := re.search(r'(?:星期|周|禮拜|礼拜)([一二三四五六日天])', q):
        return weekday(ZH_WD.index('日' if m[1] == '天' else m[1]))
    if m := re.search(r'([월화수목금토일])(?:요일|욜)', q):
        return weekday(WD[m[1]])
    return None


SLOTS = [(('아침', '오전', 'morning', '朝', '午前', '上午', '早上', '早晨'), 5, 12),
         (('점심', 'lunch', 'ランチ', '昼', '中午', '午饭', '午餐'), 11, 15),
         (('오후', 'afternoon', '午後', '下午'), 12, 18),
         (('저녁', '밤', 'dinner', 'evening', 'night', '夜', '夕', '晚'), 17, 24)]


def slot_of(q):
    ql = q.lower()
    for ws, a, b in SLOTS:
        if any(w in ql for w in ws):
            return (a, b)
    return None


def clock_of(q):
    ql = q.lower()
    if m := re.search(r'(\d{1,2}):(\d{2})', q):
        return int(m[1])
    if m := re.search(r'(\d{1,2})\s*(pm|p\.m)', ql):
        h = int(m[1])
        return h + 12 if h < 12 else h
    if m := re.search(r'(\d{1,2})\s*(am|a\.m)', ql):
        return int(m[1])
    if m := re.search(r'(오후|下午|午後)?\s*(\d{1,2})\s*(?:시(?!간)|時|点|點)', q):
        h = int(m[2])
        return h + 12 if (m[1] or h < 8) and h < 12 else h
    return None


EAT = ('먹', '식당', '밥', '메뉴', '맛집', '식사', 'eat', 'restaurant', 'food', 'lunch', 'dinner', 'breakfast', 'meal',
       '食', 'ご飯', 'ランチ', '吃', '餐', '饭', '飯')
SLEEP = ('호텔', '숙소', '체크인', '체크 인', 'hotel', 'check-in', 'check in', 'ホテル', 'チェックイン', '酒店', '入住', '宾馆')
RIDE = ('기차', '공항철도', '공항', '열차', 'train', 'airport', 'railway', '電車', '空港', '機場', '机场', '火车', '地铁')


def kind_of(q):
    ql = q.lower()
    if any(w in ql for w in SLEEP):
        return 'lodging'
    if any(w in ql for w in RIDE):
        return 'mobility'
    if any(w in ql for w in EAT):
        return 'dining'
    return None


NEXT = r'(다음|직후|후에|뒤에|나서|끝나고|마치고|다녀와서|\bafter\b(?!noon)|\bthen\b|の後|あと|之后|以后)'
PREV = r'(직전|전에|\bbefore\b|の前|之前|以前)'


class Recognizer:
    def __init__(s, items, cats, today):
        s.items = sorted(items, key=lambda i: (i['date'], i['start']))
        s.today = today
        s.days = sorted({date.fromisoformat(i['date']) for i in s.items})
        vs = [views(i, cats.get(i['place'], '')) for i in s.items]
        flat = emb([v for vv in vs for v in vv])
        k = 0
        s.V = {}
        for i, vv in zip(s.items, vs):
            s.V[i['id']] = flat[k:k + len(vv)]
            k += len(vv)

    def score(s, qv, i):
        return max(cos(qv, v) for v in s.V[i['id']])

    def filt(s, q):
        d, sl, c, k = day_of(q, s.days, s.today), slot_of(q), clock_of(q), kind_of(q)
        sig = any(x is not None for x in (d, sl, c, k))
        if d == 'none':
            return [], True
        pool = list(s.items)
        if d is not None:
            pool = [i for i in pool if date.fromisoformat(i['date']) == d]
        if c is not None:
            pool = [i for i in pool if int(i['start'][:2]) == c] or pool
        if sl is not None:
            pool = [i for i in pool if sl[0] <= int(i['start'][:2]) < sl[1]] or pool
        if k is not None:
            pool = [i for i in pool if i['kind'] == k] or pool
        return pool, sig

    def rank(s, q, qv):
        pool, sig = s.filt(q)
        return sorted(((s.score(qv, i), i['id']) for i in pool), reverse=True), sig, pool

    def pick(s, q, qv, tau):
        # 순서 질문: 기준 항목을 찾은 뒤 앞뒤로 한 칸
        for pat, step in ((NEXT, 1), (PREV, -1)):
            m = re.search(pat, q, re.I)
            if m and m.start() > 0:
                anchor_q = q[:m.start()]
                ranked, sig, pool = s.rank(anchor_q, emb([anchor_q])[0])
                if ranked and (sig or ranked[0][0] >= tau):
                    ids = [i['id'] for i in s.items]
                    j = ids.index(ranked[0][1])
                    want = kind_of(q[m.end():])   # 「마치고 들르는 식당」 — 뒤에 종류가 붙으면 그 종류의 다음 항목
                    while 0 <= j + step < len(ids):
                        j += step
                        if want is None or s.items[j]['kind'] == want:
                            return ids[j]
        ranked, sig, pool = s.rank(q, qv)
        if not ranked:
            return None
        if len(pool) == 1 and sig:
            return ranked[0][1]
        return ranked[0][1] if (ranked[0][0] >= tau or sig) else None


# ── v3: 등록할 때 한 번, 항목을 부르는 말을 모델이 만든다(찾기 색인 전용 — 답에는 안 쓴다) + 없는 종류는 없음 ──
import os
ALIAS_S = {'type': 'object', 'properties': {'phrases': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['phrases']}


def aliases(it, cat, cache):
    key = f"{it['title']}|{it['place']}"
    if key in cache:
        return cache[key]
    prompt = (f"여행 일정 항목: {it['title']} (장소: {it['place']}, 분류: {cat or it['kind']}).\n"
              "고객이 채팅에서 이 항목을 이름 없이 또는 줄여서 부를 만한 짧은 표현 12개를 만들어라 — "
              "거기서 하는 일, 장소의 종류, 흔한 별칭·옛 이름·줄임말. 한국어 6개, 영어 3개, 일본어 1개, 중국어 2개. "
              "날짜·시각·가격은 넣지 마라.")
    b = {'model': 'gemma4:12b', 'stream': False, 'think': False, 'format': ALIAS_S, 'options': {'temperature': 0},
         'messages': [{'role': 'user', 'content': prompt}]}
    out = []
    for _ in range(3):
        try:
            out = json.loads(post('/api/chat', b)['message']['content']).get('phrases', [])[:14]
            break
        except json.JSONDecodeError:
            b['options']['seed'] = _ + 1
    cache[key] = out
    return out


class RecognizerV3(Recognizer):
    def __init__(s, items, cats, today, cache_path):
        cache = json.load(open(cache_path, encoding='utf-8')) if os.path.exists(cache_path) else {}
        s.items = sorted(items, key=lambda i: (i['date'], i['start']))
        s.today = today
        s.days = sorted({date.fromisoformat(i['date']) for i in s.items})
        vs = [views(i, cats.get(i['place'], '')) + aliases(i, cats.get(i['place'], ''), cache) for i in s.items]
        json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        flat = emb([v for vv in vs for v in vv])
        k = 0
        s.V = {}
        for i, vv in zip(s.items, vs):
            s.V[i['id']] = flat[k:k + len(vv)]
            k += len(vv)

    def filt(s, q):
        d, sl, c, k = day_of(q, s.days, s.today), slot_of(q), clock_of(q), kind_of(q)
        sig = any(x is not None for x in (d, sl, c, k))
        if d == 'none':
            return [], True
        pool = list(s.items)
        if k in ('lodging', 'mobility') and not any(i['kind'] == k for i in s.items):
            return [], True          # 일정에 없는 종류를 물었다
        if d is not None:
            pool = [i for i in pool if date.fromisoformat(i['date']) == d]
        if c is not None:
            pool = [i for i in pool if int(i['start'][:2]) == c] or pool
        if sl is not None:
            pool = [i for i in pool if sl[0] <= int(i['start'][:2]) < sl[1]] or pool
        if k is not None:
            pool = [i for i in pool if i['kind'] == k] or pool
        return pool, sig


# ── v4: v3 + 관광공사 소개글(문장 조각으로 나눠 색인에만 쓴다 — 답에는 안 쓴다) ──
def overview_views(text, size=160):
    sents = [x.strip() for x in re.split(r'(?<=[.다!?])\s+', text or '') if x.strip()]
    out, cur = [], ''
    for x in sents:
        if len(cur) + len(x) > size and cur:
            out.append(cur)
            cur = ''
        cur = (cur + ' ' + x).strip()
    if cur:
        out.append(cur)
    return out[:5]


class RecognizerV4(RecognizerV3):
    def __init__(s, items, cats, today, cache_path, overviews):
        cache = json.load(open(cache_path, encoding='utf-8')) if os.path.exists(cache_path) else {}
        s.items = sorted(items, key=lambda i: (i['date'], i['start']))
        s.today = today
        s.days = sorted({date.fromisoformat(i['date']) for i in s.items})
        vs = [views(i, cats.get(i['place'], '')) + aliases(i, cats.get(i['place'], ''), cache)
              + overview_views((overviews.get(i['place']) or {}).get('overview', '')) for i in s.items]
        json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        flat = emb([v for vv in vs for v in vv])
        k = 0
        s.V = {}
        for i, vv in zip(s.items, vs):
            s.V[i['id']] = flat[k:k + len(vv)]
            k += len(vv)
