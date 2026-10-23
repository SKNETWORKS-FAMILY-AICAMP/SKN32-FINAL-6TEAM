---
type: report
title: 운영 API 기준 사본 확보와 제한 반영의 실제 선행 의존
status: baseline-collected
domain: neutral
---

# 운영 API 기준 사본 확보와 제한 반영의 실제 선행 의존

기존 x600 서버의 cs 프로젝트 API에서 허용된 코드·설정 404개 파일을 읽기 전용으로 보존했고, 모든 복사본의 SHA256이 원본과 일치했습니다. 실제 운영 코드에는 앞서 구현한 대화 재개 연결도 아직 없으므로, 플러그인 수정 파일만 단순 교체하는 반영은 성립하지 않습니다. 기준 사본 위에 필요한 선행 수정과 플러그인 변경 구간을 함께 적용한 후보를 별도로 검증해야 합니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| API 이미지·앱 위치 확인 | 끝 | 1/1 = 100% |
| 허용 파일 복사·해시 확인 | 끝 | 404/404 = 100% |
| 의존 파일의 기준 사본 대조 | 끝 | 52/52 = 100% |
| 반영 후보 작성·설치 시험 | 미실행 | 0/1 = 0% |

분모 404는 운영 컨테이너에서 복사한 허용 파일 수입니다. 분모 52는 이번 의존 조사에서 선택한 경로 수이며, 최종 배포 파일 수나 전체 변경 파일 수가 아닙니다. 바이트 단위로 4개는 현행과 같고 48개는 다르거나 운영에 없었습니다. 줄바꿈을 정규화하면 6개가 같으며, 그중 2개는 줄바꿈만 다릅니다. 이 차이를 모두 이번 플러그인 작업의 변경이라고 간주하지 않습니다.

## 수집 범위와 보존 위치

- [운영 기준 사본](../../../legacy/deployment_baselines/2026-10-11_214932/)에 앱의 `.py`·`.sql`·`.json`·`.md`·`.txt` 파일과 지정된 프로젝트 YAML·guardrails YAML·requirements·일꾼 코드를 보존했습니다. 캐시·환경 파일은 제외했습니다.
- [원본 해시와 수집 기록](../../../legacy/deployment_baselines/2026-10-11_214932/baseline-manifest.json)에 404개 SHA256, 이미지 ID, 관련 패키지 버전과 Team의 비밀이 아닌 필드를 기록했습니다. 수집 완료 시각은 2026-10-11 21:49:42 KST입니다.
- [52개 경로의 대조 근거](../evidence/2026-10-11_1936_team_plugin_implementation/deployed-source-baseline-comparison-v2.json)는 각 운영 원본·현행 파일의 SHA256과 동일 여부를 기록합니다. 기준 사본의 추가 조사 JSON은 복사한 운영 파일을 수정하지 않고 별도 파일로 만들었습니다.

원격 컨테이너의 실제 작업 폴더는 `/srv`입니다. 먼저 확인한 `/app`은 존재하지 않았습니다. `/srv/app`, 지정 설정 두 개, requirements, 일꾼 파일의 존재를 확인한 뒤 메모리 tar를 stdout으로 받아 로컬에서 검증·해제했습니다. 운영 파일·임시 파일을 만들거나 수정하지 않았습니다. 환경변수 원값·환경 파일·SSH 설정·주소·DB 내용은 복사하거나 출력하지 않았습니다.

확인한 API 이미지 ID는 `sha256:1f1c6850f3570dc8694629e2a4cab7c36c7e86097a5e1b8b54a736a25a7ea294`입니다. 이번 수집은 API 컨테이너 기준이며, 실제 worker의 이미지 ID 일치 여부와 운영 Compose 사본은 아직 별도 확인이 필요합니다.

## 설치 의존에서 확인한 사실

| 대상 | 운영 기준과의 대조 |
|---|---|
| [requirements](../../../requirements.txt) | 전체 파일이 동일합니다. 새 패키지 설치 요구를 추가하는 차이는 없습니다. 후보의 `pip check`·실제 import 확인은 아직 수행하지 않았습니다. |
| [Core 계약](../../../app/core/contracts.py), [DB 저장소](../../../app/infrastructure/db/repository.py) | Core 계약은 바이트까지 동일하고 DB 저장소는 줄바꿈만 다르며 본문은 동일합니다. 이 두 파일을 통째로 새것으로 바꾸는 선행 의존은 확인되지 않았습니다. |
| 설치 패키지 | 운영에서 FastAPI 0.116.1, Pydantic 2.13.4, psycopg 3.3.4, HTTPX 0.28.1, PyYAML 6.0.2, uvicorn 0.35.0, Starlette 0.47.3을 직접 읽었습니다. 이 버전 목록만으로 후보 조립/기동 성공을 보장하지 않습니다. |
| Team 선언 | 6개 Team 모두 active=true입니다. 지정된 6개 선언에는 required 필드가 없었습니다. 새 로더에서 생략하면 기본 required=true가 되므로, 선택 Team 실패를 허용하려면 required 정책을 별도로 명시해야 합니다. |

## 실제로 필요한 선행 파일

다음 의존은 운영 기준 소스를 직접 대조해 확인했습니다. 개별 수정 구간을 기준 사본에 적용해야 하며, 현행 파일 전체를 가져오는 최종 목록으로 사용하지 않습니다.

| 막힌 지점 | 운영에 확인된 상태 | 필요한 준비 |
|---|---|---|
| 새 실행 가능 관문·요청 판 고정 | [team_availability.py](../../../app/core/team_availability.py)와 [service_bindings.py](../../../app/core/service_bindings.py)가 운영에 없습니다. | 두 중립 모듈과 이를 호출하는 Registry·조립·runtime·Controller·API 연결을 함께 반영 후보에 넣어야 합니다. |
| 고객 답변의 검증·재개 | 운영 [case_service.py](../../../legacy/deployment_baselines/2026-10-11_214932/app/application/case_service.py)에 `ResumeTokenExpired`·`ResumeRequestConflict`·`validate_customer_input`이 없습니다. 현행 Controller가 이를 직접 사용합니다. | 플러그인 관문뿐 아니라 앞서 수행한 답변 재개 관련 CaseService 변경도 필수 선행 묶음입니다. 단순 Controller 교체는 import 단계부터 실패합니다. |
| 대화 업무를 Team으로 전달 | [case_dispatch.py](../../../app/domains/travel_ops/components/conversation/case_dispatch.py)가 운영에 없습니다. | 새 전달 모듈과 실제 요청 경로의 연결 구간을 함께 준비해야 합니다. 이전 직접 계산 경로와 새 Team 실행 경로가 혼합되지 않게 확인합니다. |
| Team의 되묻기·답변 해석 | [conversation_work.py](../../../app/domains/travel_ops/instances/_shared/conversation_work.py)가 운영에 없습니다. [공통 일정 업무](../../../app/domains/travel_ops/instances/_shared/itinerary_team.py), [Dining](../../../app/domains/travel_ops/instances/dining/team.py), [Mobility](../../../app/domains/travel_ops/instances/mobility/team.py)의 추가 연결도 운영과 다릅니다. | `conversation` 요청과 분 수 없는 지연 요청을 답변 대기로 연결하는 선행 변경을 포함합니다. 이는 새 관문만 넣어도 자동으로 생기는 동작이 아닙니다. |
| 구현 없는 담당을 분류할 메타데이터 | [core_hooks/routing.py](../../../app/domains/travel_ops/components/core_hooks/routing.py)가 운영에 없습니다. | 구현을 import하지 않고 알려진 담당 관계를 선언하는 작은 메타데이터 파일도 새 조립 코드와 함께 필요합니다. |
| 재시도 상태 전이·오류 채널 | 현행 [상태 전이](../../../app/core/case_lifecycle/events.py)와 HTTP·SSE·MCP 연결이 운영과 다릅니다. | 원격 실패 후 같은 event 재시도와 고객 답변 보존의 후속 계약을 후보에서도 같은 시험으로 검증합니다. |

[Activity Team](../../../app/domains/travel_ops/instances/activity/team.py) 자체와 [Team 계산 연결 입구](../../../app/domains/travel_ops/components/team_hooks/__init__.py)는 현행과 운영 기준이 동일합니다. 다만 공통 일정 업무와 개별 계산 연결 파일은 다르므로 이 사실로 Activity의 모든 의존이 같다고 확대하지 않습니다.

## 통째로 가져오면 다른 기능을 끌고 오는 파일

| 현행 파일 | 운영 기준에 없는 추가 의존 | 제한 반영에서의 처리 |
|---|---|---|
| [composition.py](../../../app/composition.py) | 출발 재검증 모듈과 simulation 연결이 새로 들어 있습니다. | 플러그인 조립·관문 구간만 분리 적용합니다. 출발 재검증까지 함께 반영할 계획이면 이동 모듈의 독립 의존 검증을 별도로 수행합니다. |
| [run_sweepers.py](../../../scripts/run_sweepers.py) | [watch/monitoring.py](../../../app/domains/travel_ops/components/watch/monitoring.py), [customer/service_improvement.py](../../../app/domains/travel_ops/components/customer/service_improvement.py)가 운영에 없습니다. | 비활성 Team 감시를 건너뛰고 요청 판을 고정하는 변경 구간만 옮기는 후보가 필요합니다. 파일 전체 교체는 범위를 넓힙니다. |
| 감시 실행 기록 | monitoring은 `travel_watch_runs`·`travel_watch_checks`를 INSERT/UPDATE합니다. [228 SQL](../../../app/infrastructure/db/migrations/228_watch_run_history.sql)은 운영 기준 사본에 없습니다. | 코드 사본에 SQL이 없다는 사실과 실제 운영 DB에 표가 없다는 판단은 구분합니다. 이번 작업은 DB를 조회하지 않았습니다. 기능을 포함할 때만 별도 읽기 스키마 확인·DB 변경 검토가 필요합니다. |
| 서비스 개선 묶음 정리 | service_improvement는 [229 SQL](../../../app/infrastructure/db/migrations/229_service_improvement.sql)의 표에 의존합니다. 운영 기준 사본에는 이 기능 코드가 없습니다. | 이 기능을 제외한 제한 후보에서는 229를 끌고 오지 않습니다. 현재 일꾼을 통째로 쓰려면 별도 기능 범위와 스키마 확인이 필요합니다. |
| [trip_watch_cases.py](../../../app/domains/travel_ops/components/watch/trip_watch_cases.py), [trip_reminders.py](../../../app/domains/travel_ops/components/watch/trip_reminders.py), [itinerary_changes.py](../../../app/domains/travel_ops/components/itinerary/itinerary_changes.py), [legs.py](../../../app/domains/travel_ops/components/team_hooks/legs.py) | 출발 관측·승차 안내·재계산 관련 추가 변경이 섞여 있습니다. | 요청 판 고정/담당 관문을 위한 변경과 이동 기능 변경을 구간별로 구분해야 합니다. |

따라서 현재 배포 준비의 장애는 패키지 설치 목록이 아니라 **운영에 아직 없는 대화 선행 변경과 다른 기능이 섞인 파일의 변경 구간 분리**입니다. 현행 전체 app·config·scripts를 복사해 빌드하거나, 위 파일 이름만으로 현행 파일 전체를 교체하면 제한 반영 조건을 충족하지 못합니다.

## 다음 후보 작성·검증 범위

1. 보존한 운영 사본을 원본으로 유지하고 별도의 후보 디렉터리를 만듭니다. 이번 작업은 원본 사본만 확보했으며 후보를 작성하지 않았습니다.
2. 답변 전달/재개 선행 변경과 플러그인 생명주기 변경을 구간별로 적용하고, 새 모듈을 포함한 최종 해시 목록을 만듭니다. 228·229·출발 재검증·simulation의 추가 의존을 무조건 가져오지 않습니다.
3. 설정은 필요한 Team required 정책과 A2A 정리 예산 키를 명시해 코드와 묶습니다. 롤백할 이전 설정도 운영 기준 사본에서 함께 보존합니다.
4. [사전 점검 보고서의 8개 후보 인수 항목](2026-10-11_2143_plugin_deployment_preflight.md)을 후보 이미지와 격리 DB에서 실행합니다. 그 뒤 실제 worker 이미지·운영 Compose·복구 묶음을 확인해야 운영 반영 판단이 가능합니다.

이번 읽기 조사에서 변경·재시작·배포·DB 조회/쓰기·외부 메시지·push는 수행하지 않았습니다. 기존 서비스가 응답한다는 근거와 새 후보의 실제 동작 검증은 계속 구분합니다.

줄바꿈 차이 표기를 보완하기 전 작성본은 [작성본 백업](_backup/2026-10-11_2158_baseline_equality/2026-10-11_2155_plugin_operating_baseline.md)에 보존했습니다.
