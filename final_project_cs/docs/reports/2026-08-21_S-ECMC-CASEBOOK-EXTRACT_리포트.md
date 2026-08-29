# S-ECMC-CASEBOOK-EXTRACT 리포트

## 작업 결과

2024 전자거래분쟁조정사례집 PDF를 PyMuPDF로 추출했다. PDF는 총 67페이지이며, 목차·위원회 소개·통계·예방수칙·리플릿을 제외하고 실제 사례 본문에서 8건을 식별했다. 사례 본문은 원본 PDF 44–59페이지에 있다.

전체 사례는 [all_cases.jsonl](../../../datasets/voc/ecmc_dispute_casebook_2024/processed/all_cases.jsonl)에 저장했고, B2C 쇼핑몰-고객 도메인과 Return & Refund / Fulfillment & Logistics에 맞는 2건은 [return_refund_fulfillment_relevant.jsonl](../../../datasets/voc/ecmc_dispute_casebook_2024/processed/return_refund_fulfillment_relevant.jsonl)에 별도 저장했다.

## 분류

- 포함 2건: 5번 반려견 산소호흡기 대여(온라인 오픈마켓), 7번 여행상품 예약 취소·환불
- 제외 6건: 중고 개인간 거래 5건(1–4번, 8번), 사업자 거래로 보이는 지폐교환기 1건(6번)

문서 앞부분의 거래형태 통계에 의존하지 않고 사례 본문을 직접 확인했다. 문서에는 C2C 거래 설명과 개인간거래 분쟁예방 리플릿도 실제로 포함되어 있었다. 따라서 중고 개인간 거래 사례는 키워드상 환불·반품·배송과 연결되더라도 B2C 쇼핑몰-고객 범위에서는 제외했다.

## 필드와 원문 보존

JSONL에는 문서에 실제 표시된 `case_number`, `title`, `page`, `page_end`와 페이지 범위의 추출 원문 전체인 `raw_text`를 넣었다. `page`는 재검증을 위한 1-based 원본 PDF 시작 페이지이고, 다중 페이지 사례의 끝 페이지는 `page_end`로 기록했다. 요약·의역 필드는 만들지 않았다.

## 검증 결과

`datasets/voc/ecmc_dispute_casebook_2024/processed/verify_extraction.py` 실행 결과:

- 총 페이지: 67
- 전체 사례: 8건
- 관련 사례: 2건
- `raw_text` 비어 있지 않음: 통과
- 페이지 범위 검증: 통과
- 난수 시드 20260821로 무작위 3건을 재선정하여 원본 페이지를 다시 열어 원문 전체 대조: 3건 모두 일치

## 출처·라이선스 기록

원본은 `usr.ecmc.or.kr`의 공개 게시물에서 2026-08-21 확보한 `2024_전자거래분쟁조정사례집.pdf`다. 발행처는 한국인터넷진흥원(KISA) 전자문서·전자거래분쟁조정위원회 사무국이며, PDF 발행월은 2024년 12월이다. 확보 과정에서 공개 게시물 외 별도 이용조건은 확인하지 못했다. PDF 마지막 면에는 판권이 KISA에 있고 허가 없는 무단 전재·복사를 금한다는 고지가 있으므로, 추출 데이터에는 출처와 고지를 함께 남겼다.
