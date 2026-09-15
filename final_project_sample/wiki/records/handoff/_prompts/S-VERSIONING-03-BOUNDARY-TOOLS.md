# S-VERSIONING-03-BOUNDARY-TOOLS — `app/tools` basement/domain 경계 정리 (실제 리팩터)

## 배경

pip 패키지화(장기 목표, 이번 스트림 범위 아님)를 검토하며 Claude·Codex
자문에서 확인한 사실: `app/tools/read_tools.py` 는 `app/tools/` 에 있어서
basement 취급되지만, 실제로는 `subscriptions`·`payments`·`entitlements`·
`incidents` 테이블을 직접 쿼리하는 **도메인 결합 SQL**을 담고 있다.
`tests/architecture/test_basement_is_domain_free.py` 의 `BASEMENT_DIRS =
("core","domain","application","infrastructure","presentation")` 에
`tools` 가 없어서 **이 위반이 지금 검사 대상 밖이다** — 테스트가 통과해도
basement 가 순수하다는 증거가 안 된다. 이건 이 저장소가 2026-08-16 에
`app/core/verification.py` 에서 이미 한 번 겪은 실수(`wiki/records/handoff/10`
§4)와 같은 종류다.

## 실제로 고쳐라 — 이번엔 "리포트만"이 아니다

이전 버그사냥 라운드들과 다르게, **이 스트림은 실제 코드를 고친다.**
다만 조심해서 고쳐야 한다 — `ReadToolbox` 는 `app/composition.py`,
`app/modules/customer_ops/feedback_team.py`(★**현재 유일한 production
활성 Team**, `config/project.yaml` 에 등록됨), `examples/customer_ops/
{billing,technical}.py`(예시로 보존된 Team), `scripts/run_daily_feedback.py`,
여러 테스트가 이미 쓰고 있다. **하나라도 깨지면 안 된다.**

## 만들 것

1. **`app/modules/customer_ops/read_tools.py`**(신규) — 도메인 결합
   쿼리 메서드를 여기로 옮긴다: `subscription`·`payment_history`·
   `entitlement`·`account`·`incident` (지금 `app/tools/read_tools.py`
   에 있는 그대로, SQL 문자열도 그대로 — 동작을 바꾸지 않는다, 위치만
   옮긴다). 이 파일이 "도메인이 무엇을 조회할 수 있는지"를 선언하는
   자리다(★basement 는 이 이름들을 몰라야 한다 — `verification_policy.py`
   가 대조 어휘를 선언하는 것과 같은 패턴).

2. **`app/tools/read_tools.py`**(수정) — `ReadToolbox` 를 **범용 디스패처**
   로 만든다. 지금처럼 도메인 메서드를 하드코딩하지 않고, 생성자에서
   `tool_functions: dict[str, Callable]` 를 주입받게 바꾼다(기본값은
   `None` 이 아니라 **명시적으로 비워 둔다** — CLAUDE.md "폴백 금지"
   원칙). `call()` 은 하드코딩된 `functions = {...}` 딕셔너리 대신
   `self.tool_functions` 를 쓴다. `policy()`·`register_prompt_files()`·
   `record_llm_call()`·`ToolContext`·`ToolLoopExceeded`·`call()` 의
   허용 검사·중복 호출 검사 로직은 basement 에 남는다(도메인 무관).

   ★`policy()` 메서드 자체(정책 검색 위임)는 도메인 무관이니 basement
   에 남긴다 — `read.policy` 는 모든 도메인이 쓸 공통 tool 이다.

3. **호출부 갱신** — `app/composition.py`, `app/modules/customer_ops/
   feedback_team.py`(필요하다면), `examples/customer_ops/{billing,
   technical}.py`, `scripts/run_daily_feedback.py`, 그리고 `ReadToolbox`
   를 직접 생성하는 테스트 전부(`grep -rln "ReadToolbox(" .` 로 찾아라)
   가 새 생성자 시그니처(`tool_functions=...`)에 맞게 `app/modules/
   customer_ops/read_tools.py` 의 함수들을 주입하도록 고친다. **조립
   책임은 `app/composition.py`(도메인 조립을 허용하는 유일한 basement
   예외 — 이미 `test_no_basement_file_imports_a_domain_module` 이 이
   파일만 `pytest.skip` 한다)에 둔다.**

4. **`tests/architecture/test_basement_is_domain_free.py`** —
   `BASEMENT_DIRS` 에 `"tools"` 를 추가한다. 이 테스트가 통과해야
   이번 스트림이 성공했다는 증거다(추가 전엔 실패해야 정상 — 즉 수정
   전/후로 한 번씩 돌려서 "전엔 이 파일이 위반을 잡아냈다"를 리포트에
   남겨라).

5. **`app/introspection/`** — 코드 검색으로 도메인 어휘가 없음을 이미
   확인했다(`payment`·`subscription`·`entitlement`·`refund`·`invoice`·
   `order_id`·`line_item`·`shipment`·`sku`·`cart` 없음). 그래도 같은
   이유로 검사 대상에 넣어라 — `BASEMENT_DIRS` 에 `"introspection"` 도
   추가한다. 이미 깨끗하므로 이 추가는 테스트 실패를 유발하지 않아야
   한다(실패하면 그건 새로운 발견이니 고치지 말고 리포트에 남겨라 —
   이 스트림 범위를 벗어나면 보류해도 된다).

## 하지 않을 것

- `app/application/feedback_job.py`, `app/presentation/ui/routes.py`,
  `app/presentation/api/cases.py`, 도메인 마이그레이션 파일은 **이번
  스트림에서 재분류하지 않는다** — Codex 가 이전 자문에서 "별도 분류가
  필요하다"고 짚었지만, 범위를 한 번에 넓히면 검증이 흐려진다. 대신
  리포트에 "다음 스트림 후보"로 파일:이유를 나열만 해라.
- `ReadToolbox` 의 SQL 문 자체를 바꾸지 않는다(오탈자를 발견해도 이번
  스트림에서 고치지 말고 리포트에 남겨라 — 범위 밖).
- `config/project.yaml`·`app/core/project_config.py`(`KNOWN_IMPLEMENTATION_REFS`)
  는 건드리지 않는다.
- pip 패키지화·`app` 리네임은 하지 않는다(별도 논의 대상, 이번 스트림
  범위 밖).

## 검증 — 반드시 순서대로

```powershell
# 1. 수정 전: tools 를 검사 대상에 넣으면 지금 실패하는지 먼저 확인해라
#    (증거로 남긴다 — 실패 원문을 리포트에 인용)
python -m pytest tests/architecture -q

# 2. 리팩터 적용 후 전체
python -m pytest -q --ignore=tests/integration/rag
python -m pytest tests/architecture -q
python -m scripts.verify_dod
```

`feedback_team.py` 가 여전히 정상 동작하는지(현재 유일한 production
Team) 특히 확인해라 — 관련 테스트(`tests/unit/voc/test_feedback*.py`,
`tests/unit/teams/**`, `tests/contract/**`)가 전부 통과해야 한다.

## 만들 것 (리포트)

`wiki/records/reports/2026-08-18_S-VERSIONING-03-BOUNDARY-TOOLS_리포트.md` —
옮긴 파일, 고친 호출부 전체 목록, 수정 전/후 `tests/architecture` 실행
결과 원문(전: 위반 검출 / 후: 통과), 전체 테스트 실행 결과, 범위 밖으로
남긴 사각지대 목록(파일:이유).
