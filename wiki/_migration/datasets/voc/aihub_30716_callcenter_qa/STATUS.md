---
type: report
title: AI Hub 30716 — 민원(콜센터) 질의-응답 데이터
description: AI Hub 30716 — 민원(콜센터) 질의-응답 데이터
status: draft
tags: [data]
domain: commerce
domain_note: 이관 전 스테이징 사본이다. 원문을 형식만 바꿔 담아 둔 곳이라 고치지 않는다
---

# AI Hub 30716 — 민원(콜센터) 질의-응답 데이터

## ★2026-08-28 갱신 — K쇼핑 subset 추출·매핑 완료

### 도메인 구분 (완료)

3개 배치 중 **`라벨링데이터_231222_add`에만 K쇼핑이 있다.** 파일명
자체가 이미 카테고리별로 분리돼 있어 별도 필터링이 필요 없었다:

```
민원(콜센터) 질의응답_K쇼핑_{AS,결제,교환,반품,배송,업무처리,주문}_Training.zip
```

(`_220121_add`엔 K쇼핑이 없다 — 금융보험·다산콜센터·질병관리본부뿐이다.
`_220125_add\쇼핑\`엔 readme만 있고 실제 데이터가 없다.)

실측 원본 건수(고객 turn 기준, `상담사` turn 제외):

| 카테고리 | 전체 행 | 고객 의도(QA=Q) turn | A-COP intent 매핑 |
|---|---:|---:|---|
| 주문 | 203,672 | 21,018 | order |
| 결제 | 240,641 | 21,814 | order |
| 배송 | 117,325 | 11,712 | shipping |
| 반품 | 74,894 | 7,369 | return |
| 교환 | 125,958 | 12,558 | exchange |
| AS | 15,635 | 2,398 | **제외** |
| 업무처리 | 227,108 | 17,480 | **제외** |

AS·업무처리는 A-COP의 5개 intent 어디에도 깔끔히 안 들어가서
**의도적으로 제외**했다 — 억지로 `other`에 몰아넣으면 실제로는
"AS 문의"인 걸 "기타"로 왜곡하는 것이다.

### issue_code 매핑 (샘플 기반, 완료)

카테고리별 고객 turn 300건씩(seed=7, 재현 가능) 무작위 샘플링 →
`고객의도`+`고객질문(요청)` 텍스트를 키워드 규칙으로
`app/modules/customer_ops/feedback.py`의 13개 issue_code에
군집화했다. **대부분(90%+)이 `*_other`로 떨어졌다** — 이건 매핑
실패가 아니라 이 원본 데이터의 실제 성격이다: 일반 콜센터 QA
말뭉치라 "입금문의"·"카드등록문의" 같은 **일반 문의**가 대다수고,
A-COP의 issue_code는 golden.jsonl처럼 **분쟁·예외 상황** 위주로
설계돼 있어 애초에 겹치는 부분이 적다. 세부 매핑 성공 건수는
`processed/stats.json`을 봐라(예: `order_change_or_cancel` 39/600,
`shipping_delivered_not_received` 4/300).

PII: 샘플 1500건에서 전화번호 패턴 재검사 결과 0건 — 원본 자체가
이름·전화번호를 "ㅇㅇㅇ" 플레이스홀더로 이미 마스킹해서 배포한다.

### 산출물

- `scripts/extract_and_map.py` — 재현 가능한 추출·매핑 스크립트
- `processed/kshopping_sample.jsonl` — 1,500행(5카테고리×300),
  스키마: `source_category`/`customer_turn_text`/`raw_intent_field`/
  `mapped_intent`/`mapped_issue_code`(불확실하면 `null`)
- `processed/category_mapping.json` — 매핑 규칙 + 매칭 예시
- `processed/stats.json` — 카테고리별 전수/샘플/issue_code 분포

### 한계

- **전수 매핑이 아니라 샘플(카테고리당 300건) 기반**이다. 전체
  110만 건 중 실제로 라벨을 단 건 1,500건뿐이다.
- issue_code 매핑은 키워드 규칙 기반이라 정교하지 않다 — 사람 검수
  없이 이대로 학습·평가 데이터에 쓰면 안 된다.
- `final_project_cs/eval/datasets/golden.jsonl`·`holdout.jsonl`에는
  **아직 병합하지 않았다** — 병합은 더 신중한 별도 결정이 필요하다.
