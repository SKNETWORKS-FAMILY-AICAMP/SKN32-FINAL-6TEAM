# Team 모듈 — 계약 사전과 빠진 두 단계

`[초안 2026-09-09]` **이 문서는 [`../briefing/A-COP_Team모듈_제작_브리핑.html`](../briefing/A-COP_Team모듈_제작_브리핑.html)
의 보충이다.** 겹치는 것은 안 쓴다.

★**먼저 그 브리핑을 읽는다.** Team 하나의 해부(manifest · 주입 · 단일 진입점 · 근거),
`TeamResult` 의 뜻, 팀별 명세, 만드는 순서, 자주 밟는 함정이 거기 있다.

이 문서가 채우는 것은 **둘**이다.

| | 왜 필요한가 |
|---|---|
| **① 계약 필드 사전** | 브리핑은 필드를 *설명*하는데, 만드는 사람은 **타입과 상한**이 필요하다 |
| **② 빠진 두 단계 — 생성·재검증** | 브리핑의 `execute()` 는 **다섯 칸**인데 v10 §5 는 **일곱**을 요구한다 |

---

## 1. 빠진 두 단계 — 여기가 핵심이다

`[실측 2026-09-09]` 브리핑 §1-③ 이 `execute()` 를 다섯 칸으로 적었다.

```
1 가드    2 준비    3 조회    4 판단    5 반환
```

**v10 §5 는 그 사이에 둘을 더 요구한다.**

> ★각 Team 안에서 **판정(코드)과 대안 생성(LLM)을 분리한다.**
> 생성한 대안은 **판정을 다시 통과해야** 통지된다.
> — v10 §5, v9 의 Response Generation & Review 원칙을 Team 내부로 흡수한 것

```
1 가드   2 준비   3 조회   4 판정   ⑤ 생성   ⑥ 재검증   7 반환
                            코드      LLM       코드
                            └───────────────────┘
                              같은 함수를 두 번 부른다
```

★**⑥이 이 아키텍처의 실체다.** ⑤ 없이 ④→7 로 가면 "안 된다" 만 말하는 제품이 되고,
⑥ 없이 ⑤→7 로 가면 **그럴듯한 대안이 검증 없이 고객에게 간다.** v9 에서 이 원칙을
별도 Team(`response_review`)으로 뒀다가 v10 이 각 Team 안으로 넣었다.

### 코드로 쓰면

```python
        # ── ④ 판정 (코드) ─────────────────────────────────────────
        #    도메인 규칙은 전부 여기. LLM 을 부르지 않는다.
        verdict = self._judge(booking, policy, task.context.current_state)
        if verdict.ok:
            return self._result(task, NextAction.RESPOND, evidence,
                                answer=self._explain(verdict), confidence=0.9)

        # ── ⑤ 생성 (LLM) ─────────────────────────────────────────
        #    깨졌을 때만 부른다. llm 이 없으면 건너뛴다.
        candidates = self._generate_alternatives(task, verdict) if self.llm else []

        # ── ⑥ 재검증 (코드) ──────────────────────────────────────
        #    ★④와 **같은 함수**를 다시 부른다. 다른 함수를 쓰면
        #      "생성용 느슨한 판정" 이 생겨서 원칙이 무너진다.
        passed = [c for c in candidates if self._judge(c, policy, {}).ok]
        if not passed:
            return self._escalate(task, evidence, "no_valid_alternative")

        # ── 7 반환 ───────────────────────────────────────────────
        proposal = self._proposal(task, "activity.rebook",
                                  {"booking_id": booking["id"], "to": passed[0]},
                                  evidence, risk="medium")
        return self._result(task, NextAction.WAIT_FOR_APPROVAL, evidence,
                            proposals=[proposal], confidence=0.8,
                            wait_reason="human_approval")
```

★**④와 ⑥이 같은 `self._judge` 를 부르는 것이 규칙이다.** 재검증용 함수를 따로 만들면
느슨해지고, 느슨해진 것을 아무도 못 본다.

`[미확보]` 이 두 단계를 강제하는 **테스트가 없다.** "생성한 것이 판정을 통과했는가" 를
기계로 확인하려면 `decisions` 에 재검증 기록을 남겨야 한다 — 지금 계약에 그 자리가 없다.

---

## 2. 계약 필드 사전

`[실측 2026-09-09]` `final_project_cs/app/core/contracts.py` 에서 그대로 읽었다.
**필드 이름·타입을 바꾸면 계약 변경**이고 Registry·Executor·A2A·평가 하네스가 걸린다.

### 받는 것 — `TeamTask`

| 필드 | 타입 | 상한·비고 |
|---|---|---|
| `contract_name` | `Literal["a_cop.team_task"]` | 고정 |
| `contract_version` | `Literal["1.0"]` | major 가 같아야 받는다 |
| `task_id` · `run_id` · `case_id` | `UUID` | |
| `team_id` | `str` | |
| `capability` | `str` | manifest 의 `capabilities` 중 하나 |
| `case_version` | `int` | 낙관적 동시성 기준 |
| `input_text` | `str` | **1 ~ 12,000자** |
| `context` | `ContextPack` | 읽을 것은 전부 여기 |
| `allowed_tools` | `list[str]` | |
| `deadline_at` | `datetime` | |
| `resume` · `resume_node` | `bool` · `ResumeNode \| None` | 승인 뒤 재개 |

### 읽는 것 — `ContextPack`

| 필드 | 타입 | 상한 |
|---|---|---|
| `current_state` | `dict` | |
| `evidence` | `list[Evidence]` | **최대 40** |
| `history_summary` | `str` | **≤ 10,000자** |
| `similar_cases` | `list[dict]` | **최대 3** |
| `knowledge_scope` | `list[str]` | |
| `token_budget` | `Literal[12000]` | 고정 |
| `estimated_input_tokens` | `int` ≥0 | |
| `degraded` | `bool` | **참이면 판정하지 않는다** |
| `omissions` | `list[str]` | 무엇이 빠졌는지 |

### 내는 것 — `TeamResult`

| 필드 | 타입 | 상한·비고 |
|---|---|---|
| `outcome` | `completed` · `waiting` · `handoff` · `escalated` · `failed` | **다섯이다** |
| `answer` | `str \| None` | **≤ 6,000자** |
| `confidence` | `float` | **0 ~ 1** |
| `evidence` · `decisions` · `action_proposals` | `list[...]` | |
| `next_action` | `NextAction` | 7종 |
| `wait_reason` · `required_input_schema` · `handoff_capability` · `failure_code` | 각 `\| None` | |
| `warnings` | `list[str]` | ★§3 참고 |

★**브리핑의 `outcome` 목록이 넷이다**(`completed · escalated · handoff · failed`).
**계약은 다섯**이고 `waiting` 이 빠져 있다 — 승인 대기가 바로 그것이라 여행에서 제일
많이 쓰는 값이다.

### 제안 — `ActionProposal`

| 필드 | 상한·규칙 |
|---|---|
| `action_type` | `"activity.rebook"` 처럼 점 표기 |
| `arguments` | `dict` |
| `idempotency_key` | **8 ~ 128자.** `idempotency_key(tenant_id, request_id, action_type, business_subject)` |
| `approval_required` | `bool` |
| `risk_level` | `low` · `medium` · `high` |
| `rationale_evidence_ids` | **비어 있으면 승인 목록에 안 올라간다** |

### 근거 — `Evidence`

| 필드 | 값 |
|---|---|
| `source_type` | `customer_message` · `db` · `policy` · `tool_result` · `case_event` · **`remote_agent`** |
| `confidence` | `float` **0 ~ 1** |
| `evidence_id` · `source_id` · `claim` · `value` · `observed_at` | |

★`remote_agent` 가 따로 있는 이유 — **우리가 확인한 사실**과 **남의 시스템이 그렇다고
말한 것**은 신뢰도가 다르다. A2A 로 받은 근거는 이 값을 쓴다.

### 선언 — `TeamManifest`

| 필드 | 상한·비고 |
|---|---|
| `capabilities` | **최소 1개** |
| `required_context` | `case_state` · `policy` · `db_facts` · `history` 중에서 |
| `max_steps` | **1 ~ 12, 기본 6.** 2026-09-09 부터 실제로 강제된다(`c060e9d`) |
| `default_capability` | `str \| None` — ★**적어야 한다.** §3 |
| `team_id` · `display_name` · `accepted_case_types` · `allowed_tools` · `knowledge_scope` · `active` · `implementation_revision` | |

---

## 3. 브리핑에 없는 함정 둘

브리핑 §7 에 있는 것은 안 적는다. **거기 없는 것만** 적는다.

### `warnings` 에 정상 안내를 넣으면 안 된다

`[실측 2026-09-09]` 러너가 `degraded` 를 이렇게 계산한다.

```python
"degraded": bool(record.get("degraded"))
            or bool(team_result.get("failure_code"))
            or bool(team_result.get("warnings"))     # ← 경고 하나면 degraded
```

Mock Team 이 부를 때마다 `"Mock 단계에서는 승인 제안만 생성하며…"` 를 넣었더니,
**golden 216행 중 degraded 102행(47%)의 58.8%(60행)가 가짜**가 됐다.
기권 지표가 통째로 오염됐다.

★`warnings` 는 **사람이 봐야 하는 것**만 넣는다. "나는 Mock 이다" 는 사람이 볼 것이
아니다 — manifest 나 `decisions` 에 적는다.

### `default_capability` 를 안 적으면 Registry 가 못 고른다

intent 이름과 capability 이름이 안 맞을 때 이름 매칭이 실패한다. 실재 팀 둘이 이것
때문에 주석을 달아 뒀다 — `fulfillment_logistics`(intent `shipping`, capability 는
`fulfillment.` / `shipment.`), `voc_store_manager`(intent `other`).

---

## 4. 공통 헬퍼를 어디에 둘까 — 제안

`[실측 2026-09-09]` 지금 6팀에 공통 성격 헬퍼가 **80줄 복붙**돼 있다.

```
_evidence   6/6 팀
_result     4/6 팀     ← 안 가진 팀은 반환 모양이 다르다
_escalate   2/6 팀
```

★**줄 수가 문제가 아니라 균일하지 않은 것이 문제다.** 여행 팀으로 늘리면 그대로 복제된다.

| 어디에 두나 | 도메인 어휘 가드 | 도메인을 갈아끼울 때 |
|---|---|---|
| **`app/core/team_base.py`** | 통과 — 옮길 코드에 도메인 어휘가 **없다** | **안 건드림** |
| `app/modules/_base.py` | 통과 | **같이 날아간다** |

**core 쪽을 권한다.** `TeamResult` 조립·Evidence 누적·에스컬레이션 반환에는 여행이든
소형가전이든 같은 것을 쓴다.

★**호환은 안 깨진다.** `TeamManifest` · `execute(task) -> TeamResult` · Registry 등록
방식이 그대로라 Composer·A2A·평가 하네스가 영향을 안 받는다.

---

## 5. 미해결 — 만들기 전에 정해야 한다

| 무엇 | 왜 먼저인가 |
|---|---|
| **`business_subject` 에 무엇을 넣나** | 지금 팀마다 다르다(`case_id` 3곳 · 도메인 id 1곳 · 3단 폴백 1곳). **여행은 Trip 하나에 예약이 여럿**이라 `case_id` 를 넣으면 한 Case 안의 두 예약이 **같은 키**를 갖는다(실측). → [구성안 §2-A](A-COP_여행Team모듈_구성안.md) |
| **재검증을 무엇으로 증명하나** | ⑥이 돌았는지 기계로 확인할 자리가 계약에 없다. `decisions` 에 남길지 정해야 한다 |

---

## 관계

- [`../briefing/A-COP_Team모듈_제작_브리핑.html`](../briefing/A-COP_Team모듈_제작_브리핑.html) — **먼저 읽는다.** 해부·팀별 명세·만드는 순서·함정
- [`A-COP_구현계획서_v10.md`](A-COP_구현계획서_v10.md) §5 · §6
- [`A-COP_여행Team모듈_구성안.md`](A-COP_여행Team모듈_구성안.md) — 팀별 대응
- [`../../final_project_cs/wiki/teams/index.md`](../../final_project_cs/wiki/teams/index.md) — 팀별 명세 정본
