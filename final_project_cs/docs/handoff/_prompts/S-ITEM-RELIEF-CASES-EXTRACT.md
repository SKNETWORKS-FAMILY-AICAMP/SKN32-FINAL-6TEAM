# S-ITEM-RELIEF-CASES-EXTRACT — 품목별 피해구제 사례 678건에서 반품/배송 관련 93건 추출·분류

## 0. 배경 (읽기만)

- `datasets/voc/data_go_kr_consumer_complaints/raw/15090382_item_relief_cases.xml`
  — 한국소비자원 "품목별 피해구제 사례" 678건. Excel XML 형식(`<Workbook><Worksheet><Table><Row><Data>`).
  컬럼: 일련번호·품목·출처·제목·질문·답변(전부 실제 서술형 텍스트).
- Claude 가 이미 확인한 사실: 제목에 "반품/환불/교환/청약철회/배송" 키워드가
  들어간 case 가 678건 중 93건이다. 이 작업은 그 93건을 실제로 뽑아서
  구조화하고, A-COP 의 두 팀(Fulfillment & Logistics, Return/Refund &
  Evidence)에 어느 쪽이 더 관련 있는지 분류하는 것이다.
- `program/research/_분쟁조정사례_2026-08-20.md` — 기존에 Claude 가 소비자24
  에서 손으로 고른 4건짜리 문서(전문 서술형). 이번 93건은 그거보다 훨씬
  많아서 같은 전문 서술 형식이 아니라 **구조화된 데이터 + 요약 문서**로
  만든다.

## 1. 할 일

1. `15090382_item_relief_cases.xml` 을 파싱해라(Excel XML — 표준 XML
   파서로 `<Row>`/`<Data>` 를 읽으면 된다, 별도 라이브러리 불필요).
   HTML 엔티티(`&#13;` 등 줄바꿈 문자)를 정리해라.
2. 제목·질문·답변 전체 텍스트를 대상으로 반품/환불/교환/청약철회/배송
   관련 case 를 골라내라(Claude 가 확인한 93건 근처가 나와야 한다 — 정확히
   93이 아니어도 되지만, 크게 다르면(예: 50건 이하거나 150건 이상) 왜
   다른지 리포트에 설명해라).
3. 골라낸 case 를 두 그룹으로 분류해라:
   - **배송/이행 관련** (Fulfillment & Logistics 몫) — 예: 배송 파손,
     오배송, 배송 지연, 미배송
   - **반품/환불/교환 관련** (Return, Refund & Evidence 몫) — 예: 청약철회,
     단순변심 반품, 하자 교환, 환불 거부/지연
   - 둘 다 걸치는 case(예: "배송 파손으로 인한 환불 거부")는 두 그룹에
     다 넣되 왜 겹치는지 표시해라. 임의로 하나만 고르지 마라.
4. 결과를 JSONL 두 개로 저장해라(각 줄: `{"seq": 일련번호, "item_category":
   품목, "title": 제목, "question": 질문, "answer": 답변}`):
   - `datasets/voc/data_go_kr_consumer_complaints/processed/fulfillment_logistics_relevant_cases.jsonl`
   - `datasets/voc/data_go_kr_consumer_complaints/processed/return_refund_evidence_relevant_cases.jsonl`
5. 원본 인코딩이 EUC-KR 인 다른 6개 CSV 와 달리 이 XML 파일은 UTF-8 인지
   먼저 확인해라(다르면 리포트에 정확히 적어라 — 지어내지 마라).

## 2. 검증 스크립트 (별도로 작성, 추출 스크립트 자신이 스스로 검증하면 안 됨)

- 두 JSONL 파일의 총 행 수와 원본 93건(또는 실제로 찾은 건수)의 관계가
  산술적으로 맞는지(교집합 case 는 양쪽에 다 있어야 하므로 단순 합계가
  아니라 "교집합 제외 합집합 = 원래 골라낸 건수"인지) 확인해라.
- 무작위 5건을 골라 원본 XML 의 해당 `일련번호` row 와 텍스트가 정확히
  일치하는지 대조해라(지어낸 요약이 아니라 원문 그대로인지).
- 두 파일 모두 유효한 JSON 라인인지, 필수 키가 다 있는지 전수 검사해라.

## 3. 요약 문서

`docs/reports/2026-08-20_S-ITEM-RELIEF-CASES-EXTRACT_리포트.md` 에:
- 실제로 몇 건을 찾았는지, 배송/이행 몇 건, 반품/환불/교환 몇 건, 겹치는
  게 몇 건인지
- 품목별 분포(전자상거래가 몇 건, 다른 품목은 몇 건인지)
- 대표 사례 3~5개를 실제 원문 그대로 인용(요약하지 말고 원문)
- §2 검증 스크립트 실행 결과(실제 터미널 출력)

## 4. 쓰기 대상

★이번엔 작업 루트가 `final_workspace`(상위 폴더) 전체다 — `-C` 가 그렇게
설정돼 있다. 아래 경로는 전부 `final_workspace` 기준 상대경로다.

- `datasets/voc/data_go_kr_consumer_complaints/processed/fulfillment_logistics_relevant_cases.jsonl` (신규)
- `datasets/voc/data_go_kr_consumer_complaints/processed/return_refund_evidence_relevant_cases.jsonl` (신규)
- `datasets/voc/data_go_kr_consumer_complaints/processed/verify_item_relief_extraction.py` (신규, 검증 스크립트)
- `final_project_cs/docs/reports/2026-08-20_S-ITEM-RELIEF-CASES-EXTRACT_리포트.md` (신규
  — 이번엔 `final_project_cs/` 접두사 필요, 워크스페이스 루트 기준이라서)

## 5. 하지 말 것

- 원본 `raw/15090382_item_relief_cases.xml` 수정 금지
- 텍스트를 요약·의역하지 마라 — `question`/`answer` 필드는 원문 그대로
  옮긴다
- 다른 6개 CSV 파일 건드리지 마라
- `program/research/_분쟁조정사례_2026-08-20.md` 수정 금지(별개 문서다)
