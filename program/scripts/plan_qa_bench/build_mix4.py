# 판정 전용 새 세트 mix4 — 11유형 × 8문제 = 88문제. 작은 모델 전문가 구조의 코드·프롬프트를 확정(커밋)한 뒤에 한 번만 잰다.
#  일정은 heavy 와 같고(같은 51항목), 문장은 전부 새로 썼다(heavy·ord2·ord3 과 겹치지 않음). 정답은 이름표(key)로 직접 적었다.
#  한계: 같은 사람이 문장·규칙·프롬프트를 썼고 일정도 같다 → 처음 보는 문장이지만 처음 보는 일정은 아니다.
# 사용: python build_mix4.py → fixtures/mix4.json
import json, os
from build_ord2 import ID, heavy, HERE


def H(*turns):
    return [{'role': 'customer' if k % 2 == 0 else 'service', 'text': t} for k, t in enumerate(turns)]


Q = {
    'context_pronoun': [
        ('거기 조식 되나?', 'ci1', H('첫날 숙소 어디야?', 'L7 명동 체크인이 16시예요')),
        ('그 집 웨이팅 심해?', 'myeongdong', H('닷새째 점심 뭐야', '12시 30분 명동교자 칼국수예요')),
        ('카페 쪽 취소할래', 'bottle', H('셋째 날 서촌에서 뭐 해?', '통인시장 구경(14:30), 서촌 카페(16:00) 순서예요')),
        ('그거 한 시간만 뒤로', 'onion_sd', H('성수 어니언 몇 시', '6일차 12시 30분 브런치예요')),
        ('맨 끝에 거 시간 확인해줘', 'airport2', H('마지막 날 일정 알려줘', '체크아웃, 종묘, 쌈지길, 사찰음식 점심, 교보문고, 태극당, 청계천 야경, 우래옥 저녁, 공항 이동 순서예요')),
        ('첫번째 거 몇 시였지', 'craft', H('둘째 날 오후에 뭐 있어', '서울공예박물관(14시), 어니언 안국 카페(15:30), 청계천 걷기(16:30)예요')),
        ('거기 마지막 날에도 가나?', 'urae2', H('우래옥 첫날 몇 시', '첫날 12시 점심이에요')),
        ('저녁 식당은 예약했어?', 'yeonnam', H('홍대 쪽 일정 알려줘', '홍대 이동(18시), 연남동 저녁(19:30), 홍대 버스킹(21시)이에요')),
    ],
    'duplicate_place': [
        ('토요일 우래옥', 'urae1', []), ('금요일 우래옥 시간 알려줘', 'urae2', []), ('광장시장 두번째 방문 몇 시', 'gwang2', []),
        ('첫번째 광장시장 취소해줘', 'gwang1', []), ('화요일 체크인 시간', 'ci2', []), ('수요일 광장시장', 'gwang2', []),
        ('일요일 광장시장', 'gwang1', []), ('한강 공원 가는 저녁 식사', 'yeouido_chimaek', []),
    ],
    'confusable_name': [
        ('창덕궁 후원 시간', 'changdeok', []), ('정동극장 티켓', 'jeongdong', []), ('전쟁기념관 입장 시간', 'war', []),
        ('이문설농탕 몇 시에 가', 'seolleong', []), ('발우공양 예약 시간', 'lunch_insa', []), ('명동교자 시간', 'myeongdong', []),
        ('서울역 도착 몇 시', 'airport', []), ('국립현대미술관은 언제 가?', None, []),
    ],
    'compound_intent': [
        ('경복궁 취소하고 국립민속박물관 시간 알려줘', 'gyeongbok', []), ('북촌 시간 옮기고 삼청동 수제비도 늦춰줘', 'bukchon', []),
        ('종묘 예약하고 쌈지길 몇 시인지도 알려줘', 'jongmyo', []), ('전쟁기념관 몇 시야? 그리고 리움은?', 'war', []),
        ('서울숲 빼고 뚝섬 자전거 한 시간 당겨줘', 'seoulforest', []), ('이문설농탕 취소, 호텔 체크인은 그대로', 'seolleong', []),
        ('청계천 야경 시간 알려주고 우래옥도', 'cheong2', []), ('남대문시장 미루고 서울로7017도 빼줘', 'namdaemun', []),
    ],
    'negation': [
        ('국립중앙박물관 말고 남대문시장 시간', 'namdaemun', []), ('리움 말고 그 다음 일정 시간', 'brunch', []),
        ('우래옥 말고 첫날 저녁 시간', 'chicken', []), ('경복궁 말고 통인시장 취소', 'tongin', []),
        ('토속촌 말고 그 전 일정', 'folk', []), ('창덕궁 말고 셋째 날 첫 일정', 'gyeongbok', []),
        ('광장시장 아침 말고 저녁 거 시간', 'gwang1', []), ('하동관 말고 이문설농탕 시간', 'seolleong', []),
    ],
    'typo_slang': [
        ('종묘 몇시얌', 'jongmyo', []), ('서울숲 몇시임?', 'seoulforest', []), ('교보문고 몇시욤', 'kyobo', []), ('태극당 시간ㅇㅇ', 'taegeuk', []),
        ('청계천 야경 몇싱', 'cheong2', []), ('경복궁 몇시양', 'gyeongbok', []), ('수제비집 취소ㅠㅠ', 'sujebi', []), ('연남동 저녁 몇 시얌', 'yeonnam', []),
    ],
    'out_of_scope': [
        ('내일 비 와?', None, []), ('ㅋㅋㅋㅋㅋ', None, []), ('비트코인 얼마야', None, []), ('자바스크립트 코드 짜줘', None, []),
        ('너 몇 살이야', None, []), ('택시 앱 뭐 써야 돼?', None, []),
        ('감사합니다 수고하세요', None, H('리움 몇 시야', '4일차 10시 30분이에요')), ('환불 규정 알려줘', None, []),
    ],
    'nameless_description': [
        ('궁궐 구경하는 거 첫날', 'deoksu', []), ('냉면집 마지막 날 저녁', 'urae2', []), ('설렁탕 저녁', 'seolleong', []), ('칼국수 점심', 'myeongdong', []),
        ('한옥마을 걷는 거', 'bukchon', []), ('야경 보는 산책', 'cheong2', []), ('수제비 먹는 점심', 'sujebi', []), ('극장 가는 거', 'jeongdong', []),
    ],
    'ordinal_relative': [
        ('목요일 세번째 일정', 'onion_sd', []), ('화요일 첫 일정', 'co1', []), ('이틀째 첫 식사', 'sujebi', []), ('여행 두번째 식사', 'chicken', []),
        ('닷새째 두번째 식사', 'myeongdong', []), ('정동극장 다음에 뭐 먹어?', 'chicken', []), ('종묘 바로 전 일정', 'co2', []), ('일곱째 날 마지막 식사', 'urae2', []),
    ],
    'change_request': [
        ('경복궁 한 시간 늦춰줘', 'gyeongbok', []), ('통인시장 빼줘', 'tongin', []), ('리움 취소할게요', 'leeum', []), ('쌈지길 30분 당겨줘', 'ssamzie', []),
        ('일정 좀 바꿔줘', None, []), ('그 시간 미뤄주세요', None, []),
        ('그거 취소해줘', 'kyobo', H('교보문고 몇 시야', '7일차 14시 30분이에요')), ('삭제해줘', 'natl', H('국립중앙박물관 시간', '5일차 10시예요')),
    ],
    'absent_but_plausible': [
        ('남산 케이블카 몇 시', None, []), ('홍대 클럽 언제 가', None, []), ('강남역 쇼핑 몇 시', None, []), ('올림픽공원 몇 시', None, []),
        ('서울랜드 몇 시야', None, []), ('익선동 한옥거리 언제 가?', None, []), ('이화여대 앞 쇼핑 시간', None, []), ('가로수길 몇 시', None, []),
    ],
}
qs = []
for typ, rows in Q.items():
    assert len(rows) == 8, typ
    for q, k, hist in rows:
        qs.append({'q': q, 'gold': ID[k] if k else None, 'type': typ, 'split': 'held', 'history': hist})
json.dump({'sets': {'mix4': {'today': heavy['today'], 'items': heavy['items'], 'qs': qs}}}, open(os.path.join(HERE, 'fixtures', 'mix4.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('mix4 문제', len(qs), '정답 null', sum(x['gold'] is None for x in qs), '앞 대화', sum(bool(x['history']) for x in qs))
