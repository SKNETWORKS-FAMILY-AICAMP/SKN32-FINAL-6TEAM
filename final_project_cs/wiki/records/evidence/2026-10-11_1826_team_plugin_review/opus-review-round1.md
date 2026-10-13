# triPilot Team 플러그인 수명 설계 독립 검토

요청대로 Read/Grep/Glob만 썼고 파일은 하나도 바꾸지 않았습니다. 그래서 plan 파일 작성과 계획 승인 요청도 하지 않았습니다. 아래에서 **[사실]**은 현재 작업 트리에서 확인한 코드이고, **[제안]**은 제 의견입니다. A2A 실행기(`a2a_executor.py`)는 읽지 않았습니다.

---

## 1. 방향 판단: 큰 방향은 동의, 세 군데는 수정이 필요합니다

**동의하는 부분**
- 꺼진 구현은 import하지 않고 메타데이터만 남기는 것.
- 실행 객체를 받는 관문을 하나로 만드는 것.
- 필수 코어 실패는 숨기지 않는 것.
- 같은 프로세스 안에서는 "논리적 격리"만 주장하고, 새 프로세스 인프라는 강제하지 않는 것.
- 의도적으로 끈 것과 결정 15의 데이터 장애를 구분하는 것.

이 다섯 가지는 코드 사실과 맞습니다.

**수정 ① 계산 서비스가 없을 때의 의미가 현행 계약과 충돌합니다**
- 초안 13줄("기존 처리 코드가 대신 성공시키지 않습니다")과 인수 시험 7번("필수 의존 요청 불가")이 문제입니다.
- [사실] 현행 규정은 반대입니다. hook이 등록돼 있지 않으면 부품이 원래 가지던 길로 갑니다.
  - `team_hooks/__init__.py:17-19`
  - `team_hooks/legs.py:10-11` (이동 → 직선거리 어림값)
  - `wiki/teams/composition.md:216-219`
  - `D-CS-013:105,110`
- [제안] 일괄로 "불가"라고 정하지 말고, hook 함수마다 둘 중 하나로 분류해 표로 확정해야 합니다.
  - **가용성 저하로 계속 진행**: 예) `legs.leg_planner`의 어림값
  - **해당 요청 불가**: 예) 꺼진 팀이 owner인 변경
- 이 표가 없으면 2단계(로더)와 4단계(조립 판)의 끝내는 조건을 판정할 수 없습니다.

**수정 ② "검사 + 실행 참조 획득 동기화"와 drain은 현재 구조에 비해 과설계입니다**
- [사실] 실행 중에 팀을 끄는 API가 없습니다.
  - `active`는 조립할 때 manifest 복사본에 고정됩니다(`composition.py:306`).
  - `TeamRegistry`에는 등록 후 바꾸는 API가 없습니다(`registry.py:31-131`).
- [사실] 실행 중 교체 경로는 관리용 빌드의 `/admin/reload` 하나뿐입니다. 고객 릴리즈 빌드에는 없습니다(`app/presentation/api/app.py:105-108`). 교체는 참조 하나를 바꾸는 방식입니다(`runtime.py:80-86`).
- 따라서 "검사 직후 꺼지는 경쟁"은 레지스트리 하나 안에서는 생길 수 없습니다. 실제로 생기는 일은 "옛 판을 잡은 요청이 swap 뒤에도 옛 팀으로 끝나는 것"뿐입니다.
- [제안] 잠금 대신 **"요청 시작 시 판 하나를 고정하고, 그 판으로 끝낸다"**를 계약으로 삼는 편이 맞습니다.
  - 릴리즈 빌드의 drain은 프로세스 정상 종료 문제입니다. 관리 빌드 reload에서만 의미가 있으니 인수 시험 9~11번은 후순위로 내릴 것을 권합니다.

**수정 ③ 여러 제공자 선택 규칙과 판 호환성 검사는 지금 필요 없습니다**
- [사실] hook은 모두 1:1입니다(`composition.py:510-539`).
- [사실] capability 중복은 이미 조립 단계에서 거부됩니다(`composition.py:308-314`).
- [제안] 초안 66줄의 "명시적 선택 규칙"과 74줄의 "재활성화 시 계약·버전 호환성 확인"은 "1:1만 허용하고 중복은 조립 실패"로 줄이는 것이 적절합니다.

**초안이 다루는 기존 규정 충돌 (초안도 일부 인지하고 있음)**
- "활성 구현을 import하지 못하면 빌드 실패" 규정과 부딪힙니다.
  - `composition.md:172`
  - `team-registry.md:75`
  - 결정 15에 따른 이동 자료 부재 시 기동 중지(`composition.py:293-296`)
- 초안의 "선택 인스턴스 로딩 실패 → unavailable" 방향은 이 규정을 바꾸는 변경입니다. 결정 15를 유지할지 먼저 정해야 합니다.

---

## 2. 위험 5개 (근거는 모두 [사실])

**1. 재개 경로에서 꺼진 owner가 그대로 실행되거나, 실패할 경우 토큰만 소비됩니다**
- 담당 팀이 바뀔 때만 active를 검사합니다(`controller.py:824-827`).
- 같은 owner로 재개하면 `VALID_INPUT`(토큰 사용 표시와 답변 저장)을 커밋합니다(`controller.py:793-838`).
- 그다음 `run_case` → `registry.get(owner)`로 가는데, 여기서 active 검사가 없습니다(`controller.py:333`).
- 지금은 꺼진 팀이 실행됩니다. 3번만 고치면 이번에는 토큰은 이미 소비됐는데 실행은 거부되는 상태가 생깁니다.
- 참고할 점: 담당이 바뀌는 경로는 트랜잭션 안에서 예외가 나면 롤백되어 토큰이 보존됩니다(`controller.py:803-827`). 이 방식을 일반화하면 됩니다.

**2. 채팅 변경 경로는 owner를 먼저 커밋한 뒤 실패합니다**
- `case_dispatch.py:85-90`이 `ROUTED{owner_team_id: team}`를 커밋한 다음에 Controller를 부릅니다.
- `run_case`의 A 트랜잭션 안에서 `get()`이 `RegistryError`를 던지면 `start_run`까지 롤백됩니다(`controller.py:295-333`).
- 결과: Case는 ROUTED 이후 상태로 owner만 지정된 채 남고, 실행 기록도 실패 이벤트도 없습니다.
- 덧붙여 capability가 `f"{team}.itinerary"`처럼 문자열 규칙으로 만들어지고 manifest와 대조되지 않습니다(`case_dispatch.py:88`).

**3. 운영 오류가 고객 입력 오류(422)로 표시됩니다**
- `RegistryError(ValueError)`(`registry.py:9`)가 `except ValueError → 422 invalid_customer_input`에 잡힙니다(`trip_api.py:1930-1931`).
- `ToolScopeViolation(ValueError)`(`executor.py:12`)도 같은 길로 422가 됩니다.
- `get()`과 `resolve()`가 모두 같은 예외 타입이라, "팀 없음 / 꺼짐 / 모호한 라우팅"을 구분할 수 없습니다.

**4. 조립이 꺼진 팀도 import하고, hook은 설정과 상관없이 전역으로 꽂힙니다**
- `build_registry`가 inactive 선언까지 `_import_ref`와 생성을 합니다(`composition.py:299-301`).
  - 오류 문구도 "active team ..."이라 실제 상태와 맞지 않습니다(`composition.py:156`).
- 선언 검증기는 inactive는 건너뛰지만 active는 미리 import합니다(`project_config.py:180-193`). 그래서 로더만 고쳐서는 활성 팀 로딩 실패를 격리할 수 없습니다(초안 지적이 맞음).
- `wire_domain_teams`는 세 팀 내부를 무조건 import하고 등록합니다(`composition.py:495-539`).
  - 운영 코드에서 `clear()`(`legs.py:35`, `watch_planners.py:26`)를 부르는 곳이 없습니다. 팀을 꺼도 그 팀의 계산은 계속 쓰입니다.
  - 등록 도중 import가 실패하면 `legs`만 바뀌고 나머지는 옛 상태로 남는, 부분 등록이 됩니다.
  - 호출 지점이 세 곳입니다: `composition.py:269`, `:381`, `:558`.

**5. 새 조립이 실패해도 그 전에 전역 hook이 바뀝니다**
- `build_controller`가 `wire_*`를 먼저 하고(`composition.py:380-381`), 그다음 레지스트리를 만듭니다(`:392`).
- reload가 실패하면 Controller는 옛 판을 유지하지만(`app.py:127-136`), hook은 이미 새로 실행된 뒤입니다.
- 정확히 말하면, 지금은 hook 내용이 설정과 무관해서 실제로 바뀌는 값은 없습니다. 하지만 4번을 고쳐 설정에 따라 hook을 꽂기 시작하는 순간 실제 오염이 됩니다.
- `ControllerProxy`는 속성에 접근할 때마다 판을 다시 읽습니다(`runtime.py:108-109`). 다만 trip_api는 `runtime.controller`를 요청당 한 번 잡으므로(`trip_api.py:1901-1903`) Controller 쪽은 판이 고정됩니다. hook만 고정되지 않습니다.

---

## 3. 최소 구현 순서 (전부 [제안])

1. **계약 문서 먼저 확정**
   - `composition.md:172`, `team-registry.md:75-85`, D-CS-013의 hook 미등록 표를 고칩니다.
   - hook 함수마다 "저하 / 불가"를 분류하고, 결정 15를 유지할 범위를 적습니다.
2. **실행 관문과 예외 타입 분리**
   - `TeamRegistry`에 실행 가능한 항목만 돌려주는 메서드(예: `runnable(team_id)`)를 둡니다.
   - 실패 예외는 `ValueError` 계열이 아닌 새 타입(예: `TeamUnavailable(RuntimeError)`)으로 합니다.
   - `get()`은 메타데이터 조회용으로 남깁니다.
   - 적용 지점: `executor.py:23`, `controller.py:166`, `:333`, `:438`, `:825`
3. **고객 상태를 바꾸기 전에 관문 통과**
   - `case_dispatch.execute`에서 ROUTED 커밋 전에 검사합니다.
   - `_resume`에서는 행 잠금 안, `VALID_INPUT` 전에 "최종 owner의 가용성"을 검사합니다. 이렇게 하면 실패해도 Case가 바뀌지 않고 토큰도 소비되지 않습니다.
4. **trip_api 응답 매핑**
   - `except ValueError`보다 앞에서 `TeamUnavailable`을 503으로 매핑합니다.
   - `ToolScopeViolation`은 500 계열 운영 오류로 분리합니다.
   - SSE와 MCP도 같은 함수를 타는지 확인합니다.
5. **로더 수정**
   - `build_registry`는 inactive 항목을 import하지 않습니다.
   - capability 중복 검사는 active 항목끼리만 합니다. inactive의 capability는 import 없이 알 수 없으므로, 필요하면 YAML에 선언해야 합니다.
   - 선택 팀 로딩 실패를 격리하는 작업은 1번의 결정 15 범위가 정해진 뒤에 합니다.
6. **hook 조립**
   - `wire_domain_teams(active_team_ids)`로 바꿔, 레지스트리 생성이 성공한 뒤 hook 묶음을 만듭니다.
   - 실제 꽂기(clear 후 일괄 등록)는 `runtime.swap` 직전 한 곳에서 합니다.
   - 요청 단위로 hook 판을 고정하는 것은 그다음 단계로 둡니다.

---

## 4. 인수 시험 보완

초안 16개에 추가하거나 구체화할 것:
- **같은 owner 재개 + 그 팀이 꺼짐**: 503, `resume_token_used`가 false로 남음, Case version 불변, 같은 답변을 다시 보내면 정상 처리. (기존 12번을 구체화)
- **채팅 변경 대상 팀이 꺼짐**: ROUTED 이벤트 0건, `agent_runs` 0건.
- **응답 코드 회귀**: `RegistryError`/`ToolScopeViolation`이 422로 나가는 회귀가 없어야 함.
- **import 여부**: inactive ref를 존재하지 않는 모듈로 둬도 기동되고, 해당 모듈이 `sys.modules`에 없어야 함.
- **hook 해제**: 팀을 끄면 해당 hook이 `is_registered()==False`이고, 부품은 계약표대로 저하 또는 불가로 동작.
- **hook 일괄성**: hook import가 일부 실패해도 부분 등록이 없음. reload 실패 시 hook 객체가 그대로(identity 불변).
- **추가 경로**: `build_mobility_departure_observer`와 감시 묶음(`watch_planners.planner()==None`)에서 팀이 꺼졌을 때 건너뛴 사실이 기록됨.
- **범위 조정**: 9~11번은 "관리 빌드 reload 한정"으로 범위를 명시.

---

## 5. 확정이 필요한 것

**계약**
- hook 함수별 저하/불가 표.
- 예외 계층: `RegistryError`가 `ValueError`를 상속하는 것을 유지할지. 기존 catch 지점을 grep으로 전수 확인한 뒤 정해야 합니다.
- 오류 코드 구분: `team_unavailable`과 `team_not_installed`를 공개 코드로 나눌지.
- 503에 `Retry-After`를 붙일지.
- capability 중복 검사 대상을 active로 한정할지.

**Case 상태**
- [제안] 새 상태는 추가하지 않습니다. 관문을 상태 변경보다 앞에 두면 "Case 불변 + 503"으로 충분합니다.
- 이미 RUNNABLE 상태인 Case의 owner가 꺼진 경우(예: 2번처럼 이미 지정된 경우)에 무엇을 할지는 정해야 합니다. `ROUTING_FAILED`로 escalated 처리하면 받는 운영자가 없다는 점(`controller.py:313-315` 주석)과 충돌하므로, 그대로 두고 재시도하는 쪽이 일관됩니다.

**토큰**
- 소비 시점을 "가용성 검사를 통과한 뒤의 `VALID_INPUT`"으로 못박습니다.
- 재활성화 후 재개는 같은 `request_id`의 멱등 처리(`resume_requests`)를 그대로 씁니다.
- 실행 중 timeout으로 종료된 실행은 지금처럼 GUARDRAIL_ESCALATED로 둘지, 재시도 가능으로 표시할지 정해야 합니다.
