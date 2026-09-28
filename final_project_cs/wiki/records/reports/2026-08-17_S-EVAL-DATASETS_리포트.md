# 2026-08-17 S-EVAL-DATASETS 리포트

## 작업 범위

쇼핑몰 도메인으로 `eval/datasets/golden.jsonl` 60건과 `eval/datasets/holdout.jsonl` 20건을 전면 재작성했다. 지정된 소유 범위 밖의 파일과 `eval/datasets/attack_fixtures.jsonl`은 변경하지 않았다.

모든 문의는 한국어로 작성했고, `expected_intent`는 `order`, `shipping`, `return`, `exchange` 네 값만 사용했다. `doc_ref`는 `wiki/records/handoff/_prompts/_doc_index.json` 및 실제 `knowledge/documents/`의 문서 ID·섹션 제목과 대조했다.

## 건수 및 배분

| 데이터셋 | order | shipping | return | exchange | 합계 |
|---|---:|---:|---:|---:|---:|
| golden | 15 | 15 | 15 | 15 | 60 |
| holdout | 5 | 5 | 5 | 5 | 20 |

golden은 각 intent의 5개 라우팅 문서를 3건 이상씩 인용하도록 구성했다. 문서별 golden 인용 횟수는 `doc_01`~`doc_10`이 각각 3건, `doc_11` 4건, `doc_12` 3건, `doc_13` 3건, `doc_14` 5건, `doc_15` 5건, `doc_16` 4건, `doc_17` 6건이다. holdout은 golden과 다른 구체 시나리오로 작성하고 모든 항목의 notes를 `holdout; ...; frozen and not used for prompt tuning` 형식으로 고정했다.

## 문서·섹션 근거 요약

| intent | 사용 문서 | golden에서 사용한 섹션 예시 및 시나리오 범위 |
|---|---|---|
| order | doc_06~doc_10 | 주문 조회·시차·비회원 조회, 주문 내용·옵션·부분 변경, 취소 시점·부분 취소·판매자 귀책 취소, 주문 상태 전이·취소완료, 카드·간편결제 실패와 이중 결제 확인 |
| shipping | doc_01~doc_05 | 배송완료 미수령·배송사 회신·대리 수령, 출고 지연·대체 배송, 출고 전/후 배송지 변경, 부재 재배송·반송·배송비, 도서산간 추가 기간·배송 불가·반품/교환 배송비 |
| return | doc_11~doc_14 | 청약철회 기한·특례·접수 시점, 반품 배송비·오배송 판정·선결제, 사용/주문제작 제한·승인, 수량 정정·초과·부분 반품·세트 수량 |
| exchange | doc_15~doc_17 | 교환 기한·동일 상품·재고 선확인, 교환 단계·대체 옵션·재출고·검수, 재고 부족/검수 반려/단종 전환·환불 금액·고객 선택권·전환 사유 재분류 |

승인 흐름은 `doc_01#승인이 필요한 구간`, `doc_08#판매자 귀책에 의한 취소`와 `doc_08#승인 절차가 필요한 지점`, `doc_12#오배송·상품 하자의 판정`, `doc_14#수량 초과 요청의 처리`, `doc_17#전환에 대한 고객의 선택권` 등 실제 승인·판정 문맥이 있는 섹션에 연결했다.

## 다양성 및 검증 결과

| 항목 | 최종 결과 |
|---|---:|
| 전체 ID | 80건, 중복 0건 |
| `wait_for_approval` | 7건 |
| `degraded` 또는 `unavailable` | 4건 |
| `negative` 또는 `frustrated` | 12건 |
| golden 문서 커버리지 | doc_01~doc_17 각 3건 이상 |

실행 명령:

```text
$env:PYTHONIOENCODING='utf-8'; python -m scripts.verify_eval_datasets
```

최종 결과: `전 항목 통과 — 인수 가능`.

중간 점검에서 `g-exchange-15`의 `doc_ref` 섹션명이 색인과 불일치해 1건 실패했으나, 실제 문서 및 색인 재대조 후 `doc_17#전환 사유의 재분류`로 수정하고 검증을 재실행해 통과시켰다.
