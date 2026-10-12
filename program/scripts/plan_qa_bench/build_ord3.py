# 「순서·상대 위치」 판정용 세트 ord3 — ord2 오류를 보기 전에 만든 것이 아니라, ord2 는 이제 개발용으로 쓰고 ord3 는 규칙·자리표 방식을 고친 뒤에도 보지 않은 채 남겨 둔다.
#  일정은 heavy 와 같고 문장은 새로 썼다. 정답은 이름표(key)로 직접 적었다. 정답 null 4개(일정 밖).
# 사용: python build_ord3.py → fixtures/ord3.json
import json, os
from build_ord2 import ID, heavy, HERE

Q = [
    ('화요일 마지막 활동', 'war'), ('목요일 첫 일정', 'to_seongsu'), ('월요일 세번째 일정', 'tosok'), ('토요일 두번째 일정', 'urae1'),
    ('일요일 마지막 일정', 'gwang1'), ('금요일 첫 식사', 'lunch_insa'), ('수요일 두번째 식사', 'myeongdong'), ('이틀째 마지막 활동', 'cheong1'),
    ('사흘째 첫 식사', 'tosok'), ('닷새째 마지막 일정', 'yeouido_chimaek'), ('엿새째 첫 활동', 'seongsu_walk'), ('나흘째 저녁', 'seolleong'),
    ('셋째 날 점심', 'tosok'), ('마지막 날 점심', 'lunch_insa'), ('첫날 저녁', 'chicken'), ('다섯째 날 아침', 'gwang2'),
    ('통인시장 끝나고 뭐 해?', 'bottle'), ('전쟁기념관 다음에', 'ci2'), ('서울로7017 가기 전 일정', 'namdaemun'), ('이문설농탕 바로 전', 'ci2'),
    ('한강 피크닉 끝나고 바로', 'yeouido_chimaek'), ('성수동 카페거리 다음 일정', 'onion_sd'), ('서울숲 앞 일정', 'onion_sd'), ('홍대 이동 바로 뒤에 뭐 있어?', 'yeonnam'),
    ('공예박물관 다음 뭐야', 'onion_an'), ('국립민속박물관 끝나면 바로 뭐 먹어?', 'tosok'), ('광장시장 마약김밥 다음 일정', 'natl'), ('리움 가기 바로 전', 'to_itaewon'),
    ('이태원 브런치 바로 전 일정', 'leeum'), ('여행 첫 활동', 'deoksu'), ('여행 마지막 활동', 'cheong2'), ('첫 체크인 바로 전 일정', 'deoksu'),
    ('둘째 체크인 다음 일정', 'seolleong'), ('마지막 체크아웃 다음', 'jongmyo'), ('일곱째 날 여섯번째 일정', 'taegeuk'), ('다섯째 날 세번째 식사', 'yeouido_chimaek'),
    ('넷째 날 네번째 일정', 'brunch'), ('여섯째 날 세번째 활동', 'ttukseom'),
    ('아홉째 날 첫 일정', None), ('첫날 여덟번째 일정', None), ('마지막 날 마지막 일정 다음', None), ('넷째 날 세번째 식사', None),
]
qs = [{'q': q, 'gold': ID[k] if k else None, 'type': 'ordinal_relative', 'split': 'held', 'history': []} for q, k in Q]
json.dump({'sets': {'ord3': {'today': heavy['today'], 'items': heavy['items'], 'qs': qs}}}, open(os.path.join(HERE, 'fixtures', 'ord3.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('ord3 문제', len(qs), '정답 null', sum(x['gold'] is None for x in qs))
