# S-ECMC-CASEBOOK-EXTRACT — 2024 전자거래분쟁조정사례집 PDF에서 사례 추출

## 0. 배경 (읽기만)

- `datasets/voc/ecmc_dispute_casebook_2024/raw/2024_전자거래분쟁조정사례집.pdf`
  — 전자문서·전자거래분쟁조정위원회(ECMC, KISA 산하)가 발간한 2024년
  분쟁조정 사례집. 출처: `usr.ecmc.or.kr`, 공개 자료, 승인 절차 없이
  다운로드됨(2026-08-21, Claude가 사용자 승인 후 받음).
- 이 PDF는 (앞서 확인한) `datasets/voc/data_go_kr_consumer_complaints/`
  7종과 다르다 — 저건 행 단위 정형 데이터, 이 PDF는 **사람이 쓴 사례
  서술 문서**(정책·제도 설명 + 실제 조정사례 여러 건이 섞여 있음)다.
- `python -c "import pypdf"`, `import fitz`(PyMuPDF) 둘 다 이 환경에
  설치돼 있다 — 새로 설치할 필요 없다.

## 1. 할 일

1. PDF 텍스트를 페이지 단위로 추출해라(`pypdf` 또는 `fitz` 아무거나,
   한글이 깨지지 않는 쪽을 써라 — 실제로 열어서 확인하고 골라라).
2. 추출한 텍스트에서 **실제 분쟁조정 사례**(사건 개요 + 당사자 주장/쟁점
   + 조정 결과가 있는 단위)를 식별해라. 목차·정책설명·통계 페이지는
   제외해라.
3. 각 사례를 구조화해서 JSONL로 저장해라. 스키마는 문서 실제 구조를 보고
   맞춰라(전형적으로 `title`/`summary`/`outcome` 같은 필드가 되겠지만,
   원문 구조에 없는 필드를 지어내지 마라 — 원문에 실제로 있는 것만 채운다).
   반드시 포함할 것: `page` (원본 PDF 페이지 번호, 재검증용), `raw_text`
   (해당 사례의 원문 텍스트 전체, 요약 아님).
4. Return & Refund / Fulfillment & Logistics 두 팀과 관련 있는 사례만
   따로 골라 두 번째 JSONL 로도 만들어라(청약철회·반품·환불·교환·배송
   관련 — `S-ITEM-RELIEF-CASES-EXTRACT` 작업과 같은 키워드 기준을 써도
   된다). 이 문서 앞부분 설명(P2P/개인간거래 다루는 부분이 있는지 페이지
   내용으로 직접 확인해라 — 목록 페이지의 소개글만 보고 판단하지 마라)에
   비춰, 우리 도메인(B2C 쇼핑몰-고객 분쟁)과 무관해 보이는 사례(예:
   개인간 중고거래, 순수 광고계약 분쟁)는 제외하되 **제외한 것도 몇 건인지
   세어서 리포트에 남겨라.**

## 2. 검증

- 별도 스크립트로: 총 페이지 수, 추출된 사례 건수, 각 사례의 `raw_text`
  가 실제로 비어있지 않은지, `page` 필드가 실제 PDF 페이지 범위 안에
  있는지 확인해라.
- 무작위 3건을 골라 그 페이지를 다시 열어서 `raw_text` 가 실제 그 페이지
  내용과 일치하는지 대조해라.

## 3. 쓰기 대상 (workspace 루트 기준 상대경로 — `-C` 가 `final_workspace` 다)

- `datasets/voc/ecmc_dispute_casebook_2024/processed/all_cases.jsonl` (신규)
- `datasets/voc/ecmc_dispute_casebook_2024/processed/return_refund_fulfillment_relevant.jsonl` (신규)
- `datasets/voc/ecmc_dispute_casebook_2024/processed/verify_extraction.py` (신규, 검증 스크립트)
- `datasets/voc/ecmc_dispute_casebook_2024/REPORT.md` (신규 — 출처·라이선스·
  추출 방법·건수·검증 결과. `datasets/README.md` 의 기존 REPORT.md 관례를
  따라라 — 다른 데이터셋 폴더의 REPORT.md 를 참고해라)
- `final_project_cs/docs/reports/2026-08-21_S-ECMC-CASEBOOK-EXTRACT_리포트.md` (신규)

## 4. 하지 말 것

- 원본 PDF 수정 금지
- `datasets/voc/data_go_kr_consumer_complaints/` 아래 파일 건드리지 마라
  (별개 작업)
- 텍스트를 의역·요약해서 `raw_text` 에 넣지 마라 — 추출 그대로
- 라이선스가 불명확하다고 임의로 판단하지 마라 — 확인된 사실(공개
  게시물, 별도 이용조건 명시 여부)만 REPORT.md 에 적어라
