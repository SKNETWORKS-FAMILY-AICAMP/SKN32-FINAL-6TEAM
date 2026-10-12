# 문장을 절 단위로 나눠 「어느 절이 대상인가」를 결정론적으로 정한다 (ANVIL 식: 앞단에서 구조화하고 뒤는 코드가 처리).
#  - 「A 말고 B」 : A 는 제외(excl), 대상은 B(rest). B 에 이름이 없고 앞뒤 표현만 있으면 A 가 기준 항목(anchor)이다.
#  - 「A 하고 B」(요청 둘) : 정의상 대상은 먼저 말한 절(first). 연결어는 명시한 동사(취소·예약·알려주·옮기·빼 …)+「고」, 「그리고」, 쉼표, 물음표뿐이다
#    (「끝나고」「먹고」 같은 시간 순서 표현은 자르지 않는다).
import re

NEG = re.compile(r'\s*(?:말고|아니고)\s*')
CONN = re.compile(r'(?:(?:취소|예약|삭제|변경|추가|확인)하|알려주|알려줘|옮기|당기|미루|바꾸|늦추|빼|넣|지우)고\s+|,\s*|\s그리고\s+|\?\s+(?=\S)')


def analyze(q):
    q = q.strip()
    out = {'full': q, 'excl': None, 'tt': q, 'negation': False, 'compound': False}
    m = NEG.search(q)
    if m and q[:m.start()].strip() and q[m.end():].strip():
        out['excl'], out['tt'], out['negation'] = q[:m.start()].strip(), q[m.end():].strip(), True
        return out
    m = CONN.search(q)
    if m and q[:m.start()].strip() and q[m.end():].strip():
        out['tt'], out['compound'] = q[:m.start()].strip(), True
    return out
