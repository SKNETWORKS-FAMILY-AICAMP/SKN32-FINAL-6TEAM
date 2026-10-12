# 2026-08-18 — versioning 스트림 3(`app/tools` 경계 리팩터) 검수

`S-VERSIONING-03-BOUNDARY-TOOLS.md` 계약으로 Codex 에게 실제 리팩터를
맡겼다. 결과물을 그대로 신뢰하지 않고 검수한 결과(RULE.md §3.6-3), 계약
위반 1건과 실제 결함 1건(운영에 영향)을 발견해 직접 고쳤다.

## 1. [계약 위반] "폴백 금지" 원칙을 어긴 암묵적 레거시 브리지

계약(`S-VERSIONING-03-BOUNDARY-TOOLS.md` "만들 것" #2)은 명확히 요구했다:
"기본값은 `None` 이 아니라 명시적으로 비워 둔다 — CLAUDE.md '폴백 금지'
원칙" 그리고 "`ReadToolbox` 를 직접 생성하는 테스트 전부... 가 새 생성자
시그니처에 맞게 고치도록 한다."

Codex 는 이 대신 `ReadToolbox.__init__` 에 옛 호출 방식과의 "호환 브리지"
를 추가했다:

```python
def __init__(self, tool_functions=None, *, policy_search=None):
    self.tool_functions = dict(tool_functions) if isinstance(tool_functions, dict) else {}
    self._legacy_connection_factory = tool_functions if callable(tool_functions) else None
    ...
```

`_legacy_connection_factory` 는 **저장만 되고 어디서도 읽히지 않는 죽은
필드**였다 — `ReadToolbox(get_connection)` 처럼 옛 방식으로 만들면
겉보기엔 성공하지만 실제로는 도메인 tool 이 하나도 등록되지 않은 빈
toolbox 가 만들어진다. 호출자는 연결이 배선됐다고 믿지만 `.call()` 시점에야
`ToolNotAllowed: unknown tool 'read.subscription'` 으로 조용히 늦게
터진다 — CLAUDE.md 가 막으려는 "신호 없는 축소"·"폴백" 그 자체다.

**수정**: 브리지를 제거하고 `ReadToolbox` 를 계약대로 순수
`tool_functions: dict` 필드 하나짜리 dataclass 로 되돌렸다. 남아 있던
옛 호출부 4곳을 새 시그니처로 직접 고쳤다:
- `examples/tests/test_team_scenarios.py` — `toolbox.subscription = ...`
  사후 대입 대신 `ReadToolbox({"read.subscription": ...})` 생성자 주입.
- `tests/integration/controller/test_controller_integration.py:423` —
  `policy_search=` kwarg 대신 `ReadToolbox({"read.policy": ...})`.
- `tests/unit/test_project_composition.py`, `tests/unit/test_composition_root.py`
  — tool 을 실제로 호출하지 않는 자리라 `ReadToolbox()`(빈 기본값)로 정리.
- **`eval/runners/common.py:263`** — `ReadToolbox(get_connection)` 옛
  방식이 그대로 남아 있었다. 브리지를 없앤 상태에서 이걸 그대로 뒀으면
  `tool_functions.get(name)` 이 `AttributeError: 'function' object has
  no attribute 'get'` 로 즉시 크래시했을 것이다 — `build_read_tool_functions(
  get_connection, policy_search_fn=search_policy)` 로 교체.

## 2. [실제 결함, 운영 영향] `FeedbackAnalyticsTeam` 이 완전히 깨져 있었다

`app/modules/customer_ops/feedback_team.py:33` 은 `self.tools.call(...)`
가 아니라 **`self.tools.connection_factory()` 를 직접 호출**해 배치
집계용 원본 connection 을 얻는다(named tool 하나로 표현하기 어려운
전체 배치 작업이라 애초에 이렇게 설계돼 있었다). 그런데 리팩터 후
`ReadToolbox` 에는 `connection_factory` 라는 이름의 필드 자체가 없었다
(브리지판에도 `_legacy_connection_factory` 라는 다른 이름으로만 있었다).
**`FeedbackAnalyticsTeam` 은 이 저장소의 유일한 production 활성 Team이고
(`config/project.yaml`), `scripts/run_daily_feedback.py` 가 매일 배치로
돌린다.** 이 상태로 배포됐으면 일일 VOC 배치가 매번 `AttributeError` 로
죽었을 것이다.

Codex 의 스트림 3 보고서(`wiki/records/reports/2026-08-18_S-VERSIONING-03-BOUNDARY-TOOLS_보고서.md`)
는 "Team 구현(`feedback_team.py`)... 은 범용 `ReadToolbox` 타입과 `call()`
계약만 사용하므로 기능 변경 없이 유지했다"고 적었다 — **이 문장은
사실이 아니다.** `feedback_team.py` 는 `call()` 을 전혀 쓰지 않는다.

**왜 기존 테스트가 못 잡았는가**: `FeedbackAnalyticsTeam.execute()` 를
실제 DB connection 과 함께 끝까지 실행하는 자동 테스트가 없다(배치
스크립트 경로는 CLI 로만 수동 검증돼 왔다, `wiki/records/reports` 이력 참고).
`tests/unit/voc/test_feedback*.py` 는 `run_daily_feedback()` 함수 자체나
inline 분류를 검증하지, `FeedbackAnalyticsTeam.execute()` 를 통해서
호출하지 않는다. 전체 pytest 스위트가 353 passed 로 "깨끗"했던 것은
이 경로가 애초에 테스트 커버리지 밖이었기 때문이다.

**수정**: `ReadToolbox` 에 `connection_factory: Callable[[], Any] | None = None`
을 **명시적인 정식 필드**로 추가했다(레거시 브리지가 아니다 — 배치
작업처럼 named tool 하나로 안 되는 Team 을 위한 의도적 확장). `app/composition.py`
의 `build_registry()` 기본 조립과 `scripts/run_daily_feedback.py` 양쪽에서
`connection_factory=get_connection` 을 명시적으로 함께 넘기도록 고쳤다.

**재현 검증**: 실제 PostgreSQL 커넥션으로 `FeedbackAnalyticsTeam.execute()`
를 오늘 날짜로 end-to-end 실행해 확인했다.

```python
team = build_registry(tools=ReadToolbox(
    tool_functions=build_read_tool_functions(get_connection),
    connection_factory=get_connection,
)).get("feedback_analytics").module
result = asyncio.run(team.execute(task))
# OK outcome= completed
```

## 종합 검증

```powershell
python -m pytest -q --ignore=tests/integration/rag
```
```text
353 passed, 1 deselected
```
```powershell
python -m pytest tests/architecture -q
```
```text
74 passed
```
```powershell
python -m scripts.verify_dod
```
```text
evidence 29/29 · 통과 25 · 부분통과 4 · 미착수 0
테스트: 357 passed, 0 skipped, 0 failed
```

## 스트림 1·2 는 결함 없음(경미한 보정만)

- 스트림 1(SemVer/CHANGELOG): `CHANGELOG.md` 의 GitHub 링크가 존재하지
  않는 저장소(`A-COP/project-final_project_sample`)를 가리켰다 — 실제
  원격(`roroblack/A-COP`)으로 고쳤다. 그 외 내용은 실제 커밋 이력과
  일치해 정확했다.
- 스트림 2(basement manifest/export): 검토 결과 결함 없음. `scripts/export_basement.py`
  실행·전용 테스트 2건 통과 확인.
