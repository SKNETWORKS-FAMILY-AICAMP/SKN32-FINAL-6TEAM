# 혼합 대중교통 공개 골든 — 운임 일치와 실제 후보 누락 수정

강남 기준점에서 남산타워 기준점으로 가는 일반선 혼합 경로가 빠지는 원인을 수정했습니다. 이제 기존 빠른 신분당 경로와 함께 1,650원 일반선 대안이 실제 제품 후보에 나옵니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 선택 경로의 환승 운임 대조 | 웹 1,650/2,350/1,500원 일치 | 3/3 = 100% |
| 실제 혼합 경로 생성 | 수정 전 2개→수정 후 3개 | 3/3 = 100% |
| 현재 일정에서 최종 후보 제공 | 일반선·신분당 제공 | 2/3 = 66.7% |
| 남은 버스 환승의 제외 이유 | 공통 출발 시각에서 재판정 불성립 | 1/1 = 100% |
| 생성·운임·조조 회귀 시험 | 통과 | 58/58 = 100% |
| 상세 원문의 승차칸·출구 내부 계산 | 각각 1-1·6번 일치 | 각 1/1 = 100% |

분모3은 같은 공개 출발·도착 좌표1개에서 얻은 선택 경로3개입니다. 개발 표본이며 독립 검증·실제 결제·실제 도착 측정으로 부르지 않습니다. 위 표는 이 표본의 범위별 결과이며 21기능 전체 완료율이 아닙니다.

## 공개 관측과 계산 입력

원문은 [카카오 혼합 경로 골든](C:/Users/playdata2/Documents/final_workspace/datasets/mobility/raw/mobility_web21_20261012_v1/kakao-mixed-aligned-01.json)입니다. 관측 시각은2026-10-12 11:46:48 KST, 공개 출발 좌표37.4979,127.0276·도착37.5512,126.9882입니다. 상세 화면은 일반선 경로M01만 확보됐고 다른 경로의 출구·승차칸은 미관측입니다.

운임 재생은 실제 BusRoutes 정류장ID·방향·증가하는 순번·연속구간 거리와 제품 FareNet 거리 범위를 사용했습니다. 웹 운임과 웹 표시 총거리는 생성 입력으로 넣지 않았습니다. 성인1인1카드·승하차 태그·환승 시간 조건의 예상액이며, 실제 태그 결제 확정액 주장이 아닙니다.

| 경로 | 웹 운임 | 제품 지정경로 운임 | 수정 전 생성/제공 | 수정 후 생성/제공 |
|---|---:|---:|---|---|
| M01 2강남→교대·3교대→동대입구·01A→남산타워 | 1,650원 | 1,650원 | X/X | O/O |
| M02 신분당강남→신사·3신사→동대입구·01A→남산타워 | 2,350원 | 2,350원 | O/O | O/O |
| M03 420강남→국립극장·01A→남산타워 | 1,500원 | 1,500원 | O/X | O/X |

M01/M02는 실제 Planner 최종출력에서도 각각1,650/2,350원으로 확인했습니다. 실제 Planner 결과M01 44분·도보627m, M02 43분·도보629m는 관측 분+90분 도착 목표(13:16)의 일정 재생값입니다. 웹39/34분의 선택 편성·출발 조건과 같지 않으므로 시간 오차나 시간 정확도 통과로 세지 않습니다.

## 원인과 수정

기존 생성기는 각 버스 환승점마다 지하철 최단 경로 하나만 구체화했습니다. 강남→동대입구에서는 빠른 신분당 경로가 선택되면서 일반2호선→교대→3호선 대안이 운임 비교 전부터 없어졌습니다.

실제 최단 후보를 유지하고, 그 후보가 기존 운임 규칙의 추가운임 노선을 쓰는 경우 같은 버스·환승점에 추가운임 노선을 피한 최단 대안 하나를 생성하도록 바꿨습니다. 운임을 정답에 맞추거나 신분당선을 임의로 금지하지 않았습니다. 사고로 피해야 하는 노선, 환승상한, 기존 허용소요배수, 중복제거, 혼합 판정3개 상한을 유지했습니다. 철도를 먼저 타는 대안의 후속 버스 승차 예상창도 추가 철도 소요만큼 갱신합니다.

수정은 candidates.py와 plan.py 두 파일이며, 백업은 [수정 전 원본](C:/Users/playdata2/Documents/final_workspace/final_project_cs/_backup/2026-10-12_mixed_regular_v1/)입니다. 기존 시험의 생성기 mock 계약을 갱신했고 새 시험은 실제 작은 CandidateGraph에서 최단 유지·일반선 대안·운행중단 회피·시간상한·환승상한·정책 참조·중복·판정 개수·버스 승차창을 검증합니다.

## 버스 환승 후보가 최종 목록에서 빠진 이유

M03는 실제 후보 생성·판정까지 됐고12:03 출발이면51분으로 성립했습니다. 현재 일정의 공통 이동 출발12:09에서 다시 판정하면 성립하지 않아 earlier_departure로 제외됐습니다. 현재 계약은 후보별 별도 출발 칸 없이 같은 이동 항목의 출발 시각에 바꿔 탈 수 있는 후보만 싣습니다. 따라서 이 결과를 생성 실패나 M03 운임 실패로 세지 않았고, 통과처럼 숨기지도 않았습니다. 후보별 출발 계약을 임의로 바꾸지 않았습니다.

## 승차칸·출구와 확인 한계

M01의 실제 철도 구간 transfer_cars는 교대2호선→3호선1-1, 실제 동대입구→선택01A02222 접근의 OSM 최근접 출구는6번·직선67.52m로 상세 원문과 일치했습니다. 현재 혼합 최종 options에는 transfer_car가 들어가지 않습니다. 내부 도우미 일치를 고객 화면의 혼합 승차칸·출구 표시 완료로 세지 않습니다. 출구 개방·실보행도 확인하지 않았습니다.

mock 서버 시험: 이 혼합 과제에서는 하지 않았습니다. 실제 로컬 제품 함수·현재 적재 데이터 재생58/58 단위 회귀와 공개3경로를 확인했습니다.
실서버 확인(서버 응답): 안 했습니다. cs 프로젝트 서버HTTP 응답·운영 반영·실제 휴대폰 지도는 이번 혼합 과제의 확인 범위가 아닙니다.

## 재현과 보존

- [지정 경로 운임·실제 정류장 대조](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_web21_20261012/mixed-replay-v1/comparison-v1.json), [운임 재생 스크립트](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_web21_20261012/mixed-replay-v1/replay-v1.py), [운임 보고서](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_web21_20261012/mixed-replay-v1/REPORT-fare-v1.md).
- [수정 전 실제 Planner 완결 결과](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_web21_20261012/mixed-replay-v1/planner-comparison-v2.json).
- [최종 실제 Planner 결과](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_web21_20261012/mixed-replay-v1/planner-comparison-v4.json), [후보 체크포인트](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_web21_20261012/mixed-replay-v1/planner-generated-v4.json), [최종 재생 스크립트](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_web21_20261012/mixed-replay-v1/planner-replay-v4.py), [실행 로그](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_web21_20261012/mixed-replay-v1/planner-replay-v4.log).
- [58개 회귀 시험 로그](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_web21_20261012/mixed-replay-v1/mixed-unit-v3.log), [원문·코드·산출물 해시](C:/Users/playdata2/Documents/final_workspace/.tmp/mobility_web21_20261012/mixed-replay-v1/manifest-final-v2.json).

최초planner-comparison-v1.json은 디스크 공간 부족으로0바이트이며 해당 로그도 부분 결과입니다. 완결 결과로 세지 않고 그대로 보존했습니다. 새v2/v3/v4 이름을 사용해 덮어쓰지 않았습니다. 수정 전에 코드·기존 시험을 백업했습니다. 제한API 호출0회·개인 자료 접근0회·커밋/푸시/배포0회입니다.
