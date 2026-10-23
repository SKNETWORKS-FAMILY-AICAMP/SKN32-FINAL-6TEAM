# triPilot 팀 플러그인 수명 설계 2차 검토 (Codex 반론 A~E)

파일은 하나도 바꾸지 않았고 Read/Grep/Glob만 썼습니다. 그래서 plan 파일도 쓰지 않았습니다. **[사실]**은 지금 작업 트리에서 확인한 코드이고, **[제안]**은 제 의견입니다. 제품 구현이 통과했다는 주장은 하지 않습니다.

1차와 달리 이번에는 사용자 요구("팀이 없으면 그 업무는 안 돌고, 독립 서비스는 유지")를 기존 규정보다 우선합니다. 그래서 1차 수정 ①("저하로 계속"을 기본 분류로 둔 것)과 1차 6단계("clear 후 일괄 등록을 swap 직전에")는 철회합니다.

---

## 1. A~E 판정

| 안 | 판정 | 근거와 보완 |
|---|---|---|
| **A** 요청마다 불변 판 하나 고정 | **동의, 판의 범위를 넓혀서** | [사실] 지금 `swap`은 Controller 참조 하나만 바꿉니다(`app/application/runtime.py:80-85`). hook은 이 판 밖에 있습니다. [제안] 판에 Controller, Registry, TeamExecutor, hook 표, capability→endpoint 표, revision을 함께 넣습니다. 참조 카운트는 쓰지 않고, 옛 판은 GC가 거둡니다. 두 가지는 분명히 적어야 합니다. ① "검사 직후 경쟁이 없어진다"는 **프로세스 안의 조립 상태**에만 해당합니다. 원격 A2A 팀 쪽 상태, 요청마다 DB에서 읽는 값(`web_guard.values`), 이동 엔진 설정(`mobility_wiring.configure`)은 판이 고정하지 않습니다. ② 옛 판으로 끝난 요청은 꺼진 팀의 결과를 쓸 수 있습니다. 그래서 `agent_runs`와 이벤트에 판 revision을 남겨 감사할 수 있게 합니다. |
| **B** clear+전역 교체로는 원자성이 없음 | **동의** | 근거는 아래 4가지 [사실]입니다. 단, 잠금을 "새 판 포인터 게시"로만 줄이는 것은 **조립이 전역 상태를 전혀 건드리지 않을 때만** 맞습니다. |
| **C** hook별 계약표, 꺼진 팀 업무를 어림값으로 성공시키지 않음 | **동의. 단, 기존 규정을 명시적으로 폐기해야 함** | [사실] 지금 규정은 정반대입니다. 미등록이면 어림값으로 갑니다(`composition.py:492-493`, `team_hooks/legs.py:10-11,54`). 사용자 요구가 우선이므로 D-CS-013, `composition.md:216-219`, `team_hooks/__init__.py:17-19`를 고친다고 문서에 적어야 합니다. 상태는 세 가지로 나눕니다. ① 팀 disabled/absent: 판에 hook이 없고, 그 팀에 필수 의존하는 요청은 unavailable. ② 팀은 enabled인데 엔진만 off: 지금은 hook 람다가 호출할 때 모듈 상태를 읽고(`composition.py:508-514`) 같은 `None`(어림값)이 됩니다. ③ 선택 hook 없음(유사도): "없음"을 표시하고 계속. 지금은 ①과 ②가 `legs.leg_planner()==None` 하나로 섞여 구분되지 않습니다. 이것을 분리하는 것이 C의 핵심 구현점입니다. |
| **D** 선택 팀만 격리, 결정 15와 fail-fast 유지 | **동의, 보완 하나** | [사실] 꺼진 팀의 capability와 hook 제공 여부는 지금 import하지 않으면 알 수 없습니다(`composition.py:299-308`). 그래서 YAML에 `required`/`optional`, capabilities, 제공 hook을 선언해야 합니다. 선언이 없으면 **필수로 간주**해서 기존 fail-fast를 유지합니다. 선언 검증기가 active를 미리 import하는 부분(`project_config.py:180-193`)도 이 범위에 넣습니다. |
| **E** 상태 변경 전 관문, 503, 1:1 유지 | **동의, 보완 둘** | ① "명시적 운영 실패 기록"은 Case 트랜잭션이 롤백되므로 **Case 밖에** 남겨야 합니다(별도 트랜잭션 또는 운영 로그). ② [사실] A2A 실행기는 취소와 실패를 모두 `ESCALATE`로 돌려줍니다(`a2a_executor.py:91-99,112-114`). 원격 팀이 꺼진 경우가 여기에 섞이면 운영자가 없는데 escalated로 표시되는 문제가 그대로 생깁니다. 원격 쪽 unavailable은 별도 코드로 503에 매핑해야 합니다. |

### B 판정 근거: 전역 hook 교체가 원자적이지 않은 이유 [사실]

1. `legs.register`는 대입문 두 개입니다(`legs.py:31`, `:32`). `clear()`는 모든 hook을 `None`으로 만듭니다(`:35-38`). clear와 register 사이에 읽는 요청은 `None`을 보고 **직선거리 어림값으로 성공**합니다. 이것은 C가 금지하는 결과입니다.
2. 한 함수 안에서 hook을 두 시점에 따로 읽습니다. `itinerary_changes.py:116`은 `walk_limit_m()`, `:141`은 `leg_planner()`입니다. 그 사이에 교체가 끼면 옛 판의 상한과 새 판의 계산기가 섞입니다.
3. `wire_domain_teams`는 네 모듈을 차례로 등록합니다(`composition.py:510-539`). 중간에 멈추면 부분 상태가 남습니다.
4. 조립 경로 세 곳이 전역을 다시 씁니다(`composition.py:269`, `:381`, `:558`). 후보 조립을 시작하기만 해도 전역이 바뀝니다.

### A2A까지 같은 관문을 적용할 위치

- **1차 관문 (Controller):** 판의 `runnable(team_id)`를 TeamTask를 만들기 전에 부릅니다. 대상은 `controller.py:333`(실행), `:438`(검토 task), `:166`, `:825`입니다. [사실] `team_executor.execute`(`:372`, `:454`)가 이 뒤에 있으므로, 여기서 막으면 Local과 A2A 둘 다 막힙니다.
- **2차 관문 (A2A 실행기 안, 방어용):**
  - **resolver:** [사실] 지금은 capability만으로 endpoint를 찾고 팀 상태는 보지 않습니다(`a2a_executor.py:18`). resolver 예외도 그대로 올라갑니다. [제안] resolver는 **판에 속한 표**로 만들고, capability→team_id가 `task.team_id`와 맞는지 확인합니다. 실패하면 `TeamUnavailable`을 냅니다.
  - **결과 대조:** [사실] 돌아온 `TeamResult`는 그대로 받고(`:100-101`), dict는 `setdefault`로 처리해서 원격이 `team_id`/`task_id`/`run_id`를 덮어쓸 수 있습니다(`:104-107`). [제안] 세 값이 task와 다르면 거부합니다.
  - **원격 unavailable 신호:** 별도 코드로 받아 503에 매핑하고 ESCALATE로 보내지 않습니다.

---

## 2. 양측이 합의할 수 있는 최소 구현 순서 [제안]

1. **계약 문서**
   - 사용자 요구가 우선한다는 것과, 어림값 대체를 폐기하는 범위.
   - hook 계약표(제공 팀, 필수/선택, 없을 때 처리, 기존 경로).
   - YAML의 required/optional, capability와 hook 선언.
   - 결정 15와 fail-fast를 어디까지 유지할지.
2. **예외 분리:** `TeamUnavailable`을 `ValueError` 계열이 아닌 타입으로 만들고 503에 매핑합니다. `ToolScopeViolation`은 422 경로에서 뺍니다.
3. **상태를 바꾸기 전 관문**
   - `case_dispatch`: ROUTED 커밋 전.
   - `_resume`: 행 잠금 안, `VALID_INPUT` 전.
   - Controller 4곳.
   - A2A resolver와 결과 대조.
4. **로더:** 꺼진 팀은 import하지 않습니다. `wire_domain_teams(active)`는 전역을 바꾸지 않고 **hook 표 객체를 반환**하게 합니다.
5. **불변 판**
   - 판 객체를 만들고, 참조 하나를 잠금 안에서 게시합니다.
   - 요청과 백그라운드 작업은 시작할 때 판을 고정합니다(contextvar 등).
   - `team_hooks` 함수는 고정된 판에서 읽습니다. 판이 없으면 전역으로 대체하지 않고 오류를 냅니다.
   - 운영 경로의 `register`/`clear` 전역은 없앱니다.
6. **호출 지점을 계약표대로 정리:** 필수 hook이 없으면 Case를 바꾸기 전에 unavailable. 선택 hook이 없으면 "없음"을 표시합니다.

---

## 3. 남은 미정 계약

- **계획 생성에서 이동 팀이 꺼진 경우:** `planner.py:1492`와 `intake/review.py:344`가 `leg_planner`를 씁니다. 계획 자체를 unavailable로 할지, 이동 항목 없이 계획을 만들지("이동 정보 없음" 표시) 정해야 합니다. 어느 쪽이 "독립 서비스 유지"인지는 사용자 판단이 필요합니다.
- **엔진 off + 팀 enabled에서 어림값 허용 여부:** 팀이 근거를 "estimate"로 표시하는 결과로 볼지 정해야 합니다.
- **감시 묶음:** 꺼진 종류를 건너뛴 기록을 어디에 남길지.
- **식당 원장:** hook이 없을 때 "모름"으로 계속할지, 요식 owner 요청은 불가로 할지.
- **contextvar 전파:** threadpool로 실행되는 sync 엔드포인트와 outbox/감시 작업에도 판이 넘어가는지 **확인이 필요합니다**. 아직 확인하지 않았습니다.
- **오류 코드와 응답:** `team_unavailable`과 `team_not_installed`를 나눌지, 503에 `Retry-After`를 붙일지, 원격 unavailable의 failure_code 이름.
- **판 revision 저장 위치:** `agent_runs`, 이벤트, 또는 둘 다.

---

## 4. 추가 인수 시험

**B: 원자성**
- 장벽을 `itinerary_changes.py:116`과 `:141` 사이에 두고 reload를 끼웁니다. 두 값이 모두 옛 판에서 와야 하고, 새 요청은 새 판을 봐야 합니다.
- reload를 반복하는 동안 다른 스레드가 hook을 계속 읽습니다. 두 판 모두 mobility가 enabled이면 `None`이 한 번도 관측되면 안 됩니다.
- 후보 조립이 실패해도 게시된 판의 identity가 그대로이고 전역 hook 모듈 상태도 바뀌지 않아야 합니다.

**C: 계약표**
- 이동 팀 disabled 상태의 일정 변경: 503, Case version 그대로, 어림값 이동 항목 0건.
- 엔진 off + 팀 enabled: disabled와 **다른** 코드나 근거로 계약표대로 동작.
- 유사도 팀 disabled: 요청은 성공하고 "유사도 없음"이 표시됨.

**판 고정**
- 감시 작업이 시작할 때 고정한 판으로 돌고, 꺼진 종류는 건너뛴 기록이 남음.
- sync 엔드포인트도 같은 판을 봄.

**A2A**
- 판에서 disabled인 팀이면 transport 호출 0회.
- resolver가 다른 팀의 endpoint를 돌려주면 거부.
- 원격이 `team_id`/`task_id`가 다른 결과를 돌려주면 completed로 받지 않음.
- 원격 unavailable은 503이고 ESCALATE가 아님.
- resolver 예외는 `TeamUnavailable`이 됨.

**D**
- optional 팀의 load가 실패해도 Core와 다른 팀은 정상.
- required 팀 실패, 선언 오류, 중복 id는 후보를 거부하고 옛 판을 유지.

**감사**
- 팀을 끈 뒤 옛 판에서 끝난 요청의 이벤트에 옛 revision이 남음.
