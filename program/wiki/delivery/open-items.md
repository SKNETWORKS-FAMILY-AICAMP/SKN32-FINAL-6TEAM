---
type: plan
title: 열린 항목
description: 아직 안 끝난 일과 미확인 사항. 완료된 것은 여기 없다
status: draft
tags: [release]
owners: [human:미배정]
---

# 열린 항목

`[실측]` `A-COP_남은작업_인수인계.md`(2026-08-24 작성)에서 **살아 있는 것만** 추출.

**완료된 것은 안 적는다.** 원본은 완료 항목까지 다 담아서 무엇이 남았는지 찾기 어려웠다.

## 사람이 해야 하는 것

| 항목 | 왜 AI가 안 하나 |
|---|---|
| `git push -u origin workspace` | **AI 세션은 푸시를 실행하지 않는다** |
| **★ wiki 저장소 전환** | **준비 완료.** 사용자가 부르면 실행 — 놓을 자리만 정하면 된다 → [D-012](../decisions/D-012-cutover-timing.md) |

## 미확인

`[미확보]` 정직하게 적는다.

| 항목 | 상태 |
|---|---|
| v2 계약 문서 | 다른 세션 작업 중. **endpoint 이름·`config_revision`·인증 scope·감사 필드를 하나로 맞춰야 한다** |
| UI가 import할 패키지 이름 | 확정 안 됨 |

## 확인 완료로 닫은 것

| 항목 | 결과 |
|---|---|
| VOC 데이터 전처리 8종 | **2026-09-01 전부 완료** |
| `implementation_ref` allowlist 제한 | **확인됨.** `KNOWN_IMPLEMENTATION_REFS`로 코드에 있고 Composer HTTP 경로에만 적용 |
| Composer 범위 재검토 | → [D-CS-001](../../final_project_cs/wiki/decisions/D-CS-001-composer-ui-removal.md) 외 Composer 계열 결정 |
| **쿠팡 배송이력 5건 중 4건만 수집** | **★ [2026-09-04] 확인됨 — 정상 동작.** `preprocess_stats.json`을 열어 보니 8건 중 취소 3건(배송 자체 없음) 제외 5건 중 1건이 송장번호 미기재. 데이터 결손 아님 → [`../../datasets/wiki/scraper-notes.md`](../../datasets/wiki/scraper-notes.md) |

## 문서 쪽 열린 항목

| 항목 | 어디 |
|---|---|
| 이관 199건 (사람 판정 60) | [../governance/migration-scope/index.md](../governance/migration-scope/index.md) |
| 골든셋 라벨링 절차 확인 | [../evaluation/golden-set.md](../evaluation/golden-set.md) |
| Team 경계 불변식 3개 자동화 | [`quality/invariants.md`](../../final_project_cs/wiki/quality/invariants.md) |
| **DoD evidence 9건이 낡았다 — `final_project_cs/docs/evidence/` 수정 필요** (2026-09-06 대조로 확인) | [`quality/dod-evidence-drift.md`](../../final_project_cs/wiki/quality/dod-evidence-drift.md). 06은 sample을 잰 것, 08은 대상 Team이 퇴역, 13·21은 옛 라벨, 14·22·02·20·24는 일부 낡음. **wiki가 아니라 evidence 원본을 고쳐야 하는 일이라 cs 저장소 작업자 몫** |

## 측정 대기

`[미확보]` 반나절~하루면 되는데 결론을 크게 바꾸는 것들.

| 순위 | 무엇 | 무엇이 흔들리나 | 시간 |
|---|---|---|---|
| ~~1~~ | **3B 모델 VRAM 상한** — **해결** | 12GB 확정(세션 1 실측) → [../business/gpu-limits.md](../business/gpu-limits.md). **처리량(tok/s)은 아직** | 반나절 |
| **2** | **검토·승인 1건 소요시간** | **72% 절감이 여기 달려 있다.** 도구 설치 완료 → [../business/measure-review-time.md](../business/measure-review-time.md) | **30분** |
| ~~2~~ | **오류 1건당 손실** — **일부 측정** | 분쟁 8건 실측. 중앙값 5만 · 최대 152.6만 → [../business/error-cost.md](../business/error-cost.md) | 완료 |
| 3 | Baseline A·B 재측정 | **"단순 LLM보다 낫다"를 못 말한다** | **D-010 대기** |
| 4 | **DoD-28 재측정** | **0% 가 모델 성능이 아니었다** → [../evaluation/dod28-rerun.md](../evaluation/dod28-rerun.md) | D-010 대기 |

→ [../business/index.md](../business/index.md)

## ★ [2026-09-03] 미측정을 없애는 절차

`[실측]` `A-COP_페인포인트_페르소나_설계.md` §8 에서 이관. **이 절이 빠져 있었다.**

**`[추정]`·`[미확보]` 를 없애는 방법이 이미 정해져 있었다.** 지금 있는 데이터로 대부분 채울 수 있다.

### 1단계 — 있는 데이터로 채운다

| 채울 것 | 쓸 데이터 |
|---|---|
| ~~골든셋 페르소나 배분~~ **완료** | [personas.md](../product/personas.md) 재검증. 정미라 행 18→**28건(38.9%)** 정정 |
| ~~실제 문의 유형 분포~~ **확인 결과: 못 구한다** | [golden-set.md](../evaluation/golden-set.md). **자체 정정** — 처음엔 aihub_30716 이 order 40% 라고 적었는데 틀렸다. `sample_per_group` 층화표집이라 표본 자체가 균등하다 |
| ~~커머스 문의 유형~~ **동일 사유로 못 구한다** | `aihub_102_smb_order_qa` 도 `sample_per_group: 400` 층화표집 (stats.json 확인). 둘 다 자연 빈도가 아니다 |
| ~~오류 비용의 실제 사례~~ **완료** | [error-cost.md](../business/error-cost.md) |
| ~~감정 축 검증~~ **확인 결과: 못 한다** | [golden-set.md](../evaluation/golden-set.md). `aihub_71603` 은 제품 만족도(긍정/부정)를 재고 골든셋은 상담 중 감정·불확실성을 잰다 — **다른 축이라 대조 불가** |
| `cost/case` 실측 | eval harness 실행 |

**네 번째가 특히 중요하다.** **분쟁 조정까지 간 사례집**이므로 "오류 1건이 얼마나 커지는지"의 실제 근거가 된다.

> **지어낸 숫자를 안 써도 된다.**

`[실측]` 그 데이터는 이미 있다. → [../../datasets/wiki/source-selection.md](../../datasets/wiki/source-selection.md)

### 감정 축 검증이 뭘 가리나

**worried/confused 50% 가 골든셋 특성인지 일반 특성인지**를 판별한다.

**골든셋만의 성질이면 그 50% 로 제품을 설명하면 안 된다.**

## 아직 안 정한 것 셋

`[실측]` 같은 문서 §9.

| 항목 | 판단 |
|---|---|
| v8 병합 시점 | 중간발표(2026-09-15) 전 / 후 |
| 골든셋 `persona` 필드 추가 담당 | `final_project_cs` 소유자와 협의 |
| 축 1 공개 통계 확보 여부 | 확보 시도 / 미확보 유지 |

## [2026-09-03] 인수인계에서 남은 것

`[실측]` `A-COP_남은작업_인수인계.md` 에서 이관. **대부분 완료됐고 둘이 남았다.** (쿠팡 배송이력 항목은 2026-09-04 확인 완료로 닫혔다 — 위 표 참고)

| 항목 | 상태 |
|---|---|
| VOC 데이터 전처리 | **완료** (2026-09-01) |
| `implementation_ref` allowlist 제한 | **확인됨** — `KNOWN_IMPLEMENTATION_REFS`. Composer HTTP 경로에만 적용 |
| **네이버 주문 4건 누락** | `[미확보]` **아직 안 고쳐졌다.** 로그인 상태 실제 DOM 필요 — 코드만으로 진행 불가 → [../../datasets/wiki/scraper-notes.md](../../datasets/wiki/scraper-notes.md) |
| **v2 계약 문서 정합** | `[미확보]` endpoint 이름·`config_revision`·인증 scope·감사 필드를 **하나로 맞춰야 한다** → [D-011](../decisions/D-011-composer-v3-gap.md) |
| **UI 가 import 할 패키지 이름** | `[미확보]` 아직 확정 안 됨 |

**세 번째가 D-011 과 같은 문제다.** 계약이 둘로 갈려 있어서 이름부터 안 맞는다.

## 원격 추적은 사람이 한다

`[실측]` 원본이 명시해 뒀다.

> **AI 세션은 푸시를 실행하지 않는다.** 사용자가 직접 실행한다.

**이 wiki 작업도 같다.** 커밋은 하되 푸시하지 않는다.

## ★ [2026-09-03] 정합성 점검이 남긴 미결 판단 둘

`[실측]` `program/research/_정합성_수정제안.md` 에서 이관. **A 묶음 6건은 적용됐고 B·C 가 미결로 남았다.**

### B-1. `research/index.md` 가 계획서·브리핑을 관리할 것인가

**충돌하는 두 원칙이 있다.**

| | |
|---|---|
| `index.md` 5행 | **"계획서·briefing·final_project 폴더는 이 정리의 대상이 아니다"** |
| 점검 권고 | **최신 문서군을 기준선에 기록하라** |

| 고르면 | 대가 |
|---|---|
| 포함 | **색인의 책임 범위가 넓어진다** |
| 제외 | **기준선 확인 정보가 `CLAUDE.md` 등 다른 문서에만 남는다** |

`[실측]` 2026-09-03 확인 — **아직 안 정했다.** `index.md` 에 그 문구가 없다.

### C-1. `CLAUDE.md` 기준선에 Composer v3 문서군을 넣을 것인가

`[실측]` 2026-09-03 확인 — **두 `CLAUDE.md` 어디에도 `Composer_v3_설계_토글전용` 이 없다.** 미결이다.

**이건 [D-011](../decisions/D-011-composer-v3-gap.md) 이 정해져야 결정된다** — v3 를 채택할지 자체가 미결이라 기준선에 넣을 수 없다.

## 관계

- [timeline.md](timeline.md) — 일정
- [dod.md](dod.md) — 완료 기준
- [../governance/migration-scope/index.md](../governance/migration-scope/index.md) — 문서 이관
