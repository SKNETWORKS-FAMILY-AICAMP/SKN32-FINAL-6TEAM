---
type: report
title: EKS 새벽 첫 차량 판정의 실행 인과와 원자료 한계
status: draft
domain: travel
---

# 새벽 첫 차량 판정 후속

추가 해소0/5 = **0%**, PR110 **HOLD 유지**입니다. 이번 선택 범위는 새벽 첫 차량 한 건입니다. 새 Linux 원래 시험은 실패1/1 = 100%, 같은 첫차 시험군은 통과2/3 = 66.67%·실패1/3 = 33.33%·skip0입니다. 나머지4개 및 전체223개는 이번에 재실행하지 않았습니다. 운영 reader fatal 원인은 미확정이며 이 이동 실패를 운영 fatal의 원인으로 연결하지 않습니다.

## 범위와 보존

루트/cs AGENTS, cs RULE, 양쪽 wiki 색인, 개발 역할, Mobility 계약, 데이터 REPORT와 지정 인계·보고서를 읽었습니다. 실제 coord는 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_coord`입니다. EKS/Linux/precision/Hspeed/R/V 알림14개를 확인했습니다([읽은 원문 해시](../evidence/2026-10-29_eks-dawn-first-vehicle-causality/coord-read.json)). 작성·자체 검토는 Codex이며 독립 검토 승인·통합 예약은 없습니다.

이전 Linux tip `ee8ca88070ac0b999750098b70ff7e3a825fd0f9`를 `/root/eksdawn_causality_1029/candidate`로 새 no-hardlinks 복제했습니다. 원래 공개 입력113/113 = 100% SHA256 일치를 실행 전후 확인했습니다. 제품 verify_time/plan 및 원래 시험3/3 = 100% 바이트 보존, tracked diff0입니다. Linux ARM64·Python3.12 실행이며 EKS AMD64 운영 재현은 아닙니다. mock 모델·DB 연결 차단·기존 offline guard를 유지했습니다. 원본 제품·시험·golden 수정0, 삭제0, DB/리스너 생성0, push/merge/배포/운영 호출0입니다.

## 실제 인과

기존 기대는 장소05:23 출발·지하철이며, 원래 시험은 이번에도 장소03:49 출발 → 버스710/301 →05:16 종료·05:36 목표를 반환해 실패했습니다. [원래 실행 명령·환경](../evidence/2026-10-29_eks-dawn-first-vehicle-causality/execution.json) · [원래 XML](../evidence/2026-10-29_eks-dawn-first-vehicle-causality/original.xml) · [같은 시험군 XML](../evidence/2026-10-29_eks-dawn-first-vehicle-causality/wait-family.xml).

제품 함수를 바꾸지 않고 Python 실행 추적으로 실제 `verify_leg_bus`와 `_bus_board`의 입력·반환을 수집했습니다. 710번 노선ID `100100110`, 경복궁 정류소ID `100000022`·seq20 → 연지공원 seq25가 실제 선택됩니다.

| 단계 | 실제 값과 원인 |
|---|---|
| 장소 출발/정류장 입력 | 03:49에서 접근 후 `now_min=240`(04:00). 04:00은 실제 차량 승차시각이 아님 |
| 첫차 비교 | `r.first_min=230`(03:50)보다 요청240이 늦으므로 `before_first` 분기를 지나감. 승차 seq20까지 첫 차량 도달 검사는 없음 |
| 배차 대기 | 원문 배차9분. best는 ceil(9/2)=5분, worst는9분 |
| `_bus_board` | 모델 승차245/249가 기점 막차1360 이하라 그대로 반환. 이 함수는 막차 상한이며 첫차 하한을 계산하지 않음 |
| 실제 판정 | holiday best04:05 승차·04:13 도착, worst04:09 승차·04:19 도착으로 `feasible/추정`. `observed=None`: 현재 차량 관측에 근거한 결과가 아님 |
| 후속 계획 | 이 추정 판정을 사용하여710→301과05:36 목표를 산출. OS/시간표 정밀도만으로 생긴 차이라고 닫을 수 없음 |

[전체 함수 반환 trace](../evidence/2026-10-29_eks-dawn-first-vehicle-causality/trace.json) · [간추린 원값](../evidence/2026-10-29_eks-dawn-first-vehicle-causality/summary.json). trace의 반복 호출을 독립 표본 수로 세지 않았습니다.

같은 원본 노선에서 승차 정류장만 seq1/seq20으로 바꾸어 첫차-1분·첫차·첫차+10분, best/worst 총12회 직접 판정했습니다. 두 정류장 모두03:49는 before_first,03:50는03:55/03:59 승차 가능,04:00는04:05/04:09 승차 가능으로 같습니다. **첫차 경계가 승차 정류장 도달이 아니라 노선 기점 시각에만 의존함을 실행으로 확인**했습니다. 이12개는 진단 호출이며 통과한 수락 시험으로 세지 않습니다. [원래 ID를 유지한 직접 진단](../evidence/2026-10-29_eks-dawn-first-vehicle-causality/probes.json).

## 원자료로 확정 가능한 것과 수정하지 않은 이유

원래 TOPIS 공개 노선 행은 첫차03:50·막차22:40·배차9분, source `seoul_bus_route@2026-09-10`입니다. 정류장 행에는 위치·순번·구간 거리만 있고 해당 정류장 첫 차량 출발시각은 없습니다. 원문 노선의 `st_station_nm`은 **상암차고지**인데 정류장 목록 seq1 이름은 **월드컵파크7단지**입니다. 이전 보고의12,048m는 목록 seq1→seq20 구간합입니다. 이를 상암차고지 실제 출발부터의 정확한 거리로 단정하지 않습니다. 이전 기록은 보존하고 이 후속 정정으로 연결합니다. [원문 행·파일 해시](../evidence/2026-10-29_eks-dawn-first-vehicle-causality/source.json).

기존 [독립 분위수 누적](2026-10-29_eks-linux-remaining5-investigation.md)의 holiday p90 04:26.44는 통계 모델입니다. p10/p50은 필요한 셀이 결측입니다. p90을 최소 도달시각 또는 실제 첫차 시간표로 바꾸면 통계의 뜻이 달라집니다. 경복궁04:05/04:09 승차가 현실에서 절대 불가능하다는 관측 증명도 확보하지 않았습니다. 확인한 결함 경계는 **그 승차 가능성을 정류장 첫차 근거로 검증하지 않는 것**입니다.

따라서 원래05:23 지하철 기대를 옳다고 확정하거나,03:50에 구간 p90을 더한 값으로 제품 첫차를 강제하거나, 버스를 끄지 않았습니다. 전 노선·하루 전체를 일괄 unknown 처리하는 정책도 신설하지 않았습니다. 정류장/방향별 첫 차량 근거 또는 허용된 추정 방식과 근거 결측 시 미확인 처리 범위를 먼저 확정해야 수정이 정당화됩니다. 기존 지하철 시간표를 버스 정답으로 대체할 수 없습니다. golden 재생성·기대/오차/마커/비교 범위 변경·하드코딩 폴백0입니다.

## 남은 작업과 운영 경계

5/5 = **100% 미해결** 상태를 유지합니다. 다음 작업은 정류장 첫 차량 자료의 존재·방향/기점 대응 검증과 결측 처리 계약입니다. 혼합 선택2개·golden2개는 기존 인계를 유지합니다. 제품/시험을 수정하지 않았으므로 이번에 계약·보안·DoD 전체 관문을 실행하지 않았고, 이전 결과를 새 통과로 표시하지 않습니다. Linux 보존 사본과 진단 도구는 `C:/_proj/eksdawn_causality_1029`, 실제 Linux 사본은 `/root/eksdawn_causality_1029`에 남겼습니다.

원본 Git 조회는 지정 `python tools/safe_git.py status --short --untracked-files=no`로 시도했지만 Windows Git 실행 WinError5로 실패했습니다. 이를 우회하여 원본 Git을 실행하지 않았습니다. 격리 Linux의 tracked diff0만 확인했습니다. PR110 현재 원격 상태를 새로 확인한 결과는 없으며 **기존 HOLD를 해제하는 조치는 하지 않았습니다**. 운영 reader 이유 로그와 운영 수락이 확보되기 전까지 production fatal을 미해결로 둡니다.
