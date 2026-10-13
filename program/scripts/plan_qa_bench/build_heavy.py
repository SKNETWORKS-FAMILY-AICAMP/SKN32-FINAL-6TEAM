# 무거운 시험 세트 만들기 — Claude 가 직접 쓴 7일·51항목 일정 + 유형 11개 × 12문제 = 132문제.
#  - 항목·정답은 이름표(key)로 적고 번호(id)로 바꾼다(번호 실수 방지). 번호는 날짜·시각 순.
#  - 유형마다 앞 4개는 dev(개발용), 뒤 8개는 held(판정용). 문제를 만든 쪽과 푸는 쪽이 달라야 하므로 Codex 는 출제에 쓰지 않았다.
#  - pool: 날짜·시간대·시각·종류 규칙(recog_v2.filt)으로 좁힌 후보 id (규칙이 신호를 못 읽으면 전체) — 「후보 줄이기」 시험용.
# 사용: python build_heavy.py   → fixtures/heavy.json ({"sets": {"heavy": {...}}}, job.json 과 같은 모양 + history·pool)
import json, os
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = '2026-10-09'
D = ['2026-10-10', '2026-10-11', '2026-10-12', '2026-10-13', '2026-10-14', '2026-10-15', '2026-10-16']
# (key, 날짜 인덱스, 시각, 종류, 제목, 장소)
RAW = [
    ('airport', 0, '10:30', 'mobility', '공항철도 타고 서울역 도착', '서울역'),
    ('urae1', 0, '12:00', 'dining', '우래옥에서 점심', '우래옥'),
    ('deoksu', 0, '14:00', 'activity', '덕수궁 둘러보기', '덕수궁'),
    ('ci1', 0, '16:00', 'lodging', '호텔 체크인', 'L7 명동'),
    ('jeongdong', 0, '18:00', 'activity', '정동극장 공연', '국립정동극장'),
    ('chicken', 0, '20:00', 'dining', '닭한마리 저녁', '진옥화할매원조닭한마리'),
    ('changdeok', 1, '09:00', 'activity', '창덕궁 후원 관람', '창덕궁'),
    ('bukchon', 1, '11:00', 'activity', '북촌 골목 산책', '북촌한옥마을'),
    ('sujebi', 1, '12:30', 'dining', '삼청동 수제비 점심', '삼청동수제비'),
    ('craft', 1, '14:00', 'activity', '공예 전시 보기', '서울공예박물관'),
    ('onion_an', 1, '15:30', 'dining', '카페에서 쉬기', '어니언 안국'),
    ('cheong1', 1, '16:30', 'activity', '청계천 따라 걷기', '청계천'),
    ('gwang1', 1, '18:30', 'dining', '광장시장 빈대떡 저녁', '광장시장'),
    ('gyeongbok', 2, '09:30', 'activity', '경복궁 관람', '경복궁'),
    ('folk', 2, '11:30', 'activity', '국립민속박물관 관람', '국립민속박물관'),
    ('tosok', 2, '13:00', 'dining', '삼계탕 점심', '토속촌삼계탕'),
    ('tongin', 2, '14:30', 'activity', '통인시장 구경', '통인시장'),
    ('bottle', 2, '16:00', 'dining', '서촌 카페', '블루보틀 삼청'),
    ('gwanghwa', 2, '17:30', 'activity', '광화문광장 산책', '광화문광장'),
    ('hadongwan', 2, '19:00', 'dining', '곰탕 저녁', '하동관'),
    ('co1', 3, '09:00', 'lodging', '호텔 체크아웃', 'L7 명동'),
    ('to_itaewon', 3, '09:40', 'mobility', '지하철로 이태원 이동', '이태원역'),
    ('leeum', 3, '10:30', 'activity', '리움미술관 관람', '리움미술관'),
    ('brunch', 3, '12:30', 'dining', '이태원 브런치 점심', '에그슬럿 이태원'),
    ('war', 3, '14:30', 'activity', '전쟁기념관 관람', '전쟁기념관'),
    ('ci2', 3, '17:00', 'lodging', '호텔 체크인', '스테이 서촌'),
    ('seolleong', 3, '19:00', 'dining', '설렁탕 저녁', '이문설농탕'),
    ('gwang2', 4, '08:30', 'dining', '광장시장 마약김밥 아침', '광장시장'),
    ('natl', 4, '10:00', 'activity', '국립중앙박물관 관람', '국립중앙박물관'),
    ('myeongdong', 4, '12:30', 'dining', '명동교자 칼국수 점심', '명동교자'),
    ('namdaemun', 4, '14:00', 'activity', '남대문시장 구경', '남대문시장'),
    ('seoullo', 4, '16:00', 'activity', '서울로7017 산책', '서울로7017'),
    ('yeouido_pic', 4, '18:30', 'activity', '한강 피크닉', '여의도 한강공원'),
    ('yeouido_chimaek', 4, '20:00', 'dining', '한강에서 치맥 저녁', '여의도 한강공원'),
    ('to_seongsu', 5, '09:30', 'mobility', '지하철로 성수동 이동', '성수역'),
    ('seongsu_walk', 5, '10:30', 'activity', '성수동 카페거리 산책', '성수동 카페거리'),
    ('onion_sd', 5, '12:30', 'dining', '브런치 점심', '어니언 성수'),
    ('seoulforest', 5, '14:30', 'activity', '서울숲 산책', '서울숲'),
    ('ttukseom', 5, '16:30', 'activity', '한강 자전거 타기', '뚝섬 한강공원'),
    ('to_hongdae', 5, '18:00', 'mobility', '지하철로 홍대 이동', '홍대입구역'),
    ('yeonnam', 5, '19:30', 'dining', '연남동 저녁', '연남동'),
    ('busking', 5, '21:00', 'activity', '홍대 버스킹 구경', '홍대 걷고싶은거리'),
    ('co2', 6, '09:00', 'lodging', '호텔 체크아웃', '스테이 서촌'),
    ('jongmyo', 6, '10:00', 'activity', '종묘 관람', '종묘'),
    ('ssamzie', 6, '11:30', 'activity', '인사동 쌈지길 기념품 쇼핑', '인사동 쌈지길'),
    ('lunch_insa', 6, '13:00', 'dining', '사찰음식 점심', '발우공양'),
    ('kyobo', 6, '14:30', 'activity', '교보문고 광화문점 책 구경', '교보문고 광화문점'),
    ('taegeuk', 6, '16:00', 'dining', '태극당에서 간식', '태극당'),
    ('cheong2', 6, '17:30', 'activity', '청계천 야경 산책', '청계천'),
    ('urae2', 6, '19:00', 'dining', '우래옥 마지막 저녁', '우래옥'),
    ('airport2', 6, '21:00', 'mobility', '공항철도 타고 인천공항 이동', '서울역'),
]
RAW.sort(key=lambda r: (r[1], r[2]))
ID = {r[0]: n + 1 for n, r in enumerate(RAW)}
items = [{'id': ID[r[0]], 'date': D[r[1]], 'start': r[2], 'kind': r[3], 'title': r[4], 'place': r[5]} for r in RAW]


def H(*turns):
    return [{'role': 'customer' if k % 2 == 0 else 'service', 'text': t} for k, t in enumerate(turns)]


# 유형: [(문장, 정답 key 또는 None, history)] — 앞 4개 dev, 뒤 8개 held
Q = {
    'context_pronoun': [
        ('거기 카페 몇 시?', 'onion_an', H('둘째 날 뭐 있어?', '창덕궁 후원, 북촌 산책, 삼청동 수제비 점심, 서울공예박물관, 어니언 안국 카페, 청계천 산책, 광장시장 저녁이에요')),
        ('그 식당 취소해줘', 'chicken', H('첫날 저녁 뭐야', '첫날 저녁은 20시에 진옥화할매원조닭한마리예요')),
        ('그거 한 시간 당겨줘', 'airport2', H('마지막 날 마지막 일정 뭐야', '21시에 공항철도로 인천공항 이동이에요')),
        ('방금 바꾼 거 원래대로', 'jongmyo', H('종묘 시간 바꿔줘 11시로', '종묘 관람을 11시로 바꿨어요')),
        ('거기 예약돼 있어?', 'tosok', H('셋째 날 점심 어디야', '13시 토속촌삼계탕이에요')),
        ('그 미술관 입장료는?', 'leeum', H('4일차 미술관 뭐지', '10시 30분 리움미술관 관람이에요')),
        ('마지막 거 취소', 'ttukseom', H('성수동 일정 알려줘', '성수동 카페거리 산책, 어니언 성수 브런치, 서울숲 산책, 뚝섬 한강공원 자전거 순서예요')),
        ('뒤에 거 삭제해줘', 'yeouido_chimaek', H('여의도 한강공원 일정 뭐 있어?', '피크닉(18:30)과 한강 치맥 저녁(20:00) 두 개예요')),
        ('그 호텔 짐 맡길 수 있나?', 'co1', H('체크아웃 언제야', '4일차 9시 L7 명동 체크아웃이에요')),
        ('마지막 날 걸로 예약해줘', 'urae2', H('우래옥 몇 번 가?', '첫날 점심 12시, 마지막 날 저녁 19시 두 번이에요')),
        ('아침 거 시간 미뤄줘', 'gwang2', H('광장시장 언제 가', '2일차 저녁 18:30과 5일차 아침 8:30이에요')),
        ('앞에 거는 비 오면 빼줘', 'cheong1', H('청계천 일정 알려줘', '2일차 16:30 청계천 걷기, 7일차 17:30 청계천 야경 산책이에요')),
    ],
    'duplicate_place': [
        ('광장시장 아침 몇 시?', 'gwang2', []),
        ('저녁 광장시장 예약했어?', 'gwang1', []),
        ('첫날 우래옥 몇 시야', 'urae1', []),
        ('마지막 날 우래옥 시간 바꿔줘', 'urae2', []),
        ('두번째 호텔 어디야', 'ci2', []),
        ('처음 체크인 시간이 뭐지?', 'ci1', []),
        ('일요일 청계천 몇 시야', 'cheong1', []),
        ('야경 청계천 취소', 'cheong2', []),
        ('일요일 어니언 몇 시', 'onion_an', []),
        ('목요일 어니언 예약함?', 'onion_sd', []),
        ('한강에서 먹는 저녁은 몇 시?', 'yeouido_chimaek', []),
        ('한강 피크닉 시간 알려줘', 'yeouido_pic', []),
    ],
    'confusable_name': [
        ('창덕궁 몇 시에 가?', 'changdeok', []),
        ('덕수궁 입장 시간', 'deoksu', []),
        ('경복궁 관람 몇 시야', 'gyeongbok', []),
        ('창덕궁 말고 덕수궁 시간', 'deoksu', []),
        ('국립민속박물관 몇 시', 'folk', []),
        ('국립중앙박물관 시간', 'natl', []),
        ('공예박물관 몇시', 'craft', []),
        ('통인시장 언제 가', 'tongin', []),
        ('남대문시장 시간', 'namdaemun', []),
        ('뚝섬 한강공원 몇 시', 'ttukseom', []),
        ('스테이 서촌 체크인 몇 시', 'ci2', []),
        ('경희궁은 언제 가?', None, []),
    ],
    'compound_intent': [
        ('덕수궁 취소하고 체크인 몇 시야?', 'deoksu', []),
        ('창덕궁 시간 알려주고 북촌 빼줘', 'changdeok', []),
        ('리움 시간 옮기고 전쟁기념관 취소해줘', 'leeum', []),
        ('종묘 몇 시야? 그리고 쌈지길도', 'jongmyo', []),
        ('토속촌 예약하고 통인시장 몇 시인지도', 'tosok', []),
        ('서울숲 취소하고 뚝섬 자전거도 빼줘', 'seoulforest', []),
        ('명동교자 시간 당기고 남대문시장 늦춰줘', 'myeongdong', []),
        ('정동극장 몇 시야 그리고 티켓도 알려줘', 'jeongdong', []),
        ('서울로7017 빼고 한강 피크닉 앞당겨줘', 'seoullo', []),
        ('하동관 취소하고 광화문광장 시간 알려줘', 'hadongwan', []),
        ('인사동 점심 취소, 쌈지길은 그대로', 'lunch_insa', []),
        ('태극당 시간 알려주고 교보문고도', 'taegeuk', []),
    ],
    'negation': [
        ('경복궁 말고 바로 다음 거 시간 알려줘', 'folk', []),
        ('첫날 저녁 말고 점심 몇 시', 'urae1', []),
        ('둘째 날 창덕궁 말고 북촌 몇 시?', 'bukchon', []),
        ('덕수궁 말고 정동극장 취소', 'jeongdong', []),
        ('닭한마리 말고 첫날 점심 시간', 'urae1', []),
        ('성수동 카페거리 말고 서울숲 시간', 'seoulforest', []),
        ('이태원 브런치 말고 그 전에 리움 시간', 'leeum', []),
        ('광장시장 저녁 말고 아침 거 취소', 'gwang2', []),
        ('하동관 말고 셋째 날 낮 식당 시간', 'tosok', []),
        ('종묘 말고 그 다음 일정 뭐야', 'ssamzie', []),
        ('명동교자 말고 이문설농탕 시간', 'seolleong', []),
        ('홍대 버스킹 말고 연남동 시간', 'yeonnam', []),
    ],
    'typo_slang': [
        ('덕수궁 몇시임', 'deoksu', []),
        ('창덕궁 후웡 몇시야', 'changdeok', []),
        ('닭한마리 취소ㅠ', 'chicken', []),
        ('삼청동 수제비 몇시얌', 'sujebi', []),
        ('광장시장 빈대떡 시간ㅇㅇ', 'gwang1', []),
        ('경복공 몇시야', 'gyeongbok', []),
        ('북초 몇시?', 'bukchon', []),
        ('리움미술관 몇시양', 'leeum', []),
        ('전쟁기렴관 시간', 'war', []),
        ('성수 카페거리 몇시욤', 'seongsu_walk', []),
        ('종묘 시간임?', 'jongmyo', []),
        ('우래옥 첫날 몇시얌', 'urae1', []),
    ],
    'out_of_scope': [
        ('오늘 서울 날씨 어때?', None, []),
        ('파이썬으로 코드 짜줘', None, []),
        ('엔비디아 주가 얼마야', None, []),
        ('고마워 ㅎㅎ', None, H('덕수궁 몇시야', '첫날 14시예요')),
        ('너 이름이 뭐야', None, []),
        ('환율 알려줘', None, []),
        ('김치찌개 레시피 알려줘', None, []),
        ('서울 지하철 요금 얼마야', None, []),
        ('한국어로 안녕 어떻게 말해', None, []),
        ('근데 너 AI야?', None, H('창덕궁 몇 시야', '2일차 9시예요')),
        ('비행기 티켓 얼마야?', None, []),
        ('오늘 뭐 먹지 추천해줘', None, []),
    ],
    'nameless_description': [
        ('궁궐 후원 걷는 거', 'changdeok', []),
        ('닭 통째로 끓여 먹는 저녁', 'chicken', []),
        ('곰탕 먹는 집', 'hadongwan', []),
        ('삼계탕 먹는 식당', 'tosok', []),
        ('공연 보는 거', 'jeongdong', []),
        ('전쟁 역사 보는 곳', 'war', []),
        ('대형 미술관 가는 거', 'leeum', []),
        ('빵집에서 간식 먹는 거', 'taegeuk', []),
        ('책방 구경하는 일정', 'kyobo', []),
        ('시장에서 김밥 먹는 아침', 'gwang2', []),
        ('고가도로 공원 산책', 'seoullo', []),
        ('한강에서 자전거 타는 거', 'ttukseom', []),
    ],
    'ordinal_relative': [
        ('셋째 날 첫 일정', 'gyeongbok', []),
        ('첫날 마지막 일정', 'chicken', []),
        ('첫 체크인 다음 일정', 'jeongdong', []),
        ('넷째 날 점심 다음 일정', 'war', []),
        ('마지막 날 체크아웃 바로 다음 일정', 'jongmyo', []),
        ('다섯째 날 저녁 식사', 'yeouido_chimaek', []),
        ('둘째 날 마지막 일정', 'gwang1', []),
        ('여섯째 날 점심', 'onion_sd', []),
        ('이틀째 첫 일정', 'changdeok', []),
        ('청계천 걷고 나서 바로 뭐 먹어?', 'gwang1', []),
        ('삼청동 점심 바로 전 일정', 'bukchon', []),
        ('닷새째 아침', 'gwang2', []),
    ],
    'change_request': [
        ('덕수궁 30분 미뤄줘', 'deoksu', []),
        ('정동극장 취소해줘', 'jeongdong', []),
        ('북촌 산책 빼줘', 'bukchon', []),
        ('리움 한 시간 당겨줘', 'leeum', []),
        ('이거 취소해줘', None, []),
        ('시간 좀 미뤄줘', None, []),
        ('서울숲 취소', 'seoulforest', []),
        ('종묘 11시로 바꿔줘', 'jongmyo', []),
        ('홍대 버스킹 없애줘', 'busking', []),
        ('그거 한 시간 뒤로', 'namdaemun', H('남대문시장 몇 시야', '5일차 14시예요')),
        ('취소해줘', 'war', H('전쟁기념관 몇시', '4일차 14시 30분이에요')),
        ('저녁 취소해줘', None, []),
    ],
    'absent_but_plausible': [
        ('롯데월드타워 몇 시', None, []),
        ('남산타워 예약했지?', None, []),
        ('창경궁 시간 알려줘', None, []),
        ('명동성당 언제 가?', None, []),
        ('동대문디자인플라자 몇시', None, []),
        ('코엑스 별마당도서관 가?', None, []),
        ('잠실 롯데월드 어드벤처 언제야', None, []),
        ('한강 유람선 몇 시야', None, []),
        ('동묘 벼룩시장 몇 시', None, []),
        ('강남 교보문고는 몇 시?', None, []),
        ('롯데백화점 본점 시간', None, []),
        ('서울역사박물관 몇 시야', None, []),
    ],
}

qs = []
for typ, rows in Q.items():
    assert len(rows) == 12, typ
    for k, (q, gk, hist) in enumerate(rows):
        qs.append({'q': q, 'gold': ID[gk] if gk else None, 'type': typ, 'split': 'dev' if k < 4 else 'held', 'history': hist})

# 규칙으로 후보 좁히기(오프라인, 올라마 불필요)
import sys
sys.path.insert(0, HERE)
from recog_v2 import RecognizerV3  # noqa: E402


class RuleOnly(RecognizerV3):
    def __init__(self, its, today):
        self.items = sorted(its, key=lambda i: (i['date'], i['start']))
        self.today = today
        self.days = sorted({date.fromisoformat(i['date']) for i in self.items})


rec = RuleOnly(items, date.fromisoformat(TODAY))
lost = 0
for x in qs:
    pool, sig = rec.filt(x['q'])
    x['pool'] = sorted(i['id'] for i in pool) if (sig and pool) else [i['id'] for i in items]
    if x['gold'] is not None and x['gold'] not in x['pool']:
        lost += 1
        x['pool_lost_gold'] = True
job = {'sets': {'heavy': {'today': TODAY, 'items': items, 'qs': qs}}}
os.makedirs(os.path.join(HERE, 'fixtures'), exist_ok=True)
json.dump(job, open(os.path.join(HERE, 'fixtures', 'heavy.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('항목', len(items), '문제', len(qs), '유형', dict(Counter(x['type'] for x in qs)), '분할', dict(Counter(x['split'] for x in qs)))
print('정답 null', sum(x['gold'] is None for x in qs), '· 앞 대화 있는 문제', sum(bool(x['history']) for x in qs),
      '· 규칙이 정답을 후보에서 잃은 문제', lost, '· 평균 후보 수', round(sum(len(x['pool']) for x in qs) / len(qs), 1))
