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

## 미확인

`[미확보]` 정직하게 적는다.

| 항목 | 상태 |
|---|---|
| 쿠팡 배송이력 5건 중 4건만 수집 | `normalize.py` 실행 결과가 배송 4행. 해결됐는지 **미확인** |
| v2 계약 문서 | 다른 세션 작업 중. **endpoint 이름·`config_revision`·인증 scope·감사 필드를 하나로 맞춰야 한다** |
| UI가 import할 패키지 이름 | 확정 안 됨 |

## 확인 완료로 닫은 것

| 항목 | 결과 |
|---|---|
| VOC 데이터 전처리 8종 | **2026-09-01 전부 완료** |
| `implementation_ref` allowlist 제한 | **확인됨.** `KNOWN_IMPLEMENTATION_REFS`로 코드에 있고 Composer HTTP 경로에만 적용 |
| Composer 범위 재검토 | → [D-CS-001](../../final_project_cs/wiki/decisions/D-CS-001-composer-ui-removal.md) 외 Composer 계열 결정 |

## 문서 쪽 열린 항목

| 항목 | 어디 |
|---|---|
| 이관 199건 (사람 판정 60) | [../governance/migration-scope/index.md](../governance/migration-scope/index.md) |
| 골든셋 라벨링 절차 확인 | [../evaluation/golden-set.md](../evaluation/golden-set.md) |
| Team 경계 불변식 3개 자동화 | [`quality/invariants.md`](../../final_project_cs/wiki/quality/invariants.md) |

## 측정 대기

`[미확보]` 반나절~하루면 되는데 결론을 크게 바꾸는 것들.

| 순위 | 무엇 | 무엇이 흔들리나 | 시간 |
|---|---|---|---|
| 1 | 3B 모델 처리량·지연·정확도 | 자체호스팅 논거 전체 | 하루 |
| **2** | **검토·승인 1건 소요시간** | **72% 절감이 여기 달려 있다** | **반나절** |
| 2 | 오류 1건당 손실 | 가격 논거의 상한 | 하루 |
| 3 | Baseline A·B 재측정 | **"단순 LLM보다 낫다"를 못 말한다** | `[미확보]` |

→ [../business/index.md](../business/index.md)

## 관계

- [timeline.md](timeline.md) — 일정
- [dod.md](dod.md) — 완료 기준
- [../governance/migration-scope/index.md](../governance/migration-scope/index.md) — 문서 이관
