---
type: report
title: EKS 혼합 선택의 실제 후보 생성·상한·동률 원인 추적
status: draft
domain: travel
---

# 혼합 선택 후속

추가 해소0/5 = **0%**, PR110 **HOLD 유지**입니다. 원래 혼합 실패2/2 = 100%를 새 Linux에서 재현했습니다. 관련 기본층39/39 = 100%, 전체층6/8 = 75%·실패2/8 = 25%·skip0입니다. 이번에는 새벽 첫차와 golden 두 시험, 전체223개를 재실행하지 않았습니다. 제품 결함으로 확정할 근거 없이 경로 우선순위·탐색 상한·원래 단언을 바꾸지 않았습니다. 운영 reader fatal 원인도 여전히 미확정입니다.

## 범위와 보존

루트/cs AGENTS·cs RULE, 양쪽 wiki 색인, 개발 역할, Mobility 현행 안내·연결 계약, 데이터 REPORT, 지정 새벽 보고와 잔여5 인계·보고, 실제 coord EKS/Hspeed/precision 알림14개를 읽었습니다. 작성·자체 검증은 Codex이며 독립 검토 승인이나 통합 예약은 없습니다. coord 원문 해시는 [보존 검사](../evidence/2026-10-29_eks-mixed-selection-causality/final-preservation.json)에 있습니다. 알림 전송·외부 메시지 쓰기는 하지 않았습니다.

이전 Linux tip `ee8ca88070ac0b999750098b70ff7e3a825fd0f9`를 `/root/eksmix_selection_1029/candidate`로 새 no-hardlinks 복제했습니다. 공개 입력113/113 = 100% SHA256을 전후 확인했습니다. plan/candidates 및 원래 두 시험4/4 = 100% 바이트 일치, tracked diff0이며 golden3개 해시를 남겼습니다. 기존 사본·원자료·DB·임시 폴더는 보존했습니다. Linux ARM64/Python3.12.16이며 EKS AMD64 운영 검증은 아닙니다. 이전 mock 환경과 socket 연결 차단·접속 불가 DB를 유지했고 DB/리스너를 생성하지 않았습니다. 실제 실행 명령은 [기본층](../evidence/2026-10-29_eks-mixed-selection-causality/execution.json)·[전체층](../evidence/2026-10-29_eks-mixed-selection-causality/full-exit.json)에 있습니다.

## 실제 데이터에서 선택까지

원래 `test_full_earliest_uses_mixed_when_stations_blocked`의 좌표·사고(2호선/수인분당선 중단)·11:30 목표·앞 일정 끝10:45·party·버퍼·precision을 그대로 사용했습니다. 제품 함수를 교체하지 않고 Python return trace를 수집했습니다. [전체 생성/판정/선택 trace](../evidence/2026-10-29_eks-mixed-selection-causality/trace.json)에는 각 생성기의 반환, 버스 노선쌍별 최소 추정 후보 전체, materialize, regular_alternative, _mixed_one, 재검증, _choose_planned, 목표 생성, earliest와 최종 leg 반환43개가 있습니다. 함수 호출43개를 독립 표본43개로 세지 않습니다. [간추린 값](../evidence/2026-10-29_eks-mixed-selection-causality/summary.json).

| 단계 | 실제 값과 인과 |
|---|---|
| 버스+버스 생성 | 접근 반경·유형·순번·환승 거리·회귀 제한·구간 프로파일·운행 추정을 거쳐 노선쌍당 가장 짧은 추정 1개를 보존. 첫 호출209개 노선쌍 → 추정 정렬 상위6개. 목표 생성206개·후속 계획208개도 각각 상위6개. 이는 생성기 내부 제한을 통과한 노선쌍 수이며 현실 모든 경로의 분모가 아님 |
| A/B/C 합치기 | A0·B13·C6 = 19개. A/B/C 번갈아 배치한 뒤 운행 추정 안13개를 먼저 보고 밖6개를 별도 기록. 밖 후보6개는 불가 확정이 아님 |
| 처음 B | 어린이대공원→2016은 생성 추정52.2분. 실제 지하철 구간열을 채우면 9호선 석촌→고속터미널→7호선 어린이대공원으로89.1분. materialize 뒤 전체 후보를 다시 정렬하지 않음 |
| 상한 | B 어린이대공원, C303→2412, C320→2412 순서로 성립3개를 채움. `혼합_최대=3` 때문에 나머지 안쪽10개는 `mix_cap`; 판정 실패나 열위 확정이 아님. 판정수 상한과 별도로 보존수 상한에 먼저 닿음 |
| 빠진 B | 왕십리→2016은 원래 B 목록 index2·추정53.2분. 운행 안 목록 index3(0부터)이므로 첫3개 다음에 위치. 이전 인계에서 확인한 명시적 성립과 이번 최종 선택이 다른 직접 원인 |
| 원래11:30 | 보존 후보 장소 출발09:38·10:07·10:08. 앞 일정 끝10:45에서 재판정3개도 불성립하여 `arrive_late` |
| earliest 목표 | 제한된 source3개에서 목표725분=12:05 한 개가 나옴. 두 야간 source는 첫차 전이며 대기상한480분으로 별도 기록. 최종 leg 호출1회. 전 경로 최솟값 검증이 아님 |
| 12:05 재계획 | B 출발10:18/소요86분, C303과C320은 모두10:45/56분/환승1회. `_rank=(출발,-환승,-소요,-생성번호)`에 따라 생성번호301인303이302인320보다 먼저 선택 |
| 최종 결과 | 10:45 장소 출발·11:41 이동 끝·12:05 도착 목표,303→2412. 이 세 시각의 범위는 서로 다름. 원래 rail+bus 단언은 그대로 실패 |

선택된 실노선은303 ID `100100053`·seq35→37(잠실역.롯데월드몰→잠실대교전망쉼터),2412 ID `100100209`·seq58→67(잠실대교전망쉼터→경수중학교)입니다. ID·정류장 순번은 trace에서 실제 생성된 값을 보존했습니다. 실차 관측이나 첫차 관측으로 표시하지 않습니다.

## 사양과 수정 판단

[현재 Mobility 안내](../../../final_project_cs/wiki/teams/mobility.md)는 현재 계약과 시점별 기록을 구별하며, 후속 결정 없는 조항은 적용 범위를 확인하도록 합니다. [현행 MCP 이동 판정 계약](../../../final_project_cs/wiki/external/mcp-tools.md)의 출발시각 절은 판정기가 가장 늦게 떠나도 되는 후보를 고르고 제한 탐색이 가장 이른 출발을 보장하지 않음을 명시합니다. MCP의 +90/+180/+360 탐색과 이번 Planner.earliest의 알고리즘은 서로 다르므로 그 숫자를 이번 경로에 전용하지 않습니다. [10/11 계획 시험 기준](../../../final_project_cs/wiki/records/reports/2026-10-11_mobility.md#2026-10-11-계획-시험-기준-재검토-계약)은 실패 결과를 무조건 새 정답으로 복사하지 않고 엄격 전체 비교를 유지하도록 합니다. [기존 버스+버스 도입 기록](../../../final_project_cs/wiki/records/reports/2026-10-07_카카오맵_대조_14쌍.md)은 C모양의 존재 근거이며 오늘의 전체 품질 증거는 아닙니다.

현재 제품의 구체적인 상한·A/B/C 순서·동률 규칙은 해시를 고정한 candidates.py/plan.py 및 해당 시험에서 확인했습니다. wiki에서 **이 사고에서 반드시 rail+bus를 선택해야 한다거나 모든 경로의 전역 최적을 보장한다는 후속 확정 요구는 확보하지 못했습니다.** 코드 동작 자체를 사용자 승인 사양이라고 승격하지 않습니다. 이번에는 제한 탐색과 실제 동률 처리를 분리해 원인을 입증했으며, 정렬을 다시 하거나 상한을 올리는 개선의 수락 기준·연산 비용·기존 선택 보존 요구를 임의로 새 계약으로 만들지 않았습니다. 따라서 제품 수정0·원래 시험 수정0·golden 재생성/교체0·prefix/비교 범위/오차/precision/마커 변경0입니다. 실패를 green으로 만들지 않았습니다.

## 기준 시험과 변이

원래 두 파일의 기본층은39/39 = 100%, `-m mobility_full`을 명시한 별도 실행은6/8 = 75%·실패2/8 = 25%·skip0입니다. 기본 실행이 제외한8개를 통과로 세지 않습니다. [기본 XML](../evidence/2026-10-29_eks-mixed-selection-causality/baseline.xml)·[전체 XML](../evidence/2026-10-29_eks-mixed-selection-causality/full.xml). 두 실패는 기존과 동일한 혼합/역막힘 단언입니다. 새 실패0건이며 전체223개 비회귀를 주장하지 않습니다.

실제 선택 당시 eligible2개(303/320)를 그대로 사용해 별도 pytest에서 출발 내림차순·환승/소요/생성번호 오름차순의 독립 정렬로 대조했습니다. 기준1/1 = 100% 통과. 제품 `_rank`의 생성번호 부호만 메모리에서 뒤집으면320이 선택되어 같은 단언이 실패1/1 = 100%, 변이 검출1/1 = 100%입니다. [기준 XML](../evidence/2026-10-29_eks-mixed-selection-causality/rank-baseline.xml)·[변이 XML](../evidence/2026-10-29_eks-mixed-selection-causality/rank-mutant.xml)·[정확 명령](../evidence/2026-10-29_eks-mixed-selection-causality/control-exits.json)·[진단 시험](../evidence/2026-10-29_eks-mixed-selection-causality/test_rank_replay.py). 이는 실제 후보를 이용한 동률 규칙 검사이며, 전체 경로 최적성·실시간 데이터 정확도 검사는 아닙니다. 최초 harness의 여러 동률 축 반전 진단도 rank-controls.json에 그대로 남겼고, 별도 pytest는 생성번호 하나만 바꿉니다. 디스크 제품 소스는 변경하지 않았습니다.

## 남은 작업과 인계

잔여5/5 = **100% 미해결**을 유지합니다. 이번에는 혼합1건을 상세 추적했고 다른 혼합 실패는 원래 시험으로 재현만 했습니다. 다음 검토는 (1) 제한 탐색의 현재 수락 기준과 실제 materialize 후 재정렬 필요 여부, (2) 원래 rail+bus 단언을 정당화하는 확정 계약의 존재입니다. 이를 확정하기 전 단언 완화·C모양 차단·상한 변경을 하지 않습니다. 새벽 첫차는 방향/정류장별 자료가 없으므로 일정·도달시각을 만들지 않습니다. golden 두 건도 원래 입력·현재 무폴백 계약별 권위 기대 검토가 남아 있습니다.

모든 실행과 준비 도구는 `C:/_proj/eksmix_selection_1029`, Linux 사본은 `/root/eksmix_selection_1029`에 보존했습니다. [최종 해시/보존 검사](../evidence/2026-10-29_eks-mixed-selection-causality/final-preservation.json). 원본 Git 조회는 지정 safe_git.py로 시도했으나 WinError5로 실패했고 우회하지 않았습니다. PR110 원격 상태를 이번에 새 조회하지 않았으며 기존 HOLD를 해제하지 않았습니다. 운영 쓰기·운영 호출·모델 실호출·DB 생성·push/merge/배포·삭제0입니다. 제품 변경/통합이 없어 계약·보안·DoD 전체 관문은 실행하지 않았고 과거 통과를 이번 결과로 표시하지 않습니다.
