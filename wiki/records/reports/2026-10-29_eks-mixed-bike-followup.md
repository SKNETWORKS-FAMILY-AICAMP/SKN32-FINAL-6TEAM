---
type: report
title: EKS 섞어 준 자전거 58 후속 — 출발 문맥 직접 단언·earliest_on_late 혼합 시험
status: draft
domain: travel
---

# 섞어 준 자전거 58 후속 시험 2개

선행 [보고서](2026-10-29_eks-mixed-bike-planned.md)의 「필수 아님」 후속 3개 중 2개를 시험으로 잠갔습니다. 시험만 더했습니다. 제품·픽스처·golden·기존 단언 변경은 0입니다. 누적 해소는 **2/5 = 40%** 그대로이고, 잔여 3/5와 PR110 **draft/HOLD**도 그대로입니다. push·병합·배포·운영 쓰기·모델 호출은 0입니다.

## 담당·겹침 확인

- 선행 사본 `/root/eksbike_planned_1029/review`는 깨끗했고(tracked diff 0, HEAD 56fc3ce1), WSL은 이 작업 전에 정지 상태였습니다. 실행 중인 eks 관련 프로세스도 없었습니다. 다른 담당과 겹치지 않는 범위로 판단했습니다.
- 새 no-hardlinks 사본 `/root/eksbike_followup_1029/review`(브랜치 `fix/mobility-mixed-bike-followup-20261029`, 기준 56fc3ce1)를 만들었습니다. 입력 113/113 = 100%를 SHA256으로 확인했습니다. 선행 사본·증거는 수정하지 않았습니다.
- main `57f3d2f004d0`, PR110 open/draft head `3fda4eee`는 그대로입니다(읽기만 확인).

## 더한 시험(test_plan_bike_v1 U축 +2)

| 시험 | 단언 |
|---|---|
| `test_mixed_bike_departure_context_direct` | MIXED_BIKE_CASES 4경우마다 `departure_context`에 bike 후보·bike 구간이 없고, 캡처 시각을 뺀 문맥 전체가 bike를 뺀 같은 요청과 같다. 자전거만 성립(skipped)이면 문맥을 만들지 않는다(대조와 같음). |
| `test_mixed_bike_earliest_on_late` | 앞 일정 13:00 끝·도착 13:05·`earliest_on_late`. 자전거 성립(eta 1)·불성립(대여소 없음) 두 경우 모두 skipped code·earliest 전체가 bike를 뺀 요청과 같고, left_out에 자전거 한 줄만 더해진다(성립 → `bike_not_recommended`, 불성립 → 판정기 code `mode_unavailable`). `~ebike` 판정 0. 대조군 테마(walk,bike)는 종전대로 earliest 계획 수단이 bike다. |

## 실행(Linux aarch64 · Py3.12 · offline guard · `MOBILITY_GH_URL=none`)

| 실행 | 결과 |
|---|---|
| RED — 52f933e8 plan.py | 2/2 실패(earliest가 섞어 준 자전거를 계획 수단으로 냄) |
| RED — 513ab4cc plan.py | 2/2 실패 |
| GREEN — 56fc3ce1 plan.py(sha256 `64b8880222fd8130…`, 선행 최종과 같음) | 2/2 통과 |
| 변이 M1 차단 끔 · M2 술어 `modes & {subway,bus}` · M3 술어 `"bike" in modes` · M4 earliest 차단 끔 | 각각 2 · 1 · 1 · 1 실패 → 4/4 검출, 매번 sha 복원 확인 |
| 기본층(mobility 전체 + intake 경로 후보) | 1621 통과 · 1 skip(선행 1619 + 새 2, 나머지 nodeid 결과 변화 0) |
| golden2(실자료) | 2/2 |
| mobility_full 223 | 220/223. 실패 nodeid 3개가 선행과 같음 → **새 실패 0** |
| ruff 0.16.8 | 통과 |

- mobility_full 실행 시간은 54분으로 선행(6.5분)보다 길었습니다. 같은 시각 Windows 호스트 CPU 부하가 99%였고, 그중 `test_threads_8x80`이 오래 걸렸습니다. 다른 작업의 프로세스는 건드리지 않았습니다. 시간 차이는 성능 회귀의 근거가 아닙니다(시험만 바뀜, plan.py 동일).

## 로컬 커밋

- `47549aa4e867db108d28aeaaff4465253998d9c6`(부모 56fc3ce1, 시험 파일 +51줄). push는 하지 않았습니다. patch는 [증거](../evidence/2026-10-29_eks-mixed-bike-followup/commit.patch)에 있습니다.
- 독립 검토자(Claude/Codex) 검토는 이번에 받지 않았습니다. 시험 전용 변경이고 자체 RED/GREEN·변이로만 확인했습니다.

## 남은 일(변화 없음)

- 후속 3번 「앞 일정보다 먼저 떠나야 하는 자전거 이유 문구 구분」은 하지 않았습니다. 탐침에서 섞어 준 늦은 구간의 `bike_not_recommended` 이유가 「12:54 출발은 성립 확인(역산)」처럼 앞 일정 끝(13:00)보다 이른 출발을 적는 것을 확인했습니다. 문구 계약 결정이 필요해 그대로 두었습니다.
- foot 키를 담은 bike 요약 재기록(GH 기기 필요), 3실패(earliest after_last_holiday · mixed stations_blocked · station_fallback only_blocked), 통합 예약.
- 운영 EKS reader fatal: 이번에도 기존 허용 읽기 로그 경로가 없습니다(로컬 aws/kubectl 없음, PR110 변화 없음). 원인은 미확정이고 PR110 HOLD를 유지합니다. 새 workflow·권한으로 우회하지 않았습니다.
- 팀플로에 넣는 작업은 사용자 지시대로 manager(`role-manager`) 브랜치 담당으로만 넘깁니다. 이번 작업은 팀플로에 넣지 않았습니다.

작업 폴더 `C:/_proj/eksbike_followup_1029`, 사본 `/root/eksbike_followup_1029/review`. [증거](../evidence/2026-10-29_eks-mixed-bike-followup/)에 로그·exit·변이·비교·SHA256SUMS가 있습니다.
