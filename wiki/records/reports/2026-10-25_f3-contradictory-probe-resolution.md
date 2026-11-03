---
type: report
title: F3 원문 probe 3건 정식 해소 — 동등 시험으로 대체
status: draft
domain: travel
---

# F3 원문 probe 3건 정식 해소 — 동등 시험으로 대체

[실측] 2026-10-25 사용자 지시("나머지도 해결해야지")로, 서로 모순되는 F3 원문 probe 3건(`test_no_paid_dispatch_if_local_is_queued_between_recheck_and_thread_start[0..2]`)을 삭제·완화 없이 **동등 시험으로 대체**했습니다. 원문 전문은 바이트 그대로, 실패 근거는 시험 주석과 evidence에 보존했습니다. 이는 앞선 "원문 3건 삭제·완화·pass 처리 금지" 원칙을 사용자 지시로 정식 해소한 것이며 다른 원문 시험으로 확대하지 않습니다.

| 항목 | 결과 |
|---|---|
| 모순 재확인(원문 바이트 실행) | 3/3 = 100% — 수정 코드 81행 `paid_called.wait`, 수정 전 코드 90행 `paid == []` |
| 대체 시험, 수정 전 코드 | RED 3/3 = 100% (유료 1회 호출) |
| 대체 시험, 수정 코드 | GREEN 3/3 = 100% (같은 시험 바이트, 전후 hash 동일) |
| F3/reader/failover 회귀 | 208/212 = 98.11% — bind 정책 차단 4, 제품 assertion 실패 0. 이전 보고도 208/212였고 nodeid·상태 동일 |

## 모순

원문 81행은 유료 provider가 호출되어야 풀리는 `paid_called.wait(3)`이고, 그 Event를 set하는 곳은 84행 `paid.append` 뒤뿐이며, 90행은 `paid == []`를 요구합니다. 두 요구는 동시에 만족할 수 없습니다. 근거: [원문·줄 대조·실행 로그](../../../final_project_cs/wiki/records/evidence/2026-10-25_f3_contradictory_probe/README.md).

## 변경

- 시험: `final_project_cs/tests/unit/infrastructure/test_llm_f3_acceptance.py`(대체 시험, 장벽만 "API worker 실제 종료"로 교체, 합격 기준 `paid == []` 동일)와 `test_llm_overflow_f3.py`(원문 probe 자리에 대체 사유·원문 위치를 적은 주석, 나머지 시험 5개는 그대로).
- 보존: `../../../final_project_cs/wiki/records/evidence/2026-10-25_f3_contradictory_probe/test_llm_overflow_f3.original.py.txt`(원문 SHA256 `66d43e0fb476bb6e…`)와 실행 로그·요약.
- 제품 코드는 바꾸지 않았습니다(`llm_failover.py` `3c2dc21f…` 그대로).

## 분모

212는 그대로입니다(원문 3건은 212에 들어 있지 않았습니다). 이전 단일 965 = 958 통과 + 원문 상충 3 + bind 4에서 원문 3을 폐기하면 962 = 958 + bind 4(산술, 965 재실행 아님). 대체 3건은 이미 965에 포함돼 있었습니다.

## 원본 반영

[실측] 2026-10-25 21:34 `C:/_proj/final_workspace`에 시험 2개·evidence·보고·인계를 새 파일로 넣고 색인 5곳과 `llm-failover.md`는 끝에 덧붙였습니다. 반영 전 범위 1,460파일이 격리 사본과 같음(drift 0), 신규 경로 부재, 덧붙일 문서 6개가 사본 기준과 같음을 확인했고 문서 6개는 먼저 바이트 백업했습니다. git HEAD·index는 바뀌지 않았고 제품 코드는 건드리지 않았습니다. 반영 뒤 **원본 경로에서** 같은 선택을 다시 실행했습니다: 회귀 208/212(차단 4), 대체 시험 GREEN 3/3, 같은 시험 파일을 수정 전 코드 사본에 돌리면 RED 3/3. 되돌리기는 scratch `f3_probe_resolution_20261025/rollback_original.py`(현재 hash가 기록된 반영 후 hash일 때만 동작).

## 남은 한계

claim 뒤 늦게 시작하는 물리 전송·이미 시작한 I/O 취소·bool 예약 환불·엄격 금전 상한은 증명하지 않습니다. HTTP bind 4건은 계속 차단(미검증)입니다. DB·서비스·실모델·외부 API·push·배포는 하지 않았습니다. 후보 계열의 다른 F3 시험 파일(boundaries·review·scope)은 이 작업에서 원본에 들이지 않았습니다.
