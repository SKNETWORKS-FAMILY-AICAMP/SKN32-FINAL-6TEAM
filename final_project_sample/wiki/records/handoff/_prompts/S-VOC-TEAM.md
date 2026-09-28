# 구현 지시 — VOC 를 Agent Team 으로 (v7 §0 변경 4 · P6)

## 0. 배경

v7 §0 변경 요약:

> VOC & Store Manager: Feedback Analytics 배치 모듈 → **VOC/Feedback Analytics Agent Team**.
> 기존 배치는 **이 Team 의 실행 형태**다.
> 이유: VOC 가 **집계·임계값·알림·위임을 판단**하기 때문이다.

지금은 `app/application/feedback_job.py::run_daily_feedback()` 이 순수 함수로 존재하고
`scripts/run_daily_feedback.py` 가 CLI 에서 직접 부른다. **Team 이 아니다.**

현재 **319 passed, 0 failed, skipped 0**.

## 1. ★읽어야 할 파일 (이것만 읽어라 — 넓게 읽지 마라)

```
app/application/feedback_job.py            ← 옮기지 않는다. 그대로 감싼다
app/modules/customer_ops/billing.py        ← TeamModule 구현 패턴 (참고용)
app/tools/read_tools.py                    ← ReadToolbox.connection_factory 필드만 본다
app/core/contracts.py                      ← TeamManifest·TeamModule·TeamResult·Evidence 만 본다
config/project.yaml
app/composition.py                         ← _instantiate_team·build_registry 만 본다
scripts/run_daily_feedback.py
```

★다른 파일을 읽지 마라. 이 작업은 이 7개로 끝난다.

## 2. 소유 범위

```
app/modules/customer_ops/feedback_team.py   ← 새로 만든다
scripts/run_daily_feedback.py               ← Team 경유로 바꾼다
config/project.yaml                          ← team 선언 추가
tests/**  wiki/records/reports/
```
★금지: `app/core/**`, `app/domain/**`, `app/application/feedback_job.py`(내용 변경 금지 — 그대로 감싼다),
`app/presentation/**`, `app/console/**`, `app/infrastructure/**`(읽기만).

## 3. 설계 — ★그대로 따라라. 새로 설계하지 마라

### 3-1. `app/modules/customer_ops/feedback_team.py`

```python
class FeedbackAnalyticsTeam:
    manifest = TeamManifest(
        team_id="feedback_analytics", display_name="VOC / Feedback Analytics Team",
        contract_name="a_cop.team_task", supported_contract_versions=["1.0"],
        capabilities=["voc.aggregate_and_alert"],
        # ★비워 둔다. Controller 가 실제 Case 를 여기로 라우팅하면 안 된다 —
        #   이 Team 은 스케줄러가 직접 부른다.
        accepted_case_types=[],
        required_context=[], allowed_tools=[], knowledge_scope=["voc"],
        max_steps=1, active=True, implementation_revision="2026-08-17",
    )

    def __init__(self, tools: ReadToolbox, llm=None) -> None:
        self.tools = tools   # llm 은 안 쓴다. billing.py 와 생성자 모양만 맞춘다

    async def execute(self, task: TeamTask) -> TeamResult:
        """task.context.current_state 에 report_date(ISO) 가 있어야 한다."""
        report_date = date.fromisoformat(task.context.current_state["report_date"])
        with self.tools.connection_factory() as conn, conn.transaction():
            report = run_daily_feedback(conn, report_date=report_date, tenant_id=task.context.tenant_id)

        # ★"판단" 은 여기다 — alert 유무로 outcome 을 가른다.
        #   그냥 통과시키는 wrapper 가 아니라 **판정**을 한다.
        alerts = report.get("alerts") or []
        evidence = [Evidence(evidence_id=f"voc:totals:{task.task_id}", source_type="db",
                             source_id="feedback_analytics_reports", claim="집계 완료",
                             value=report["metrics"], confidence=1.0,
                             observed_at=datetime.now(UTC))]
        decisions = [{"alert": a, "escalate": True} for a in alerts]

        return TeamResult(
            task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
            outcome="escalated" if alerts else "completed",
            answer=f"급증 alert {len(alerts)}건" if alerts else "급증 없음",
            confidence=1.0, evidence=evidence, decisions=decisions,
            next_action=NextAction.ESCALATE if alerts else NextAction.RESPOND,
        )
```

★정확한 필드명·타입은 `app/core/contracts.py` 를 실제로 열어 맞춰라. 위는 뼈대다.
★`ActionProposal` 을 내지 않는다 — VOC 는 side effect 를 제안하지 않는다.

### 3-2. `scripts/run_daily_feedback.py` — Team 경유로 바꾼다

지금은 `run_daily_feedback()` 을 직접 부른다. **v7 이 요구하는 것은 "배치가 이 Team 의
실행 형태" 이므로, 스크립트가 `FeedbackAnalyticsTeam.execute()` 를 호출**하게 바꾼다.

- `TeamTask` 를 스크립트가 직접 만든다 — 진짜 Case 가 없으므로 **합성 식별자**를 쓴다
  (`task_id=uuid4()`, `run_id=uuid4()`, `case_id=uuid4()`)
- `ContextPack.current_state = {"report_date": args.date.isoformat()}`
- 출력은 지금처럼 JSON 을 stdout 에 찍는다. **CLI 동작은 바뀌면 안 된다**
  (`python -m scripts.run_daily_feedback --date 2026-08-14` 그대로 동작)

### 3-3. `config/project.yaml`

```yaml
- team_id: feedback_analytics
  active: true
  implementation_ref: app.modules.customer_ops:FeedbackAnalyticsTeam
```

## 4. 완료 조건

```powershell
python -m pytest tests -q
```
**319건 이상, 0 failed, skipped 0.**

그리고 ★**실제로 돌려서 출력을 확인하라:**

```powershell
python -m scripts.run_daily_feedback --date 2026-08-14
```
전과 같은 모양의 JSON 이 나와야 한다. **원문을 리포트에 붙여라.**

★**Controller 가 실제 Case 를 이 Team 으로 절대 라우팅하지 않는지** 확인하는 테스트를 추가하라
(`accepted_case_types=[]` 이므로 어떤 intent 로도 매칭되면 안 된다).

## 5. 리포트

`wiki/records/reports/2026-08-17_S-VOC-TEAM_리포트.md`
— §4 출력 원문, 추가한 테스트, 발견한 결함(있다면).

## 6. 하지 말 것
- ❌ `feedback_job.py` 의 로직을 고치거나 옮기기 (그대로 감싼다)
- ❌ Controller 가 실제 Case 를 이 Team 으로 라우팅하게 만들기
- ❌ CLI 출력 형태를 바꾸기
- ❌ `app/core/**` 수정
- ❌ 소유 범위 밖 파일 읽기 (§1 목록만)
- ❌ 띄워보지 않고 "완료"
