---
type: report
title: Team 플러그인 수정의 운영 반영 사전 점검
status: preparation-only
domain: neutral
---

# Team 플러그인 수정의 운영 반영 사전 점검

현재 작업 트리 전체를 배포하면 팀 실행 수정과 무관한 DB 기능도 함께 들어갑니다. 기존 운영 코드의 검증된 사본에 필요한 수정만 반영한 후보를 만들고, 그 후보 이미지의 API와 일꾼을 함께 검증해야 합니다. 이번 조사에서는 원격 접속·이미지 빌드·DB 변경·배포·push를 수행하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 배포 단위·패키지·DB 의존 확인 | 끝 | 3/3 = 100% |
| 최소 확인·복구 절차 준비 | 끝 | 2/2 = 100% |
| 반영 후보 이미지 빌드·기동 | 미실행 | 0/1 = 0% |
| 반영 후보 인수 확인 | 미실행 | 0/8 = 0% |

분모 3은 포장 단위·패키지/설정·DB 의존 조사입니다. 분모 2는 확인 절차와 복구 절차 작성입니다. 분모 8은 아래 표의 후보 인수 항목이며, 기존 개발 폴더 시험 통과를 후보 이미지 시험으로 세지 않습니다.

## 실제 배포 단위

| 근거 | 확인한 동작 | 반영 준비에 미치는 영향 |
|---|---|---|
| [API Dockerfile](../../../deploy/Dockerfile.api) | Python 3.12에서 requirements를 설치하고 app·config·prompts·scripts 전체를 복사합니다. tests·wiki·legacy는 이미지에 들어가지 않습니다. | 현재 작업 트리를 그대로 빌드하면 다른 작업도 들어갑니다. 단일 파일 복사만으로 설치 완료를 선언할 수도 없습니다. |
| [Compose](../../../deploy/docker-compose.yml) | `tripilot-api`와 `tripilot-worker`가 같은 API 이미지를 사용합니다. worker는 별도 시작 명령을 쓰며 자체 healthcheck가 꺼져 있습니다. | API와 worker를 동일 후보로 확인해야 합니다. API의 health 200만으로 worker 정상 실행을 판단하지 않습니다. |
| [일꾼 시작 스크립트](../../../deploy/worker.sh) | 감시 작업·바깥함 배달·일일 작업을 반복 실행합니다. 실패를 기록하고 다음 회차를 계속합니다. | 실행 중이라는 사실과 회차 성공을 구분합니다. 실제 배달이 가능한 운영 환경에서 확인용으로 한 회차를 임의 실행하지 않습니다. |
| [자동 배포 스크립트](../../../deploy/auto_deploy.sh) | 선택 소스를 가져와 전체 이미지 빌드·전체 활성 SQL 실행·Compose 기동·태그 정리를 합니다. 실패 시 이전 이미지/Compose로 되돌리지만 DB는 되돌리지 않습니다. | 이번 제한 반영의 확인 명령으로 실행하면 안 됩니다. 이후 승인된 수동 반영과 자동 반영이 서로 덮어쓰지 않도록 운영 절차를 먼저 맞춰야 합니다. |
| [관리 이미지](../../../deploy/Dockerfile.admin) | API 이미지에서 파생된 별도 이미지입니다. | 관리 앱까지 실제 운영 중이면 별도 확인이 필요합니다. 고객 API 이미지 교체가 관리 앱 교체를 뜻하지 않습니다. |

웹 이미지와 DB 컨테이너의 교체는 이번 플러그인 수정 자체의 필수 배포 단위로 확인되지 않았습니다. 다만 실제 운영 Compose·이미지·설정의 기준 사본을 확보하기 전에는 교체 대상을 확정하지 않습니다. 전체 `compose up` 대신 필요한 서비스만 지정하는 절차를 후보 검증 뒤 정해야 합니다.

## 파일 묶음과 설치 가능 범위

아래는 의존성을 검토할 파일 묶음입니다. **운영 기준 소스와 대조해 확정한 반영 목록이 아닙니다.** 현재 `git diff`에는 다른 작업자의 수정도 있으므로 그 전체를 이번 변경이라고 부르지 않습니다. 최초 백업인 [수명 관리 작업 백업](../../../legacy/team_plugin_lifecycle/2026-10-11_1936/) 역시 작업 전 로컬 상태이며 운영 원본을 증명하지 않습니다.

| 묶음 | 주요 파일 | 함께 확인할 인터페이스 |
|---|---|---|
| 새 중립 모듈 | [service_bindings.py](../../../app/core/service_bindings.py), [team_availability.py](../../../app/core/team_availability.py) | 요청별 조립 판 고정, 실행 불가 오류와 응답 정보 생성. 두 파일이 후보 이미지에 실제 포함돼야 합니다. |
| 조립·실행·상태 | [composition.py](../../../app/composition.py), [runtime.py](../../../app/application/runtime.py), [controller.py](../../../app/application/controller.py), [registry.py](../../../app/core/registry.py), [project_config.py](../../../app/core/project_config.py), [이벤트 전이](../../../app/core/case_lifecycle/events.py) | 기존 Case 서비스·저장소·계약 모델과 함수 인자/상태 전이가 맞는지 운영 기준 코드에서 확인합니다. |
| 고객 요청·오류 | [API 구성](../../../app/presentation/api/app.py), [Case API](../../../app/presentation/api/cases.py), [오류 변환](../../../app/presentation/errors.py), [여행 API](../../../app/domains/travel_ops/entry/trip_api.py), [Case 전달](../../../app/domains/travel_ops/components/conversation/case_dispatch.py), [SSE 실행](../../../app/domains/travel_ops/modules/live_progress/op_stream.py), [MCP](../../../app/domains/travel_ops/modules/mcp/mcp_server.py) | 답변 본문 전달, 입력 저장 전 관문, HTTP 503, 스트림 실패, MCP 실패를 각각 확인합니다. |
| 여행 계산·읽기·감시 연결 | [Team 계산 연결](../../../app/domains/travel_ops/components/team_hooks/), [여행 도메인 입구](../../../app/domains/travel_ops/__init__.py), [이동 판단](../../../app/domains/travel_ops/components/itinerary/move_judge.py), [영업시간 확인](../../../app/domains/travel_ops/components/intake/hours.py), [접수 검토](../../../app/domains/travel_ops/components/intake/review.py), [식당 조회](../../../app/domains/travel_ops/instances/dining/ledger.py), [여행 감시](../../../app/domains/travel_ops/components/watch/), [일꾼](../../../scripts/run_sweepers.py) | 꺼진 Team 구현을 import하지 않는지, 독립 읽기가 동작하는지, 누락 계산을 성공으로 위장하지 않는지 확인합니다. 식당 조회가 쓰는 기존 DB 함수도 대조합니다. |
| 원격 실행 | [A2A 실행기](../../../app/core/remote_team/a2a_executor.py), [원격 실행 입구](../../../app/core/remote_team/executor.py), [HTTP 전송](../../../app/infrastructure/a2a/http_transport.py), [원격 여행 에이전트](../../../app/presentation/a2a/travel_remote_agent.py) | 원격 실패 재시도와 마감 후 취소 예산. 실제 사용하는 실행 방식이 로컬인지 원격인지 먼저 확인합니다. |
| 설정·관찰 | [project.yaml](../../../config/project.yaml), [guardrails.yaml](../../../config/guardrails.yaml), [실행 구성 조회](../../../app/introspection/contract.py) | 옛 YAML의 새 로더 호환, 새 YAML의 옛 로더 비호환 가능성, 실행 판과 저장된 판 구분. |

플러그인 수명 관리에 새 제삼자 Python 패키지를 추가하는 의존성은 위 모듈에서 확인되지 않았습니다. 새 중립 모듈은 표준 라이브러리와 기존 Core를 사용합니다. 그러나 [requirements.txt](../../../requirements.txt)의 설치 성공·전이 의존성 충돌 여부는 **후보 이미지에서 `pip check`와 실제 import로 다시 확인해야 합니다.** 원격 설치 패키지가 같다는 구두 전달만으로 후보 빌드 통과라고 기록하지 않습니다.

운영 기준 사본에서 먼저 파일별 해시·함수 인자·계약 버전을 비교해야 합니다. 그 뒤 필요한 변경 구간과 새 모듈만 적용해 의존성 폐쇄 목록을 만들고, 후보 소스와 이미지의 불변 식별자를 기록합니다. 폴더 전체 복사 또는 더티 작업 트리의 파일 전체 교체를 최소 반영이라고 부르지 않습니다.

## 스키마 229는 별도 기능의 의존성입니다

[229 SQL](../../../app/infrastructure/db/migrations/229_service_improvement.sql)은 서비스 개선용 합성데이터의 생성 예산·검토 묶음 표와 예산 초기화 방지 트리거를 추가합니다. 플러그인의 실행 가능 관문과 조립 판 기록 자체에는 새 DB 열/표를 추가하지 않습니다.

하지만 현재 소스의 [일꾼](../../../scripts/run_sweepers.py)은 정리 회차에서 [서비스 개선 데이터 정리](../../../app/domains/travel_ops/components/customer/service_improvement.py)를 무조건 호출합니다. [동의 처리](../../../app/domains/travel_ops/components/customer/consents.py)의 철회 경로도 대기 묶음 정리를 호출합니다. 이 파일들을 통째로 가져오면 229 표가 실제 의존성이 됩니다.

| 반영 방식 | 필요한 조치 |
|---|---|
| 운영 기준 사본에 플러그인 수정만 반영 | 다른 기능의 일꾼·동의 변경을 섞지 않은 후보를 먼저 만듭니다. 해당 후보에서 229 의존이 발생하지 않는지 확인합니다. |
| 현행 일꾼·동의·서비스 개선 기능도 포함 | 범위를 별도 명시하고 229 및 해당 기능을 함께 검증합니다. 이를 플러그인 수정만의 반영으로 보고하지 않습니다. |

[migrate.py](../../../app/infrastructure/db/migrate.py)는 [migration-plan](../../../app/infrastructure/db/migrations/migration-plan.json)의 과거 보존 제외 SQL을 뺀 **활성 SQL 전체를 한 트랜잭션으로 실행**합니다. `python -m app.infrastructure.db.migrate`는 229만 적용하는 명령이 아닙니다. 이번 범위에서 운영 DB에 실행하면 안 됩니다.

[로컬 229 적용 근거](../evidence/2026-10-11_1936_team_plugin_implementation/local-db-schema-after-229.json)는 로컬 개발 DB 확인입니다. 이 근거로 x600 서버의 cs 프로젝트 DB에 229가 적용됐다고 판단하지 않습니다. 되돌릴 때 예산 표를 지워 초기화하거나 합성데이터를 임의 파기하는 절차도 포함하지 않습니다.

## 설정 호환과 시작 조건

- 새 `TeamConfig`의 `required`·`capabilities`·`hooks`는 기본값이 있어 옛 선언을 읽을 수 있습니다. 반대로 새 선언을 옛 코드에 먼저 주면 엄격한 필드 검증에 걸릴 수 있습니다. **이전 이미지와 이전 설정을 한 묶음으로 보존**해야 합니다.
- A2A 정리 예산은 `reliability.a2a_cancel_timeout_seconds`와 `reliability.team_cleanup_grace_seconds`를 읽습니다. 새 실행기에 옛 guardrails만 주지 않습니다. YAML 전체를 교체하지 말고 기준 설정에 필요한 항목만 명시적으로 반영합니다.
- 이번 플러그인 수정만을 위해 새 환경변수가 필요하다는 근거는 찾지 못했습니다. 기존 환경 파일의 이름·주입 순서·자료 마운트와 실제 활성 실행 방식은 후보 환경에서 검증합니다. 비밀 값은 보고서·빌드 로그에 출력하지 않습니다.
- 현행 고객 API의 `/health`는 정적 응답이며 `/ready`는 정의돼 있지 않습니다. `/ready` 404를 기동 결함으로 세거나 `/health` 200을 Team·DB 준비 완료로 해석하지 않습니다.
- 고객 API의 관리 재조립 경로는 기본으로 노출되지 않습니다. 관리 앱의 재조립 확인과 고객 API 컨테이너 교체를 같은 것으로 취급하지 않습니다.
- `/introspection`은 권한이 필요한 실제 실행 구성 조회 경로입니다. 실행 중 프로세스의 `active_revision`과 저장된 `desired_revision`을 구분합니다. 별도 Python 프로세스에서 앱을 import한 결과를 기존 uvicorn 프로세스의 실행 판이라고 기록하지 않습니다.

## 반영 전에 확보할 기준 사본

1. 실제 API·worker의 불변 이미지 ID/가능하면 digest, 이미지 생성 정보, 현재 서비스별 이미지 일치 여부를 저장합니다. `local` 같은 가변 태그만으로 이전 이미지를 식별하지 않습니다.
2. 사용 중인 Compose·Dockerfile·프로젝트 선언·guardrails의 내용과 해시를 비공개 작업 영역에 보존합니다. 비밀 환경 파일은 내용을 보고서에 옮기지 않고 안전한 백업 위치와 복구 담당을 별도로 관리합니다.
3. 실제 이미지 안의 관련 소스 해시 또는 검증된 동일 소스 사본을 얻습니다. 저장소 HEAD만으로 실행 이미지의 소스를 대신하지 않습니다. 후보 파일 목록에 변경 이유·기준 해시·후보 해시·의존 파일을 연결합니다.
4. DB 스키마와 기존 식당 조회 함수, 이동 자료 마운트, 실제 모델 설정의 준비 여부를 읽기 전용으로 확인합니다. 미설정 모델을 이번 플러그인 수정으로 해결됐다고 보고하지 않습니다.
5. 자동 배포의 다음 실행이 후보/롤백을 덮어쓰지 않게 운영 일정을 조정합니다. 이 문서를 작성하면서 자동 작업을 끄거나 변경하지 않았습니다.

## 최소 후보 확인: 아직 실행하지 않았습니다

아래 8개가 이 보고서의 후보 인수 분모입니다. 먼저 운영 자료를 사용하지 않는 격리 환경에서 수행합니다. DB를 쓰는 항목은 복원된 시험 DB와 시험용 고객/일정을 사용하고 외부 알림·예약·결제 전송을 막습니다.

| 항목 | 실행·관찰 대상 | 통과 기준 |
|---|---|---|
| 1. 이미지 설치 | 후보 이미지의 `pip check`, 새 모듈 import, Python 버전 | 의존성 충돌 없이 새 파일이 실제 이미지 안에서 읽힙니다. |
| 2. 설정·조립 | 실제 반영할 YAML로 후보 API 시작, 권한 있는 구성 조회 | 시작 성공. 활성/목표 판과 선언 Team이 기대값과 일치합니다. |
| 3. 꺼진 담당의 독립성 | 격리 설정에서 담당 하나만 비활성, 독립 담당과 읽기 경로 호출 | 해당 업무만 거절되고 독립 읽기/업무는 동작합니다. 전원 비활성 시 구현 import 0도 확인합니다. |
| 4. 답변·재활성 | 답변 대기 → 담당 비활성 → 같은 답변 → 재활성 → 재전송 | 비활성 시 토큰·답변·run 보존. 이후 실제 일정은 정확히 한 번 변경됩니다. |
| 5. 전달 채널 | JSON API·SSE·MCP에 같은 실행 불가 조건 | HTTP 503/실패 프레임/도구 실패가 계약대로 나가며 완료 성공으로 끝나지 않습니다. |
| 6. 교체·원격 실패 | 실행 중 조립 교체, 원격 poll 정지/느린 cancel | 옛 요청은 옛 판으로 종료. 새 요청은 새 판 사용. 원격 취소가 예산 안에서 실행되고 동일 event 재시도가 막히지 않습니다. |
| 7. 일꾼 | 후보 이미지에서 감시 한 회차와 시험용 바깥함 배달 | fatal/누락 함수/누락 표 오류가 없고 비활성 담당 업무가 실행되지 않습니다. 실제 고객 알림은 발송하지 않습니다. |
| 8. 복구 예행 | 이전 이미지·이전 설정으로 격리 환경 복구 | API·worker 모두 이전 판으로 돌아오고 기존 읽기/업무가 동작합니다. DB 추가가 있다면 옛 코드 호환까지 확인합니다. |

다음은 1번의 **향후 후보 확인 명령 예시**입니다. `$CANDIDATE_IMAGE`에는 검증한 후보 이미지 ID 또는 digest를 넣습니다. 현재 실행하지 않았으며 원격 명령도 아닙니다.

```powershell
docker image inspect $CANDIDATE_IMAGE --format '{{.Id}}'
docker run --rm --network none --entrypoint python $CANDIDATE_IMAGE -m pip check
docker run --rm --network none --entrypoint python $CANDIDATE_IMAGE -c "import sys; import app.core.service_bindings; import app.core.team_availability; print(sys.version); print('plugin modules import OK')"
```

정적 YAML 확인은 `config_from_declaration`과 `Guardrails`를 사용하되, 앱 기동·DB 준비·실행 중 프로세스 확인과 구분합니다. 실제 기동은 격리 DB·필요 자료를 붙인 후보 환경에서 기존 환경 주입 방식으로 수행합니다. 이미지에 시험 파일이 없으므로 별도 읽기 전용 시험 묶음을 마운트하거나 검증용 이미지를 준비해야 합니다. 로컬 소스를 import한 시험 결과를 후보 이미지 시험으로 대신하지 않습니다.

후보의 핵심 회귀 범위는 [Controller 시험](../../../tests/integration/controller/test_plugin_unavailable.py), [조립 판 시험](../../../tests/unit/test_plugin_composition_runtime.py), [읽기 경계 시험](../../../tests/unit/travel/test_plugin_read_boundaries.py)입니다. DB fixture와 의존 시험 설정도 같은 검증 묶음에 넣습니다. 특히 `test_reactivation_same_reply_changes_real_itinerary_only_once`, `test_inflight_disable_keeps_old_team_and_applies_real_itinerary_once`, `test_controller_remote_deadline_leaves_budget_for_cancel_and_original_failure`를 포함합니다.

승인된 운영 교체 뒤에는 추가 쓰기 시험 대신 API/worker 이미지 ID, API 재시작 횟수·health, 권한 있는 구성 조회, 본인 여행 읽기, worker 회차 로그와 `controller_call_finished`의 실제 판을 확인합니다. worker가 단순히 running인지만 보지 않습니다. 이 운영 확인도 아직 수행하지 않았습니다.

## 복구 경로

이전 API 이미지·worker 이미지·Compose·프로젝트 선언·guardrails를 같은 검증 묶음으로 보존합니다. 자동 정리로 이전 이미지가 없어지지 않게 불변 ID와 보존 정책을 확인합니다. 반영 실패 시 승인된 절차로 API·worker를 이전 묶음으로 교체하며, 새 YAML만 남겨 옛 코드가 읽게 하지 않습니다. 웹 이미지·이동 자료·DB까지 불필요하게 바꾸는 전체 기동 명령은 복구 절차로 쓰지 않습니다.

229 등 추가 스키마를 포함했다면 이미지 복구가 DB 복구를 뜻하지 않습니다. 이 SQL은 추가 표/트리거 중심이지만 옛 코드 호환은 격리 환경에서 확인해야 합니다. 표 삭제·예산 초기화·고객 데이터 되감기는 이 플러그인 복구 범위가 아닙니다. DB 복구가 필요하면 별도 백업과 변경 범위를 확정해야 합니다.

## 현재 확인된 근거와 남은 관문

- 부모 작업에서 저장한 [기존 x600 서비스 응답](../evidence/2026-10-11_1936_team_plugin_implementation/deployed-x600-health-v2.json)과 [별도 기존 서비스 응답](../evidence/2026-10-11_1936_team_plugin_implementation/deployed-arm-health-v2.json)은 각각 `/health` 200, `/ready` 404입니다. 정상 응답 확인 2/2이며 새 수정의 운영 반영 근거는 아닙니다.
- 기존 원격 모듈·자료 폴더·모델 설정의 점검은 부모의 이전 도구 출력 전달로만 알고 있습니다. 이 보고서는 이를 새 JSON에서 재검증한 것처럼 기록하지 않습니다. 필요한 항목은 읽기 전용 확인과 실제 근거 저장이 남았습니다.
- [개발 인수 매핑](../evidence/2026-10-11_1936_team_plugin_implementation/acceptance-mapping.json)과 [개발 검증 보고](2026-10-11_2135_controller_acceptance_a2a_deadline.md)는 현행 로컬 소스의 증거입니다. 후보 이미지·운영 코드 기준 사본·운영 DB 상태의 증거를 대신하지 않습니다.

운영 기준 사본과 확정 후보 목록이 아직 연결되지 않았으므로 **설치 가능 목록 확정·후보 빌드 통과·운영 반영 준비 완료를 선언하지 않습니다.** 다음 단계는 기준 사본 확보 → 제한 후보 작성 → 위 8개 후보 확인입니다. 실제 운영 반영은 이 결과와 복구 묶음을 검토한 뒤 별도 승인 범위에서 진행합니다.

링크 경로를 바로잡기 전 작성본은 [작성본 백업](_backup/2026-10-11_2144_preflight_links/2026-10-11_2143_plugin_deployment_preflight.md)에 보존했습니다.
