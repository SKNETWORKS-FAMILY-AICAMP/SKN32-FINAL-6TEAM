# -*- coding: utf-8 -*-
"""수집 데이터 보고서(데이터 정의서)를 만든다.

필드 정의는 datasets/commerce/*/processed 의 실제 산출 파일에서 읽은 것이다.
건수는 preprocess_stats.json 과 각 REPORT.md 를 따른다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from docxfill import Doc, esc, check

HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(FORMS))
c = lambda n: os.path.join(REPO, "program", "plan", "diagram", "charts", n)

d = Doc(os.path.join(FORMS, "[데이터 수집 및 저장] 수집 데이터 보고서.docx"),
        os.path.join(HERE, "_tmp_data"))

d.replace_text("SK 네트웍스 Family AI 00기 : _____팀",
               "SK 네트웍스 Family AI 32기 : 6팀 A-COPilot")
d.replace_text("2026. 4. 18. ", "2026. 9. 10.")
d.replace_text("000", "김지혜, 서유현, 송채영, 정세환, 최상욱, 최연우")
d.fill_empty_para("00000014", "https://github.com/roroblack/A-COP.git")
d.fill_empty_para("00000015", "https://github.com/roroblack/A-COP.git")


def fill_row(row_xml, values):
    """행 하나의 셀 텍스트를 values 로 바꾼다. 첫 w:t 만 쓰고 나머지는 비운다."""
    cells = list(re.finditer(r'<w:tc>.*?</w:tc>', row_xml, re.S))
    assert len(cells) == len(values), "셀 수가 다르다 %d vs %d" % (len(cells), len(values))
    out, last = [], 0
    for m, val in zip(cells, values):
        check(val)
        cell = m.group(0)
        seen = [False]

        def sub(t):
            if not seen[0]:
                seen[0] = True
                return '<w:t xml:space="preserve">%s</w:t>' % esc(val)
            return '<w:t xml:space="preserve"></w:t>'

        cell = re.sub(r'<w:t[^>]*>[^<]*</w:t>', sub, cell)
        out.append(row_xml[last:m.start()] + cell)
        last = m.end()
    return "".join(out) + row_xml[last:]


def replace_table_rows(anchor_first, anchor_last, rows):
    """예시 행 하나를 템플릿 삼아 rows 만큼 복제한다."""
    i = d.xml.index(anchor_first)
    rs = d.xml.rindex("<w:tr>", 0, i)
    re_ = d.xml.index("</w:tr>", d.xml.index(anchor_last)) + len("</w:tr>")
    tpl = d.xml[rs:d.xml.index("</w:tr>", rs) + len("</w:tr>")]
    tpl = re.sub(r' w14:paraId="[0-9A-F]{8}"', "", tpl)
    d.xml = d.xml[:rs] + "".join(fill_row(tpl, r) for r in rows) + d.xml[re_:]


# ---------------------------------------------------------------- 1. 개요
d.replace_para("00000028", [
    "본 프로젝트가 쓰는 데이터셋의 개요를 아래 표에 정리한다. "
    "수집 목적과 사용 예정 기능, 출처를 함께 적어 이후 활용 단계에서 참조할 수 있게 한다.",
    "데이터는 두 트랙으로 나눈다. 도메인 사실 트랙은 실제 주문, 반품, 취소, 교환, 리뷰 기록이고 "
    "표현과 의도 트랙은 공개 고객지원 데이터로 문장 다양성과 의도 표현을 보강하는 쪽이다. "
    "표현 트랙으로 주문이나 금액 같은 사실을 주입하지 않는다.",
])

DATASETS = [
    ("commerce/coupang_order_history",
     "본인 쿠팡 계정의 주문과 배송 기록",
     "Context Broker 주문 정보, 골든셋 재료",
     "Case 조회, 배송 문의 응답",
     "본인 계정. 비공개, git 제외"),
    ("commerce/naver_order_history",
     "본인 네이버 계정의 주문 기록",
     "쇼핑몰 한 곳에 구조가 치우치는 것을 막는다",
     "Case 조회",
     "본인 계정. 비공개, git 제외"),
    ("commerce/courier_tracking",
     "국내 택배사 송장 조회 결과",
     "코어 2의 배송조회 Action 실행부",
     "배송조회 Action",
     "택배사 공개 조회. 운영 중 실시간 호출"),
    ("datasets/voc",
     "공개된 고객 문의와 응대 문장",
     "RAG 지식 색인과 표현 트랙 보강",
     "정책 검색, 답변 초안 생성",
     "공개 데이터셋. 라이선스 확인 후 사용"),
    ("datasets/mt",
     "번역 성능 비교 자료",
     "다국어 응대 품질 검토",
     "응답 번역 검토",
     "공개 데이터셋"),
    ("스마트스토어 실데이터",
     "주문, 반품, 취소, 교환, 리뷰 기록",
     "도메인 사실 트랙. 파인튜닝 2차와 골든셋",
     "Case 분류, ActionProposal 근거",
     "본인 계정. 비식별화 후 사용"),
    ("검증 쇼핑몰",
     "주문과 반품 시나리오",
     "확장 범위 검증",
     "주문과 반품 Action 확인",
     "준비 중. 확보된 데이터로 단정하지 않음"),
]
replace_table_rows("예: 상담 로그 샘플", "내부 테스트", DATASETS)

# ---------------------------------------------------------------- 2. 수집 방법
d.replace_para("00000041", ["2.1 수집 방식"])
d.insert_after_para("0000004F", d.build([
    ("l", "웹 크롤링. 쓰지 않는다. 로그인 자동화와 봇 탐지 우회는 하지 않는다."),
    ("l", "브라우저 확장. 쓴다. 사용자가 직접 로그인한 상태에서 본인 계정의 기록만 읽는다. "
          "페이지에 이미 들어 있는 JSON을 읽으므로 화면 클릭이나 페이지 이동이 필요 없다."),
    ("l", "API 호출. 쓴다. 택배사 배송 이력 조회에 사용한다."),
    ("l", "공개 데이터셋 내려받기. 쓴다. VOC와 번역 자료에 사용한다."),
    ("l", "사용자 입력. 쓰지 않는다."),
]))

d.replace_para("00000054", ["Python. 표준 라이브러리와 JSON 처리. 브라우저 확장은 Manifest V3 자바스크립트다."])
d.replace_para("00000056", ["수동 실행이다. 자동 주기를 두지 않는다. "
                            "본인 계정 데이터라 사람이 로그인한 상태에서만 수집한다."])
d.replace_para("00000058", ["실패를 조용히 넘기지 않는다. 실패 건수를 세어 보고하고 "
                            "수집 결과 파일에 상태값을 남긴다. "
                            "택배 조회는 no_history, not_found, error를 상태로 구분해 저장한다."])
d.replace_para("0000005A", ["아래 그림이 수집부터 사용까지의 흐름이다."])
d.insert_after_para("0000005A", d.image_xml(c("08_pipeline.png"), 6.2)
                    + d.caption("그림 1. 데이터 처리 흐름. 수집한 자료는 정규화와 색인을 거쳐 "
                                "Context Broker가 쓴다."))

# ---------------------------------------------------------------- 3.1 필드
FIELDS = [
    ("orders.jsonl", "order_id", "string", "주문 번호", "16102433396441"),
    ("orders.jsonl", "order_status", "string", "주문 상태", "결제완료"),
    ("orders.jsonl", "seller_name", "string", "판매자 이름", "(주) 홀세일코리아"),
    ("orders.jsonl", "product", "object", "상품 이름과 옵션, 수량", "name, option, quantity"),
    ("orders.jsonl", "payment", "object", "결제 금액과 수단", "amount 4100, method 삼성카드"),
    ("orders.jsonl", "shipping", "object", "배송사와 송장번호", "carrier, tracking_number"),
    ("orders.jsonl", "cs", "object", "문의 여부와 반품 상태", "has_inquiry, return_status"),
    ("orders.jsonl", "_source", "object", "수집 시각과 출처", "crawled_at 2026-08-21T10:58:55Z"),
    ("tracking.jsonl", "order_id", "string", "주문 번호. orders 와 잇는 키", "16102427880443"),
    ("tracking.jsonl", "shipment_box_id", "string", "배송 상자 식별자. 자릿수가 커서 문자열로 둔다",
     "1094088506117996544"),
    ("tracking.jsonl", "courier", "string", "택배사", "로켓배송"),
    ("tracking.jsonl", "tracking_number", "string", "송장번호", "10327889211555"),
    ("tracking.jsonl", "status", "string", "배송 상태 문구", "내일 새벽 도착 보장"),
    ("tracking.jsonl", "events", "array", "배송 이력. 단계와 위치와 시각", "캠프도착, 안양1"),
    ("tracking.jsonl", "queried_at", "string", "조회 시각", "2026-08-21T10:58:55.793Z"),
    ("tracking.jsonl", "outcome", "string", "수집 결과 구분", "collected"),
]
replace_table_rows("chat_logs.csv", "2025-05-10 15:01:22", FIELDS)

# ---------------------------------------------------------------- 3.2 데이터 양
d.replace_para("00000073", [
    "팀원 제출본을 쇼핑몰별로 합쳐 네 파일로 둔다. 합계 5,773행이다. "
    "VOC 공개 데이터는 9종 중 5종 전처리를 마쳤고 4종 924MB 가 남았다.",
])
# ★합본 네 개. 주문과 배송을 나누고, 그 안에서 다시 쇼핑몰로 나눈다.
#   두 쇼핑몰의 배송 레코드 모양이 달라서 한 파일에 담으면 읽는 쪽이 매번 갈라야 한다.
MERGED = [
    ("team_naver_orders", "네이버 주문", "270", "cyw 68 · kjh 101 · syh 44 · csw 57"),
    ("team_coupang_orders", "쿠팡 주문", "3,483", "cyw 9 · syh 2,651 · csw 366 · scy 457"),
    ("team_naver_tracking", "네이버 택배 배송", "238", "cyw 58 · kjh 88 · csw 49 · syh 43"),
    ("team_coupang_tracking", "쿠팡 택배 배송", "1,782", "cyw 4 · syh 1,212 · csw 283 · scy 283"),
]
d.insert_after_para("00000073", d.build(
    [("b", "팀 합본 네 파일 (datasets/commerce/_dist/)")]
    + [("l", "%s.jsonl, %s %s행. 제출자별 %s" % (f, label, n, by)) for f, label, n, by in MERGED]
    + ["행마다 _submitter 와 _platform 과 _source_file 을 박아 출처를 남긴다. "
       "합치고 나면 어느 파일에서 온 행인지 알 방법이 없기 때문이다.",
       "쿠팡 주문의 DeliveryRequest 안 자유입력은 가려서 낸다. 공동현관 비밀번호는 "
       "쿠팡이 가려 보내지만 이 자유입력은 가려지지 않아 집 열쇠 위치가 51행 들어 있었다. "
       "가린 행은 _masked 필드에 무엇을 가렸는지 이름으로 남긴다.",
       "원본 그대로가 필요하면 같은 폴더의 team_submissions_*.zip 을 본다. "
       "그쪽은 바이트도 파일명도 바꾸지 않은 제출본이다."]))
d.replace_para("00000075", ["쿠팡 고유 주문 8건. 취소된 배송 상자 3건과 송장번호 없는 상자 1건은 제외했다. "
                            "택배 이력이 실제로 나온 것은 238건 중 50건이다. "
                            "나머지는 송장번호가 오래돼 택배사가 기록을 지운 것이며 실패로 세지 않는다."])
d.insert_after_para("00000075", d.image_xml(c("09_dataset_status.png"), 5.6)
                    + d.caption("그림 2. 데이터 수집 현황. 못 가져온 부분을 0으로 채우지 않고 그대로 표시했다."))

# ---------------------------------------------------------------- 3.3 저장 위치
d.replace_para("00000078", ["datasets/<도메인>/<이름>/ 아래에 raw, processed, scripts, REPORT.md 를 둔다. "
                            "예를 들어 datasets/commerce/coupang_order_history/processed 다.",
                            "여러 사람의 제출본을 합친 것은 datasets/commerce/_dist/ 에 둔다. "
                            "raw 와 processed 는 한 사람 것이고 _dist 는 팀 전체를 합친 것이라 자리를 나눈다. "
                            "_dist 는 git 에 올라가지 않는다."])
d.replace_para("0000007A", ["JSON Lines 를 쓴다. 한 줄에 한 건이라 큰 파일도 줄 단위로 처리할 수 있다."])
d.replace_para("0000007C", ["UTF-8 을 쓴다."])

# ---------------------------------------------------------------- 4. 법적 윤리적 검토
d.replace_para("0000007F", ["포함한다. 본인 계정의 실제 구매 기록이기 때문이다."])
d.replace_para("00000081", ["주문번호, 판매자 이름, 결제 수단, 송장번호, 배송지 관련 문구"])
d.replace_para("00000083", ["raw 와 processed 를 git 에 올리지 않는다. 스크립트와 스키마와 REPORT.md 만 올린다. "
                            "배포용 압축본도 같은 규칙으로 제외한다. "
                            "문서에는 원문이나 개인정보를 옮기지 않는다."])
d.replace_para("00000085", ["내부 사용에 한정한다."])
d.replace_para("00000087", ["공개 데이터셋은 라이선스와 재배포 조건을 확인한 뒤 사용한다. "
                            "확인되지 않은 항목은 확인 전까지 사용하지 않는다."])
d.replace_para("00000089", ["A-COPilot 전체"])
d.replace_para("0000008B", ["2026-08-28"])

# ---------------------------------------------------------------- 5. 품질
d.replace_para("0000008E", ["주문은 order_id 기준으로 중복을 제거한다. "
                            "배송 이력은 order_id 와 shipment_box_id 조합으로 본다."])
d.replace_para("00000090", ["필수 필드 누락과 날짜 형식 오류를 걸러낸다. "
                            "택배 조회는 스키마 파일로 응답 형태를 검증한다."])
d.replace_para("00000092", ["없는 값은 null 로 두고 0 으로 채우지 않는다. "
                            "화면과 보고서에서도 모름으로 표시한다. 0 은 정상으로 읽히기 때문이다."])
d.replace_para("00000094", ["자릿수가 큰 식별자는 문자열로 저장한다. "
                            "shipment_box_id 는 값이 커서 숫자로 두면 자릿수가 잘린다. "
                            "날짜는 ISO 8601 로 통일한다."])

# ---------------------------------------------------------------- 6. 변경 이력
CHANGES = [
    ("2026-08-21", "A-COPilot", "쿠팡 주문과 배송 수집. 페이지 내 JSON 방식으로 전환", "클릭 없이 수집"),
    ("2026-08-24", "A-COPilot", "정규화 결과 기록. 주문 9행, 배송 4행", "통계 파일에 해시 포함"),
    ("2026-08-28", "A-COPilot", "네이버 4건 누락과 택배 이력 부족을 그대로 기록", "숨기지 않는다"),
    ("2026-08-31", "A-COPilot", "팀원 제출본 반영. 네이버 270건, 택배 질의 238건", "파일명이 아니라 실제로 세어 확인"),
    ("2026-08-31", "A-COPilot", "합본 4파일 5,773행을 _dist 에 생성", "주문과 배송을 쇼핑몰별로 나눔"),
]
replace_table_rows("2025-05-09", "개인정보 보호 강화 조치", CHANGES)

out = d.save(os.path.join(FORMS, "[데이터 수집 및 저장] 데이터 정의서_A-COPilot.docx"))
print("저장:", out)
