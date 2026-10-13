# 여행 HTTP 계산 관문 후속 보완

담당 Team을 꺼도 실행되던 식당 판정과 지도 경로 탐색을 차단했습니다. 저장된 일정 조회와 Dining을 쓰지 않는 Activity 장소 해결은 계속 동작합니다. 로컬 코드와 합성 시험 결과이며 운영 배포 완료를 뜻하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 기존 우회 HTTP 재현 | 확인 | 4/4 = 100% |
| 신규 HTTP·배선·독립 읽기 회귀 | 통과 | 24/24 = 100% |
| 관련 기존 접수·조립·일정 회귀 | 통과 | 97/97 = 100% |
| 읽기 도구의 unbound·False 포함 회귀 | 통과 | 61/61 = 100% |

시험 집합은 서로 겹치므로 위 행을 합산하여 고유 시험 수로 주장하지 않습니다.

## 실제로 확인한 우회와 결과

수정 전에는 Dining disabled와 not_installed 각각에서 `POST /v1/trips`가 실제 Dining SQL 구현을 실행하고 폐점 판정 422를 내렸습니다. Mobility도 두 상태 각각에서 등록된 여행의 route-shapes GET이 도로 그래프 탐색을 하고 200을 내렸습니다. 합성 인증·TripStore·SQL cursor·도로 Router 대역을 사용한 실제 FastAPI 처리기 호출입니다. 고객 DB와 외부 경로 API는 사용하지 않았습니다.

같은 재현을 보완 뒤 다시 실행하면 네 요청 모두 503·team_unavailable·원래 이유를 반환합니다. Dining의 연결/SQL은 실행 0회이고, Mobility는 소유권·저장 일정 읽기를 위해 연결을 열지만 그래프 탐색은 실행 0회입니다. [수정 전](../evidence/2026-10-11_1936_team_plugin_implementation/trip-api-disabled-repro-v1.log)과 [수정 후](../evidence/2026-10-11_1936_team_plugin_implementation/trip-api-disabled-after-v1.log)를 보존했습니다. [재현 스크립트](../evidence/2026-10-11_1936_team_plugin_implementation/trip-api-disabled-repro.py)는 두 결과에 같은 코드를 사용합니다.

## 구현 경계

Dining의 lookup_factory·slot_verdicts·planner_factory·link_core_place와 Mobility의 mobility_shapes.items/review를 조립 때 기존 함수·클래스 그대로 캡처합니다. 요청에서 Team 구현을 다시 import하지 않으며 현재 Registry의 필수 관문을 먼저 거칩니다. 구성의 기존 legs/dining_ledger 훅 선언은 유지하고 shapes는 Mobility에 부속된 계산 패밀리입니다.

Dining 이름 조회기는 처음 실제 조회할 때 생성합니다. Activity 소스로 이름이 해결되면 Dining 구현을 호출하지 않습니다. 이름 조회·방문구간 판정·경로선 계산 알고리즘을 새로 맞추지 않았습니다. `with_ledger`는 TeamUnavailable만 재발생시키며 일반 조회 오류의 기존 정책은 확장하지 않았습니다.

읽기 도구도 바인딩 없는 제품 경로에서 dining_ledger=False를 사용해 None 성공으로 넘어가지 못합니다. standalone을 명시한 기존 합성 재생 경계만 해당 설정을 허용합니다.

## 시험 근거와 한계

[HTTP 및 관련 회귀](../evidence/2026-10-11_1936_team_plugin_implementation/trip-api-gates-v2.log)는 121/121, 17.60초입니다. 신규 24건은 disabled/not_installed/load_failed × 식당 등록/등록 여행 경로선/접수 경로선 9건, 활성 기존 SQL·그래프 계산 3건, 저장된 일정 실제 GET 독립 읽기 2건, 제공자 인자 보존·실제 조립 캡처·unbound 및 예외 전파·지연 조회 경계를 포함합니다. 식당 정상 경로는 닫힌 가게를 원래 SQL 결과로 거절하는 422가 올바른 결과입니다. 등록 쓰기 성공이나 이동 정확도 측정으로 주장하지 않습니다.

[읽기 도구 후속 회귀](../evidence/2026-10-11_1936_team_plugin_implementation/dining-read-tool-gate-v3.log)는 61/61, 4.13초입니다. 중간 v2의 4개 실패는 unit harness가 standalone을 기본으로 켜는 조건을 제품 경계 시험에서 명시적으로 끄지 않은 시험 조건 문제였습니다. 로그를 삭제하지 않고 보존했습니다.

관련 7개 Python 파일 ruff와 변경 대상 diff 공백 검사는 통과했습니다. 저장소 전체 diff 검사는 다른 작업 파일의 기존 CRCRLF/끝 공백 때문에 실패하여 전체 통과로 보고하지 않습니다. 이 패치의 [소스 SHA256](../evidence/2026-10-11_1936_team_plugin_implementation/trip-api-gates-sha256-v2.json)을 보존했습니다.

실서버 확인(서버 응답): 이번 검증은 로컬 FastAPI 처리기의 합성 요청이며 x600 서버의 cs 프로젝트 서버 요청은 하지 않았습니다. 외부 경로 정확도·실제 고객 등록·운영 배포를 검증하지 않았습니다.

백업: [HTTP 패치 전 원본](../../../legacy/team_plugin_lifecycle/2026-10-11_2205_trip_api_gates/)과 [읽기 도구 후속 원본](../../../app/tools/_backup/2026-10-11_2200_unbound_read_tool_gate/). 커밋·푸시·배포는 하지 않았습니다.
