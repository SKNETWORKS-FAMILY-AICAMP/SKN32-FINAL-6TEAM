---
type: contract
title: Team 실행 가용성·조립 판 계약
status: draft
domain: neutral
---

# Team 실행 가용성·조립 판 계약

접수 단계의 식당 영업시간 판정도 Dining 필수 계산입니다. 장소 행이 있는 경우와 관광 콘텐츠 번호·이름만 있는 경우 모두 같은 실행 관문을 사용하며, 후자는 `dining_ledger.catalog_state` hook으로 Team의 원장 구현에 위임합니다. 꺼진 Team을 우회하는 직접 원장 SQL을 컴포넌트에 두지 않습니다. 독립적인 기존 계획서 읽기와 새 영업시간 판정은 구분합니다.

이동 판정의 JSON·MCP 읽기 도구도 필수 계산을 수행합니다. `TeamUnavailable`을 일반 `engine_error`와 직선거리 어림값으로 바꾸지 않으며 동일한 503·이유를 유지합니다. 그 밖의 실행 오류도 조립 판 안에서는 필수 엔진 불가로 명시하고 추정 성공을 발행하지 않습니다.

2026-10-11 구현 착수 계약. [수명 관리 계획](../team-plugin-lifecycle.md)의 구현 경계입니다. 아직 구현·운영 완료를 주장하지 않습니다.

`TeamUnavailable(RuntimeError)`은 `team_id`, `reason`과 외부 코드 `team_unavailable`을 가지며 고객 입력 오류와 구분합니다. disabled, not_installed, load_failed, remote_unavailable을 이유로 구분합니다. HTTP는 503이고 SSE·MCP도 실패로 표현합니다. ToolScopeViolation은 ValueError에서 분리합니다.

Registry의 `get`은 메타데이터 조회로 남기고 `require_runnable(team_id, capability=None)`이 실행 객체 획득 관문입니다. 비활성·부재·선택 로딩 실패는 이 관문에서 거절합니다. `declare_unavailable(team_id, reason)`으로 구현을 import하지 않고 상태를 등록합니다. manifest 계약 major와 capability 소유를 검사하고 중복 제공은 거절합니다.

선언의 TeamConfig에 `required: bool = True`, `capabilities: list[str] | None = None`, `hooks: list[str] | None = None`을 호환 필드로 추가합니다. 미지정은 기존 선언을 유지합니다. 명시적 capability와 실제 manifest가 다르면 조립 오류입니다. 비활성 구현을 import하지 않으며 선택 로딩 실패는 등록표에 이유를 남깁니다. 정적 검증은 구현 import를 하지 않습니다. TeamTask/TeamResult 전송 필드는 이 변경에서 바꾸지 않습니다.

Controller는 task 생성 전 관문을 사용합니다. 담당 지정 ROUTED와 재개 토큰·답변·VALID_INPUT 반영 전에도 같은 판에서 확인합니다. 거절된 업무 상태·답변·토큰은 보존하고 운영 원인은 별도 로그에 남깁니다. Local/A2A 모두 관문을 거치며 A2A 결과의 team_id/task_id/run_id를 대조합니다. 원격 unavailable을 ESCALATE 성공으로 바꾸지 않습니다.

조립 판은 Registry·Executor·계산 연결·Controller·revision을 함께 고정합니다. 요청/백그라운드 회차는 시작 시 고정하고 종료까지 유지합니다. 새 판 준비는 게시된 계산 표와 전역 엔진 상태를 바꾸지 않으며 실패한 판을 게시하지 않습니다. 기존 판 요청은 끝까지 실행하고 새 판 이후 요청에 비활성 정책을 적용합니다. 꺼진 Team의 필수 계산을 직선거리 어림값·모름·빈 사고 목록으로 대신 성공시키지 않습니다.

## 실행 경계 보완 (2026-10-11)

- `required`는 active인 구현을 적재할 때만 적용합니다. inactive이면 required여도 import하지 않습니다. 선택 팀은 코드·훅 제공자 적재 실패를 `load_failed`로 격리합니다. 계약 불일치·중복 capability는 선택 여부와 관계없이 후보 오류입니다.
- 업무를 시작하기 전에 확인 가능한 불가(disabled/not_installed/load_failed)는 재개 입력·토큰을 소비하지 않습니다. 원격 실행 시작 후 연결이 끊긴 경우에는 실패를 감사 기록에 남기고 동일 요청의 재시도를 허용합니다. 이미 적용한 변경의 멱등성은 기존 Core 계약을 따릅니다.
- 필수 이동 계산에서 활성 Team의 엔진이 준비되지 않았으면 `team_unavailable`, `reason=engine_unavailable`로 실패합니다. 직선거리 추정으로 성공하지 않습니다. disabled와 다른 원인입니다.
- HTTP·SSE·MCP의 Team 불가 코드는 `team_unavailable`입니다. retryable은 remote_unavailable만 true입니다. 의도적으로 꺼진 기능은 반복 전송으로 해결된다고 안내하지 않습니다.
- 조립 판의 감사 위치는 운영 로그의 `composition_revision`입니다. 고객 데이터나 접속 정보는 넣지 않습니다. 작업 중 판을 바꿔 기록하지 않습니다.
- 이동 엔진 자료·경유 설정은 프로세스 수명 동안 고정합니다. 설정 변경은 재기동이 필요하며 hot reload 후보가 전역 엔진을 다시 초기화하지 않습니다. Team 활성/비활성 교체는 별도로 지원합니다.
- 문자열 A2A endpoint는 조립 때 주입한 신뢰된 resolver의 기존 계약을 유지합니다. endpoint가 신원 메타데이터를 포함하면 대조하고, 결과의 team/task/run 식별자는 항상 필수 대조합니다. 모르는 완료 상태는 성공으로 받지 않습니다.
- 새 Case 접수의 201은 업무 완료를 뜻하지 않습니다. 실행 불가 결과는 별도 상태 조회에서 원인을 확인할 수 있어야 합니다. 동기 재개와 웹 변경 요청의 불가는 503 또는 SSE error로 끝납니다.

재개 구현 순서는 기존 owner 관문 → prospective resuming 상태로 읽기 전용 route 선택 → 최종 owner/capability 관문 → resume_prepare 후보 확보 → VALID_INPUT입니다. resume_route는 저장을 하지 않습니다. 동일 event가 이미 입력 반영됐고 Case가 running이며 활성 run이 없으면, VALID_INPUT·토큰 소비를 반복하지 않고 run_case를 다시 시도합니다. 이미 완료된 요청은 기존 멱등 응답을 유지합니다.

새 Case는 분류 뒤 실행 관문에서 알려진 불가를 확인하면 503과 case_id를 반환합니다. 접수 자체가 보존되어도 완료로 표시하지 않습니다. 같은 요청의 재전송은 아직 agent run이 없는 routing 업무를 다시 실행할 수 있습니다.


## A2A 전송 메타데이터와 결과 식별자

HTTP 제출 어댑터는 요청의 `task_id`, `run_id`, `team_id`를 원격에 전달하고 원격 artifact는 세 값을 그대로 돌려줍니다. 이는 TeamTask/TeamResult 스키마 변경이 아니라 기존 식별자 검사의 전송 배선입니다. 원격 상태 조회용 id는 별도로 유지할 수 있지만 업무 결과 id를 대신하지 않습니다. 완료·대기 artifact의 식별자 누락·불일치는 거절하며, 결과에 요청 id를 임의 채워 넣지 않습니다. capability resolver는 조립 판에 고정된 신뢰 경계이며 기존 문자열 endpoint 형식을 유지합니다. 원격 unavailable은 일반 전송 실패와 구분합니다.

취소는 best effort이며 `reliability.a2a_cancel_timeout_seconds` 안에서 끝납니다. 취소 시간 초과·실패는 고객 입력을 포함하지 않는 운영 로그에 예외 종류와 요청 실행 식별자를 남기며 원래의 deadline 실패 결과를 보존합니다. 기본 1초는 외부 SLA 실측이 아닌 구현 운영 한도입니다.


## A2A 동기 호출과 제한시간 (2026-10-11)

capability resolver의 동기 구현은 외부 제출·상태 변경이 없는 순수 조회에 한해 `asyncio.to_thread`로 실행합니다. 현재 요청의 ContextVar 조립 판을 전달하며, 반환값이 awaitable이면 요청의 이벤트 루프에서 이어서 기다립니다. resolver의 기한이 지나면 결과를 버리고 원격 제출은 하지 않습니다. Python은 이미 실행 중인 thread를 강제로 취소하지 못하므로 resolver가 기한 뒤에도 끝날 수 있으며 순수 조회라는 전제가 필요합니다. 비동기 resolver도 지원합니다.

transport의 submit/send, poll/get_status, cancel은 존재하는 메서드마다 async 함수여야 합니다. 제출 전 계약을 확인하며 동기 제출 구현은 실행 0회로 거절합니다. 동기 factory가 awaitable을 돌려주는 방식도 transport에서는 허용하지 않습니다. 명시적인 async 어댑터가 필요하며 그 어댑터 안에서 동기 I/O로 이벤트 루프를 막아서는 안 됩니다. cancel이 없는 구현의 취소는 실패로 추정하지 않고 best effort 미지원으로 구분합니다. 취소 지원 시 기존 취소 유예시간을 적용합니다. 동기 제출을 thread로 옮겨 기한 뒤 늦은 POST를 만드는 방식은 사용하지 않습니다.

## 실행 마감과 정리 예산 (2026-10-11)

실행기가 task의 deadline을 스스로 집행하고 기한 뒤 취소 정리가 필요하면 선택 속성 `cleanup_budget_seconds`로 유한한 0 이상 정리 예산을 알립니다. A2A 실행기는 기존 `reliability.a2a_cancel_timeout_seconds`를 이 값으로 제공합니다. 이 속성이 없는 실행기는 기존 Controller의 Team 실행 제한시간을 유지합니다. TeamExecutorPort의 기존 `execute` 구현은 그대로 호환됩니다.

Controller는 이 속성을 제공하는 실행기에 대해 `task.deadline_at까지 남은 시간 + cleanup_budget_seconds + reliability.team_cleanup_grace_seconds`를 바깥 제한시간으로 사용합니다. 정리 구간의 실행기 마감이 Controller에 먼저 취소되는 경합을 방지합니다. grace 기본 0.1초는 이벤트 루프의 정리·실패 결과 반환을 위한 운영 정책값이며 외부 SLA 실측이 아닙니다. 업무 실행 자체의 deadline은 늘리지 않습니다. 음수·무한대·NaN 예산은 계약 오류로 거절합니다. 검토 담당 Team 실행에도 같은 계산을 적용합니다.

취소가 끝나거나 취소 자체가 제한시간을 넘기더라도 기존 `remote_deadline_exceeded` 원인을 Core가 기록합니다. 취소 실패 로그는 별도로 보존합니다. 외부 호출자가 명시적으로 요청을 취소한 경우의 CancelledError 전파는 변경하지 않습니다.

## 백그라운드 회차 실패 격리 (2026-10-11)

회차의 조립 실패는 의도적인 Team 비활성과 구분해 fatal로 기록합니다. 실패한 판을 게시하거나 전역 계산으로 대신 실행하지 않으며, 그 회차의 Team 의존 작업은 실행하지 않습니다. 분류 되잡기·회원 정리·끝난 여행의 외부 값 정리 등 독립 작업은 계속 수행합니다. 재난 안전 점검도 기존 감시 주기 문 안에서 독립적으로 수행합니다. 성공한 회차는 기존처럼 하나의 Controller·등록표·계산 표를 종료까지 고정합니다.

작업 하나의 일반 예외는 작업 이름·예외 종류와 실패 건수로 관찰하고 다음 독립 작업을 진행합니다. 상주 실행은 회차 예외를 기록한 뒤 다음 회차를 시도하며, 단발 실행은 실패 종료 코드를 반환합니다. KeyboardInterrupt·SystemExit 같은 명시적 종료 신호는 가로채지 않습니다. 예외 메시지에 포함될 수 있는 고객 입력·접속 정보는 새 실패 로그에 싣지 않습니다.

`composition_failure`는 Team 조립 실패이며, 기능 배선이 성공하면 재난 점검을 기존 주기 안에서 독립 수행합니다. `features_failure`는 선택 기능을 연결하는 초기화 실패로 별도 fatal을 남깁니다. 이 초기화에는 게스트 여행 제외 같은 필수 감시 범위 연결도 포함되므로, 실패 위치를 확인하지 못한 상태에서는 Team 작업·출발 안내·재난 점검을 실행하지 않습니다. 연결 누락을 「모든 여행 감시」로 바꾸지 않습니다. 분류·회원 정리·끝난 여행의 외부 값 정리 등 해당 범위 연결을 요구하지 않는 작업은 계속합니다. 두 실패가 함께 나면 두 원인을 각각 기록합니다.


## 미분류와 알려진 담당 부재의 구분 (2026-10-11)

아직 담당 종류를 정하지 못한 입력은 실행 불가 플러그인과 구분합니다. 제공자 0개라는 이유만으로 모든 분류를 `TeamUnavailable`로 바꾸지 않습니다. 알려진 담당 관계가 없는 종류와 빈 종류는 기존 `RegistryError`로 남기며 Controller의 한 번 재배분 또는 routing_failed 경로를 유지합니다.

도메인은 구현을 import하지 않는 순수 라우팅 메타데이터를 조립에 제공합니다. Registry의 중립 `declare_case_types(team_id, case_types)`는 그 관계만 보관합니다. 실제 제공자가 없는 종류에 알려진 담당이 정확히 하나 있으면 실행 관문으로 부재·비활성·적재 실패를 확인하여 `TeamUnavailable`을 냅니다. 중복 담당은 `RegistryError`이며 코어에 제품 Team 이름 목록을 넣지 않습니다. 기존 활성 manifest가 받아들이는 종류의 정상 해결은 그대로 유지합니다.


## 읽기 도구의 필수 계산 경계 (2026-10-11)

`read.dining_state`와 `read.dining_states`도 담당 Team의 필수 계산입니다. 다른 Team이 허용된 도구로 호출해도 고정된 조립 판의 Dining 실행 관문과 해당 계산 제공자를 먼저 확인하며, 거절 시 DB 연결을 열거나 구현을 import하지 않습니다. `dining_ledger=False` 시험 설정도 바인딩된 제품 판에서 비활성·부재 담당을 우회하지 못합니다. 바인딩 밖의 기존 합성 재생 사용은 명시적인 standalone 경계로 한정하며 이 설정을 제품 계산 성공 근거로 쓰지 않습니다.
