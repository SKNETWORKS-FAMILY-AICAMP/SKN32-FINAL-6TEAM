---
type: decision
title: 브리핑 안건 7건 판정
description: 개발자2가 올린 데이터 범위 안건 7건을 독립 판정과 교차검증으로 정리한 결과
status: draft
tags: [data, evaluation, governance]
---

# 브리핑 안건 7건 판정

`[실측]` 2026-08-28. 원본은 `program/research/dev2_브리핑_교차검증_2026-08-28.md`.

**검증 방식이 이 문서의 값이다.**

```
Claude 독립 판정  +  Codex 교차검증 대조
```

기준은 `A-COP_구현계획서_v8.md`.

## 판정

| # | 안건 | 판정 |
|---|---|---|
| **①** | **F_판매자취소 8건** | **이관** — Procurement + Order & Payment |
| ② | 품질보증·수리 | **보류** + 게이트 신설 |
| ③ | 쿠폰·상품권 | **현행 제외 유지** |
| ④ | D5 Mock | **golden/holdout 에 넣지 않는다** |
| ⑤ | ETA 3층 | F&L 내부 tool |
| ⑥ | 해외 13% | **표현을 고쳐야 한다** |
| ⑦ | 실송장 시연 | **보조 시연으로 둔다** |

## 왜 그렇게 봤나

### ① 쟁점이 환불이 아니다

**계약 성립·이행이다.** 그리고 **8건으로는 독립 골든셋이 성립하지 않는다.**

`[실측]` 다만 하나는 따로 살린다.

> `#13219` 의 **"주문 급증 = 가격오류 신호"** 는 VOC 이상감지 축으로 따로 살린다

### ② 분모를 오염시키지 않게 게이트를 둔다

```
withdrawal / warranty_repair / mixed / unknown
```

**수리 사례를 청약철회 평가 분모에서 제외해야 한다.** 안 그러면 청약철회 성능이 수리 건 때문에 낮게 나온다.

### ③ 제외의 범위를 좁게 말한다

**실물 배송·회수 범위에서의 제외이지 영구 제외라는 법적 결론이 아니다.** 게이트 로그를 남긴다.

### ④ Mock 을 정답으로 쓰지 않는다

**contract·E2E fixture 로만 쓴다.**

`#13129` 는 역방향 통합 Case 로 보존하되 **객관적 근거가 없으면 정답을 `unknown`/`review_required` 로 둔다.** → [../decisions/D-005-write-gate.md](../decisions/D-005-write-gate.md)

### ⑤ LLM 이 필수가 아니다

| 무엇 | 방법 |
|---|---|
| 파싱·이상감지 | **규칙** |
| ETA | 통계·ML 예측 |

정답은 **각 이벤트 시점부터 실제 배송완료까지의 잔여시간**이다.

`[실측]` **근거 없는 cold-start 상수는 임의 배정 원칙에 걸린다.** 그 구간에서는 이상감지를 끄거나 별도 표시한다.

### ⑥ 기획서와 충돌한다

`#12767` 을 **"검증몰 운영모델과 동일 구조"**라고 한 것이 문제다.

**검증쇼핑몰 기획서는 해외 구매대행을 상품 선정 전제로 삼지 않는다.** 미래 확장·Mock 쟁점으로만 표현해야 한다.

### ⑦ 비결정적인 것을 합격 경로에 두지 않는다

**기록 재생을 합격 경로로 고정하고 실송장은 보조 시연으로 둔다.**

## 확인이 더 필요한 것

`[미확보]` 셋이 남았다.

| 무엇 | 왜 막혀 있나 |
|---|---|
| 품질보증 1년 · 수리→교환→환급 위계 · 상품권 별표 | **현재 법령사실 문서로 검증되지 않는다.** 공식 조문·별표·시행일이 필요하다 |
| 소비자24 원문의 **재식별 위험** | 공개 여부와 무관하게 점검해야 한다 |
| in-scope 정의와 **분모** | 39건 13% 가 어느 집합 기준인지 |

### 재식별 점검에 필요한 것

`[실측]` 원본이 넷을 적어 뒀다.

```
저장·LLM 전달 전 마스킹    join key 분리
최소 증거                  비식별 fixture 와 hash
```

**공개 데이터라도 그대로 넣지 않는다.** → [../../final_project_cs/wiki/data/tenancy.md](../../final_project_cs/wiki/data/tenancy.md)

## Return & Refund 승격 조건 — 그 뒤 어떻게 됐나

`[실측]` 원본 §"계약·기준선". v8 §422는 Return & Refund를 **Registry 계약 + Mock**으로 두고, 실데이터의 **사유 코드 체계와 상태 전이가 확인돼 골든셋 정답 구성이 가능하면 LOCAL 승격**한다고 정했다. 개발자2 브리핑이 그 확인 작업으로 보였으므로 승격 판단이 필요했고, 승격하면 §15-8-A의 golden 60/holdout 20 배분·§1-2·§8-B·§16·§25·DoD를 함께 고친다. **그때 Return의 golden 배분은 0이었다.**

`[미확보]` 승격을 판단한 기록이 없다. 2026-09-06 `config/project.yaml`엔 `return_refund`가 다른 넷과 같은 모양으로 `active: true`·`ReturnRefundTeam`으로 등록돼 있는데, 루트 `CLAUDE.md`는 여전히 "Return & Refund(Mock)"이다. Mock 그대로인지 LOCAL로 올라간 건지 등록 형식만으론 안 보인다 → [team-registry.md](../../final_project_cs/wiki/teams/team-registry.md).

`verdict`(승인/거부/검토필요)는 `TeamResult.decisions[]`에 넣고, `outcome`은 실행 상태(`completed/waiting/handoff/escalated/failed`)라 승인·거부를 넣지 않는다 — 검토필요일 때만 `escalated`나 `waiting`을 병행한다. Team 체이닝은 `next_action=HANDOFF`+`handoff_capability`로, Team 간 직접 호출은 금지. → [team-contract](../../final_project_cs/wiki/teams/team-contract/index.md)

## 관계

- [open-items.md](open-items.md) — 열린 항목
- [../evaluation/golden-set.md](../evaluation/golden-set.md) — 골든셋 구성
- 원본: `program/research/dev2_브리핑_교차검증_2026-08-28.md`
