# 처음 보는 독립 세트 mix5 — **다른 일정**(6일 · 성인 2명 · 38항목, heavy·mix4 의 51항목과 장소가 겹치지 않음) + 문장 11유형 × 8 = 88문제.
#  작은 모델 전문가 구조의 코드·프롬프트·문턱을 확정한 뒤 한 번만 재기 위한 세트. 정답은 이름표(key)로 직접 적었다.
#  한계: 같은 사람(Claude)이 일정·문장·규칙을 모두 썼다. 학습 자료(Codex 작성 장소 150곳)와 겹치는 장소가 있는지는 빌드 때 출력한다.
# 사용: python build_mix5.py → fixtures/mix5.json
import glob, json, os
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = '2026-10-30'
D = ['2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06', '2026-11-07']
RAW = [  # (key, 일차 0~5, 시각, 종류, 제목, 장소)
    ('gimpo', 0, '10:10', 'mobility', '김포공항역에서 지하철 이동', '김포공항역'),
    ('sila_ci', 0, '11:30', 'lodging', '호텔 체크인', '신라스테이 광화문'),
    ('mijin', 0, '12:30', 'dining', '미진에서 메밀국수 점심', '미진'),
    ('cheongwadae', 0, '14:30', 'activity', '청와대 관람', '청와대'),
    ('gogung', 0, '16:30', 'activity', '국립고궁박물관 관람', '국립고궁박물관'),
    ('gwanghwamunjip', 0, '18:30', 'dining', '광화문집 저녁', '광화문집'),
    ('hangeul', 1, '09:30', 'activity', '국립한글박물관 관람', '국립한글박물관'),
    ('euljimyeon', 1, '12:00', 'dining', '을지면옥 냉면 점심', '을지면옥'),
    ('ntheater', 1, '14:00', 'activity', '국립극장 공연', '국립극장'),
    ('terarosa', 1, '16:00', 'dining', '남산 카페', '테라로사 포스코센터점'),
    ('maro1', 1, '18:00', 'activity', '마로니에공원 산책', '마로니에공원'),
    ('gopchang', 1, '19:30', 'dining', '대학로 곱창 저녁', '대학로 곱창골목'),
    ('hapjeong', 2, '09:30', 'mobility', '지하철로 합정역 이동', '합정역'),
    ('jeoldusan', 2, '10:30', 'activity', '절두산 순교성지 산책', '절두산순교성지'),
    ('jinju', 2, '12:30', 'dining', '진주집 콩국수 점심', '진주집'),
    ('sangsang', 2, '14:30', 'activity', '상상마당 전시 보기', 'KT&G 상상마당'),
    ('anthracite', 2, '16:30', 'dining', '연희동 카페', '앤트러사이트 연희점'),
    ('bookstreet', 2, '18:00', 'activity', '경의선 책거리 산책', '경의선책거리'),
    ('sogeum', 2, '19:30', 'dining', '마포 소금구이 저녁', '마포 소금구이 골목'),
    ('sila_co', 3, '09:00', 'lodging', '호텔 체크아웃', '신라스테이 광화문'),
    ('yongsan', 3, '09:40', 'mobility', '택시로 용산역 이동', '용산역'),
    ('yongsanpark', 3, '10:30', 'activity', '용산가족공원 산책', '용산가족공원'),
    ('budae', 3, '12:30', 'dining', '부대찌개 점심', '용산 부대찌개골목'),
    ('dmuseum', 3, '14:30', 'activity', '디뮤지엄 전시', '디뮤지엄'),
    ('parnas_ci', 3, '17:00', 'lodging', '호텔 체크인', '그랜드 인터컨티넨탈 서울 파르나스'),
    ('samwon', 3, '19:00', 'dining', '삼원가든 한우 저녁', '삼원가든'),
    ('yangjae', 4, '09:00', 'activity', '양재시민의숲 산책', '양재시민의숲'),
    ('seorae_brunch', 4, '11:30', 'dining', '서래마을 브런치', '서래마을 브런치카페'),
    ('seorae_walk', 4, '13:30', 'activity', '서래마을 골목 산책', '서래마을'),
    ('lwm_shop', 4, '15:30', 'activity', '롯데월드몰 쇼핑', '롯데월드몰'),
    ('lwm_din', 4, '18:00', 'dining', '푸드홀에서 저녁', '롯데월드몰'),
    ('parnas_co', 5, '09:00', 'lodging', '호텔 체크아웃', '그랜드 인터컨티넨탈 서울 파르나스'),
    ('ihwa', 5, '10:30', 'activity', '이화벽화마을 산책', '이화벽화마을'),
    ('ikseon', 5, '12:00', 'activity', '익선동 한옥거리 구경', '익선동 한옥거리'),
    ('mandu', 5, '13:00', 'dining', '북촌손만두 점심', '북촌손만두'),
    ('maro2', 5, '15:00', 'activity', '마로니에공원 마지막 산책', '마로니에공원'),
    ('hyoja', 5, '16:30', 'dining', '효자베이커리 간식', '효자베이커리'),
    ('airport_out', 5, '19:00', 'mobility', '공항철도로 인천공항 이동', '서울역'),
]
RAW.sort(key=lambda r: (r[1], r[2]))
ID = {r[0]: n + 1 for n, r in enumerate(RAW)}
items = [{'id': ID[r[0]], 'date': D[r[1]], 'start': r[2], 'kind': r[3], 'title': r[4], 'place': r[5]} for r in RAW]


def H(*turns):
    return [{'role': 'customer' if k % 2 == 0 else 'service', 'text': t} for k, t in enumerate(turns)]


Q = {
    'context_pronoun': [
        ('거기 줄 길어?', 'mijin', H('첫날 점심 어디야', '12시 30분 미진 메밀국수예요')),
        ('뒤에 거 시간 바꿔줘', 'jeoldusan', H('수요일 오전 뭐 있어', '합정역 이동, 절두산 순교성지 산책이에요')),
        ('새로 가는 호텔 조식 되나?', 'parnas_ci', H('목요일 숙소 알려줘', '오전 9시 신라스테이 체크아웃, 17시 파르나스 체크인이에요')),
        ('그 집 예약 필요해?', 'lwm_din', H('금요일 저녁 뭐야', '롯데월드몰 푸드홀 저녁(18시)이에요')),
        ('가운데 거 취소해줘', 'terarosa', H('화요일 오후 일정', '국립극장 공연(14시), 테라로사 카페(16시), 마로니에공원 산책(18시)이에요')),
        ('그거 30분 당겨줘', 'airport_out', H('토요일 마지막 일정 뭐야', '19시 서울역에서 공항철도로 인천공항 이동이에요')),
        ('거기서 그 다음 일정은?', 'gogung', H('청와대 몇 시야', '첫날 14시 30분이에요')),
        ('산책 쪽만 빼줘', 'seorae_walk', H('서래마을 일정 알려줘', '금요일 브런치(11시 30분)와 산책(13시 30분) 두 개예요')),
    ],
    'duplicate_place': [
        ('화요일 마로니에공원 몇 시야', 'maro1', []), ('토요일 마로니에공원 취소', 'maro2', []), ('서래마을 브런치 시간', 'seorae_brunch', []),
        ('서래마을 산책 몇 시', 'seorae_walk', []), ('롯데월드몰 쇼핑 시간', 'lwm_shop', []), ('롯데월드몰 저녁 예약했어?', 'lwm_din', []),
        ('신라스테이 체크아웃 시간', 'sila_co', []), ('파르나스 체크인 몇 시야', 'parnas_ci', []),
    ],
    'confusable_name': [
        ('국립고궁박물관 관람 시간', 'gogung', []), ('국립한글박물관 몇 시', 'hangeul', []), ('국립극장 공연 시간', 'ntheater', []), ('미진 예약했어?', 'mijin', []),
        ('을지면옥 시간', 'euljimyeon', []), ('절두산 몇시에 가', 'jeoldusan', []), ('경의선책거리 시간', 'bookstreet', []), ('국립현대미술관은 언제 가?', None, []),
    ],
    'compound_intent': [
        ('청와대 취소하고 고궁박물관 시간 알려줘', 'cheongwadae', []), ('을지면옥 예약하고 국립극장 몇 시인지도', 'euljimyeon', []),
        ('디뮤지엄 시간 옮기고 용산가족공원 취소해줘', 'dmuseum', []), ('양재시민의숲 몇 시야? 그리고 서래마을은?', 'yangjae', []),
        ('진주집 빼고 상상마당 한 시간 당겨줘', 'jinju', []), ('미진 취소, 청와대는 그대로', 'mijin', []),
        ('효자베이커리 시간 알려주고 북촌손만두도', 'hyoja', []), ('합정역 이동 미루고 절두산도 빼줘', 'hapjeong', []),
    ],
    'negation': [
        ('청와대 말고 국립고궁박물관 시간', 'gogung', []), ('미진 말고 그 다음 일정 시간', 'cheongwadae', []), ('국립극장 말고 그 전 일정', 'euljimyeon', []),
        ('이화벽화마을 말고 익선동 취소', 'ikseon', []), ('월요일 청와대 말고 저녁 시간', 'gwanghwamunjip', []), ('화요일 국립극장 말고 첫 일정', 'hangeul', []),
        ('마로니에공원 화요일 말고 토요일 거 시간', 'maro2', []), ('북촌손만두 말고 효자베이커리 시간', 'hyoja', []),
    ],
    'typo_slang': [
        ('청와대 몇시얌', 'cheongwadae', []), ('고궁박물관 몇시임?', 'gogung', []), ('한글박물관 몇싱', 'hangeul', []), ('을지면옥 시간ㅇㅇ', 'euljimyeon', []),
        ('양제시민의숲 몇시욤', 'yangjae', []), ('상상마당 몇시양', 'sangsang', []), ('이화벽화마을 시간임?', 'ihwa', []), ('북촌만두 취소ㅠㅠ', 'mandu', []),
    ],
    'out_of_scope': [
        ('지금 몇 도야?', None, []), ('ㅎㅎㅎㅎ', None, []), ('이더리움 시세 알려줘', None, []), ('파이썬 리스트 정렬 코드', None, []),
        ('너 누가 만들었어', None, []), ('서울에서 자전거 빌리는 법', None, []),
        ('고생하셨어요 감사합니다', None, H('청와대 시간', '14시 30분이에요')), ('취소 수수료 얼마야?', None, []),
    ],
    'nameless_description': [
        ('메밀국수 먹는 첫날 점심', 'mijin', []), ('냉면집 화요일 점심', 'euljimyeon', []), ('옛 대통령 관저 구경', 'cheongwadae', []), ('한글 전시 보는 곳', 'hangeul', []),
        ('공연 보는 날 오후', 'ntheater', []), ('벽화 골목 걷는 거', 'ihwa', []), ('빵집에서 간식', 'hyoja', []), ('책방 골목 산책', 'bookstreet', []),
    ],
    'ordinal_relative': [
        ('화요일 첫 식사', 'euljimyeon', []), ('목요일 마지막 일정', 'samwon', []), ('이틀째 세번째', 'ntheater', []), ('금요일 두번째 활동', 'seorae_walk', []),
        ('청와대 바로 다음', 'gogung', []), ('을지면옥 끝나고 뭐 해?', 'ntheater', []), ('마지막 날 첫 일정', 'parnas_co', []), ('여행 마지막 식사', 'hyoja', []),
    ],
    'change_request': [
        ('청와대 30분 미뤄줘', 'cheongwadae', []), ('이화벽화마을 빼줘', 'ihwa', []), ('디뮤지엄 취소할게요', 'dmuseum', []), ('국립극장 한 시간 당겨줘', 'ntheater', []),
        ('일정 좀 옮겨줘', None, []), ('그 시간 미뤄주세요', None, []),
        ('그거 취소해줘', 'samwon', H('삼원가든 몇 시야', '목요일 19시예요')), ('삭제해줘', 'jeoldusan', H('절두산 시간', '수요일 10시 30분이에요')),
    ],
    'absent_but_plausible': [
        ('N서울타워 전망대 몇 시', None, []), ('이태원 클럽 언제 가', None, []), ('강남역 지하상가 몇 시', None, []), ('어린이대공원 몇 시야', None, []),
        ('경복궁 언제 가?', None, []), ('북촌한옥마을 시간 알려줘', None, []), ('코엑스 별마당 몇 시야', None, []), ('서울숲 몇 시에 가', None, []),
    ],
}
qs = []
for typ, rows in Q.items():
    assert len(rows) == 8, typ
    for q, k, hist in rows:
        qs.append({'q': q, 'gold': ID[k] if k else None, 'type': typ, 'split': 'held', 'history': hist})
json.dump({'sets': {'mix5': {'today': TODAY, 'items': items, 'qs': qs}}}, open(os.path.join(HERE, 'fixtures', 'mix5.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
from collections import Counter
print('mix5 항목', len(items), '· 문제', len(qs), '· 정답 null', sum(x['gold'] is None for x in qs), '· 앞 대화', sum(bool(x['history']) for x in qs), '· 종류', dict(Counter(i['kind'] for i in items)))
# 학습 자료와 장소 이름이 겹치는지 점검(있으면 보고)
train_dir = os.path.join(HERE, '..', '..', '..', 'datasets', 'travel', 'plan_qa_bench', 'train')
names = set()
for f in glob.glob(os.path.join(train_dir, 'places_*.json')):
    names |= {p['name'].replace(' ', '') for p in json.load(open(f, encoding='utf-8'))['places']}
mine = {i['place'].replace(' ', '') for i in items}
print('학습 자료 장소와 겹침:', sorted(n for n in mine if any(n == t or n in t or t in n for t in names)) or '없음')
