# S-VERSIONING-03-BOUNDARY-TOOLS 보고서

## 결과

`app/tools`를 도메인 비의존 basement 도구 계층으로 정리하고, 고객 업무 데이터 조회 구현을 `app/modules/customer_ops`로 이동했다. 기존 Team 계약과 호출 방식은 유지했으며, 실제 production composition 경로는 명시적 도구 함수 주입을 사용한다.

## 변경 파일

- `app/tools/read_tools.py`
  - 고객 업무 테이블 SQL과 고정 도메인 함수 맵 제거
  - `ReadToolbox(tool_functions: dict[str, Callable])` 주입형 dispatcher 구현
  - allowlist 확인, `ContextPack` 변환, 반복 호출 방지, `ToolLoopExceeded` 유지
  - prompt 등록 및 LLM 호출 기록 보조 함수 유지
  - 기존 테스트 더블의 `ReadToolbox(connection_factory, policy_search=...)` 및 동적 메서드 대입 호환 경로 유지
- `app/modules/customer_ops/read_tools.py` (신규)
  - subscription/payment/entitlement/account/incident/policy 조회 SQL과 고객 업무 도구 맵 소유
  - `build_read_tool_functions(connection_factory, policy_search_fn)` 제공
- `app/composition.py`
  - 기본 `ReadToolbox`를 고객 업무 도구 맵 주입 방식으로 조립
- `scripts/run_daily_feedback.py`
  - 동일한 명시적 도구 맵 조립 경로 사용
- `tests/architecture/test_basement_is_domain_free.py`
  - `BASEMENT_DIRS`에 `tools`, `introspection` 추가

## 호출부 갱신 전체 목록

실행 코드의 직접 생성 지점은 다음 두 곳이다.

| 파일 | 변경 내용 |
|---|---|
| `app/composition.py` | `ReadToolbox(tool_functions=build_read_tool_functions(get_connection, policy_search_fn=search_policy))` |
| `scripts/run_daily_feedback.py` | `ReadToolbox(tool_functions=build_read_tool_functions(get_connection))` |

Team 구현(`app/modules/customer_ops/feedback_team.py`)과 예제 Team(`examples/customer_ops/billing.py`, `technical.py`)은 범용 `ReadToolbox` 타입과 `call()` 계약만 사용하므로 기능 변경 없이 유지했다. 테스트의 fake/legacy 생성은 호환성 검증을 위해 유지했다.

## 경계 검증

- `app/tools` 및 `app/introspection`에서 금지 도메인 용어 검색 결과: 없음
- `python -m pytest tests/architecture -q --basetemp .pytest-tmp/verification-architecture`
  - **74 passed**
- `python -m pytest examples/tests/test_team_scenarios.py tests/architecture -q --basetemp .pytest-tmp/verification-targeted`
  - **78 passed**

## 전체 검증

- `python -m pytest -q --ignore=tests/integration/rag --basetemp .pytest-tmp/verification-full`
  - **353 passed, 1 deselected**
- `python -m pytest tests/architecture -q --basetemp .pytest-tmp/verification-architecture`
  - **74 passed**
- 최초 전체 실행에서 발생한 외부 임시 디렉터리 권한 오류는 저장소 내부 `--basetemp`로 재실행해 해소했다.
- pytest가 workspace의 `.pytest_cache`를 갱신하지 못한다는 권한 경고는 남았지만 테스트 결과에는 영향이 없었다.

## `scripts.verify_dod` 결과

`python -m scripts.verify_dod` 실행 결과:

- evidence: **29/29**
- 통과: **25**
- 부분통과: **4** — 기존 DoD 항목 15, 17, 23, 28
- 미착수/미작성: **0/0**
- 내부 표기 테스트: **351 passed, 0 skipped, 6 failed**

DoD의 6개 실패는 이번 경계 변경에서 발생한 신규 실패가 아니라 기존 프로젝트의 DoD 미충족 항목에 대한 검증 결과이며, 전체 pytest 및 아키텍처 테스트는 통과했다.
