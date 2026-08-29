# S-BASEMENT-01-AUTH-CONTRACT — resume 토큰 인증 + MCP 멱등성 + tool-scope 강제

## 0. 배경 — sample(참고용, 절대 수정 금지)과의 실제 diff에서 발견됨

이 세 결함은 오늘 `final_project_sample/acop_basement/` (참고 구현체, **읽기 전용
— 절대 쓰지 마라**) 와 `final_project_cs/app/` 를 실제 내용 대조해서 찾은
것이다. sample 은 이미 고쳐져 있다 — **sample 파일을 그대로 복사하지 말고,
같은 수정을 cs 의 실제 코드 구조에 맞게 다시 구현해라**(cs 는 sample 과
경로/일부 구조가 다르다).

### 1) resume 토큰 인증 우회 (가장 심각)

- `app/presentation/api/cases.py` 의 `POST /v1/cases/{case_id}/messages`
  가 지금 **실제 발급된 토큰을 검증하지 않는다** — 고객이 보낸 원문
  메시지를 해시해서 `resume_token_hash` 라고 이름 붙인 값을 쓰고 있다.
  이러면 `case:write` scope 만 있으면 **진짜 토큰 없이** 대기중인 어떤
  Case 든 재개시킬 수 있다.
- `final_project_sample/acop_basement/presentation/api/cases.py` 를
  읽고 어떻게 실제 발급된 토큰을 검증하는지(아마 `Controller.resume()`
  가 실제 토큰 검증 로직을 갖고 있을 것 — `final_project_sample/acop_basement/application/controller.py`
  도 같이 읽어라) 확인해라.
- cs 에서 이 검증을 실제로 적용해라 — 토큰 발급이 어디서 되는지부터
  추적해라(waiting_input 전이 시 토큰이 어디 저장/발급되는지).

### 2) MCP `open_support_case` 비멱등

- `app/presentation/api/cases.py` 의 `_mcp_open()` 이 재시도마다 새
  Case 를 만든다. DoD-11 이 주장하는 "동일 요청 10회 → action_requests
  1행" 보장이 REST 경로에서만 검증됐고 MCP 경로는 검증도 강제도 안 됐다.
- sample 의 동등 코드를 참고해서 멱등키 기반 처리를 추가해라(REST
  경로가 이미 하는 방식과 같은 원리 — dedupe key 로 기존 결과 반환).

### 3) Team tool-scope 강제 부재

- `app/core/remote_team/executor.py` 의 `LocalTeamExecutor.execute()`
  가 `task.allowed_tools` 를 `manifest.allowed_tools` 와 대조하지 않고
  그냥 `entry.module.execute(task)` 를 호출한다.
- `CLAUDE.md` §2: "Team 은 TeamManifest.allowed_tools 밖의 tool 을 호출할
  수 없다. Registry 가 거부한다." — 이게 사실이 되게 만들어라.
- `final_project_sample/acop_basement/core/remote_team/executor.py` 를
  참고해라 — `task.allowed_tools ⊆ manifest.allowed_tools` 아니면
  `ToolScopeViolation` 을 던지는 방식이다.
- **지금 당장 악용 가능하진 않다**(Controller 가 항상 manifest 로
  `allowed_tools` 를 채워서 호출하기 때문) — 하지만 강제 경계 자체가
  없다는 게 문제다. 기존 정상 흐름(Controller→execute)이 깨지지 않는지
  테스트로 확인해라.

## 1. 검증

- 각 항목마다 실제로 버그가 재현됐었다는 걸 확인하는 테스트를 추가해라
  (수정 전 상태를 흉내낸 테스트가 실패하고, 수정 후 통과하는 걸 직접
  확인해라 — 그냥 통과하는 테스트만 추가하지 마라).
- `python -m pytest -q -m "not live"` 전체 실행 결과를 리포트에 실제
  출력 그대로 붙여라(현재 359 passed 기준 변화 명시).

## 2. 쓰기 대상

- `app/presentation/api/cases.py`
- `app/core/remote_team/executor.py`
- `app/application/controller.py` (토큰 검증에 `Controller.resume()`
  관련 로직이 필요하면 — 최소한만 건드려라, §3 은 다른 작업이 이 파일의
  다른 부분을 다룬다)
- 관련 신규 테스트 파일들
- `docs/reports/2026-08-24_S-BASEMENT-01-AUTH-CONTRACT_리포트.md` (신규)

## 3. 하지 말 것

- `final_project_sample/` 아래 어떤 파일도 수정 금지 — 읽기만
- sample 파일을 그대로 복사-붙여넣기 하지 마라 — cs 구조에 맞게
  다시 구현해라
- `app/application/controller.py` 의 WAIT_EXPIRED/commit 관련 로직은
  건드리지 마라(다른 작업이 처리한다)
