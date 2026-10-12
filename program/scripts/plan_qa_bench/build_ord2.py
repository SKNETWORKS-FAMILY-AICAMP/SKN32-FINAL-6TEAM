# 「순서·상대 위치」 처음 보는 문제 48개(ord2) — heavy 세트 일정을 그대로 쓰고 문장은 새로 썼다. 정답은 이름표(key)로 직접 적었다.
#  용도: 「문장에서 날·순서·종류·기준 항목을 뽑고 코드가 일정 관계를 따라가는」 방식과 모델이 바로 짚는 방식을 비교한다.
#  판정 전용(모델·코드를 이 문제에 맞춰 고치지 않는다). 일정 밖(여덟째 날·일곱번째·마지막 다음)은 정답 null.
# 사용: python build_ord2.py → fixtures/ord2.json
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
heavy = json.load(open(os.path.join(HERE, 'fixtures', 'heavy.json'), encoding='utf-8'))['sets']['heavy']
# heavy 의 항목 이름표는 build_heavy.py 의 RAW 순서와 같다 — 이름표 → id 는 제목·장소로 찾는다
T = {(i['title'], i['place']): i['id'] for i in heavy['items']}
K = {  # 이름표: (제목, 장소)
    'airport': ('공항철도 타고 서울역 도착', '서울역'), 'urae1': ('우래옥에서 점심', '우래옥'), 'deoksu': ('덕수궁 둘러보기', '덕수궁'),
    'ci1': ('호텔 체크인', 'L7 명동'), 'jeongdong': ('정동극장 공연', '국립정동극장'), 'chicken': ('닭한마리 저녁', '진옥화할매원조닭한마리'),
    'changdeok': ('창덕궁 후원 관람', '창덕궁'), 'bukchon': ('북촌 골목 산책', '북촌한옥마을'), 'sujebi': ('삼청동 수제비 점심', '삼청동수제비'),
    'craft': ('공예 전시 보기', '서울공예박물관'), 'onion_an': ('카페에서 쉬기', '어니언 안국'), 'cheong1': ('청계천 따라 걷기', '청계천'),
    'gwang1': ('광장시장 빈대떡 저녁', '광장시장'), 'gyeongbok': ('경복궁 관람', '경복궁'), 'folk': ('국립민속박물관 관람', '국립민속박물관'),
    'tosok': ('삼계탕 점심', '토속촌삼계탕'), 'tongin': ('통인시장 구경', '통인시장'), 'bottle': ('서촌 카페', '블루보틀 삼청'),
    'gwanghwa': ('광화문광장 산책', '광화문광장'), 'hadongwan': ('곰탕 저녁', '하동관'), 'co1': ('호텔 체크아웃', 'L7 명동'),
    'to_itaewon': ('지하철로 이태원 이동', '이태원역'), 'leeum': ('리움미술관 관람', '리움미술관'), 'brunch': ('이태원 브런치 점심', '에그슬럿 이태원'),
    'war': ('전쟁기념관 관람', '전쟁기념관'), 'ci2': ('호텔 체크인', '스테이 서촌'), 'seolleong': ('설렁탕 저녁', '이문설농탕'),
    'gwang2': ('광장시장 마약김밥 아침', '광장시장'), 'natl': ('국립중앙박물관 관람', '국립중앙박물관'), 'myeongdong': ('명동교자 칼국수 점심', '명동교자'),
    'namdaemun': ('남대문시장 구경', '남대문시장'), 'seoullo': ('서울로7017 산책', '서울로7017'), 'yeouido_pic': ('한강 피크닉', '여의도 한강공원'),
    'yeouido_chimaek': ('한강에서 치맥 저녁', '여의도 한강공원'), 'to_seongsu': ('지하철로 성수동 이동', '성수역'),
    'seongsu_walk': ('성수동 카페거리 산책', '성수동 카페거리'), 'onion_sd': ('브런치 점심', '어니언 성수'), 'seoulforest': ('서울숲 산책', '서울숲'),
    'ttukseom': ('한강 자전거 타기', '뚝섬 한강공원'), 'to_hongdae': ('지하철로 홍대 이동', '홍대입구역'), 'yeonnam': ('연남동 저녁', '연남동'),
    'busking': ('홍대 버스킹 구경', '홍대 걷고싶은거리'), 'co2': ('호텔 체크아웃', '스테이 서촌'), 'jongmyo': ('종묘 관람', '종묘'),
    'ssamzie': ('인사동 쌈지길 기념품 쇼핑', '인사동 쌈지길'), 'lunch_insa': ('사찰음식 점심', '발우공양'), 'kyobo': ('교보문고 광화문점 책 구경', '교보문고 광화문점'),
    'taegeuk': ('태극당에서 간식', '태극당'), 'cheong2': ('청계천 야경 산책', '청계천'), 'urae2': ('우래옥 마지막 저녁', '우래옥'),
    'airport2': ('공항철도 타고 인천공항 이동', '서울역'),
}
ID = {k: T[v] for k, v in K.items()}
Q = [  # (문장, 정답 key 또는 None)
    ('월요일 첫 일정', 'gyeongbok'), ('수요일 마지막 일정', 'yeouido_chimaek'), ('화요일 두번째 일정', 'to_itaewon'), ('금요일 세번째', 'ssamzie'),
    ('토요일 마지막 식사', 'chicken'), ('일요일 첫 식사', 'sujebi'), ('목요일 마지막 활동', 'busking'), ('셋째 날 두번째 활동', 'folk'),
    ('넷째 날 마지막 식사', 'seolleong'), ('다섯째 날 첫 식사', 'gwang2'), ('여섯째 날 두번째 이동', 'to_hongdae'), ('둘째 날 카페', 'onion_an'),
    ('덕수궁 바로 다음', 'ci1'), ('정동극장 바로 전 일정', 'ci1'), ('리움 끝나고 바로 뭐 먹어?', 'brunch'), ('이태원 브런치 다음 일정', 'war'),
    ('북촌 산책 다음', 'sujebi'), ('서울공예박물관 가기 전 일정', 'sujebi'), ('종묘 다음 순서', 'ssamzie'), ('교보문고 바로 앞 일정', 'lunch_insa'),
    ('우래옥 마지막 저녁 뒤에 뭐 있어?', 'airport2'), ('닭한마리 다음날 첫 일정', 'changdeok'), ('연남동 저녁 다음 일정', 'busking'), ('한강 치맥 전에 뭐 해?', 'yeouido_pic'),
    ('마지막 날 첫 일정', 'co2'), ('마지막 날 마지막 일정', 'airport2'), ('첫날 첫 일정', 'airport'), ('여행 첫 식사', 'urae1'),
    ('여행 마지막 식사', 'urae2'), ('첫 체크아웃 바로 다음', 'to_itaewon'), ('둘째 날 점심 다음 일정', 'craft'), ('셋째 날 점심 전 일정', 'folk'),
    ('여섯째 날 브런치 다음 일정', 'seoulforest'), ('일곱째 날 점심 바로 뒤', 'kyobo'), ('다섯째 날 남대문시장 다음', 'seoullo'), ('나흘째 마지막 일정', 'seolleong'),
    ('이틀째 세번째', 'sujebi'), ('사흘째 마지막 식사', 'hadongwan'), ('닷새째 두번째 활동', 'namdaemun'), ('엿새째 마지막 식사', 'yeonnam'),
    ('이레째 두번째 식사', 'taegeuk'), ('둘째날 저녁 바로 전', 'cheong1'), ('셋째 날 서촌 카페 다음 일정', 'gwanghwa'), ('첫날 점심 바로 전', 'airport'),
    ('여덟째 날 첫 일정', None), ('첫날 일곱번째 일정', None), ('공항철도 인천공항 이동 다음 일정', None), ('서울역 도착 바로 전 일정', None),
]
assert len(Q) == 48
qs = [{'q': q, 'gold': ID[k] if k else None, 'type': 'ordinal_relative', 'split': 'held', 'history': []} for q, k in Q]
json.dump({'sets': {'ord2': {'today': heavy['today'], 'items': heavy['items'], 'qs': qs}}}, open(os.path.join(HERE, 'fixtures', 'ord2.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('ord2 문제', len(qs), '정답 null', sum(x['gold'] is None for x in qs))
