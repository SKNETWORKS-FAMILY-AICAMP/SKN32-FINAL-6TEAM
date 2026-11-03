---
type: report
title: 정상입구49 수용 매트릭스 정리 — T15·T16 계약 정렬, T01·I01 예산, notrun24 분류, v8 재실행 준비
date: 2026-10-26
domain: travel
---

# 정상입구49 수용 매트릭스 정리 (2026-10-26 01:20–01:50 KST)

Scratch 후보 폴더에서 작업했습니다: `C:\Users\kcxsz\AppData\Local\hermes\profiles\guguroute\cache\scratch\acceptance49-v8prep-20261026-0121-15828` (상세: `REPORT_KO.md`). 이 저장소의 코드·시험은 바꾸지 않았고, 이 보고서만 새로 추가했습니다.

## 결과
| 항목 | 결과 |
|---|---|
| T15·T16 계약 불일치 | 원인은 시험 기대였습니다. 현재 계약에서는 보류 제안을 `POST …/proposals/{id}/choose`로만 결정하고, 채팅 문장으로 승인하는 경로가 없습니다. 예약·고정 항목을 직접 고쳐 달라는 요청은 보류 제안 없이 `edit_refused`가 됩니다. 기대를 정렬했습니다(2/2 = 100%). 이번 정렬은 시험을 약화하지 않았고, 필수 검사 4개를 추가했습니다. |
| T15·T16 v7a 실모델 판정 | 0/2 pass. **T16은 제품 결함 후보(P1)입니다.** 보류 제안이 없는데 「승인해요」가 `apply_change`로 해석됐습니다. 그 결과 고정된 N서울타워가 덕수궁으로 바뀌어 v1→v2로 저장됐고, 고정 표시도 사라졌습니다(locked=False). D-020 「고정 항목을 우회하지 않는다」를 위반합니다. T15는 일정을 바꾸지 않았지만 공개 상태가 `ask_rollback`이라 기대 밖입니다. |
| T01·I01 예산 미실증 | 차단 원인은 모델 예산(cap 20 = 5+15 소진)입니다. transport가 낸 거절을 제품이 `decision_failed`로 삼켜, 시험에 fail·attempts 0으로 기록됐습니다. 하네스 결함입니다. 행 예약을 제출 전에 하고 `blocked_budget`으로 기록하도록 고쳤습니다. 실측 결과 T01은 pass, I01은 fail입니다(starts_at 22:00 오추출). |
| notrun 24건 | 막힌 사유는 24/24 = 100% 모델 예산 미배정입니다. fixture·경로·DB·시간 때문에 막힌 건은 0/24입니다. v7a zero-model prepare에서 49/49 = 100% 준비됐습니다. zero-model로 판정할 수 있는 건은 0/24입니다. |
| v8 재실행 준비 | `run_full49_v8.py --source <v8>/final_project_cs`로 실행합니다. 예상 호출 49회, 권장 cap 58회, 예상 40.4분, timeout 70분입니다. 하네스 시험은 8/8 통과했습니다. |

결과를 합산하지 않았습니다. v7a 4행 실행은 1/4 = 25% pass입니다. 과거 14/9/24/2와 temporal-f02 결과에는 더하지 않았습니다. 49행 전체를 한 소스에서 판정한 결과는 아직 없습니다.

## 실행 명령
```
<scratch>/date_risk_env_312/Scripts/python.exe run_full49_v8.py --source <v7a>/final_project_cs --prepare --label prepare-v7a-01
<scratch>/date_risk_env_312/Scripts/python.exe run_full49_v8.py --source <v7a>/final_project_cs --rows T15 T16 T01 I01 --max-calls 6 --label real-v7a-T15T16T01I01
<scratch>/date_risk_env_312/Scripts/python.exe -m pytest tests/test_harness_v8.py -q -p no:cacheprovider --confcutdir=tests -o addopts=
```

## 안전·호출
- E4B 실모델은 6/6회 호출했고 모두 stop입니다. lease는 01:40:45에 받고 01:45:44에 반납했습니다.
- live v7a counters는 실행 전후 모두 {36, 5, 5}로 변화가 없습니다. live API(8042)와 프런트는 kill·재시작하지 않았습니다.
- DB 쓰기는 비교 DB `gugu_replay_improved_20261025`의 새 tenant 2개뿐입니다: `acceptance_matrix_20261025_ca7458082a61`, `acceptance_matrix_20261025_7d427a9e6ca8`.
- 실고객, x600, 알림, 유료 호출, 원격 접속, push는 모두 0회입니다.

## 남은 한계
- T16 고정 항목 교체 결함은 수정하지 않았습니다(제품 코드 소유 밖).
- T15 거부 문장 해석 품질과 I01 시각 추출 오류가 남아 있습니다.
- choose-API 보조 행(진짜 승인·거부)은 추가할지 결정이 필요합니다.
- v8 소스가 아직 만들어지는 중이라 전체 49행은 실행하지 않았습니다.
