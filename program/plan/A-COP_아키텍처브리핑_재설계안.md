# 아키텍처 브리핑 재설계안 — 무엇이 낡았고 어떻게 다시 그리나

`[2026-09-10]` 대상은 [`program/briefing/A-COP_여행Team모듈_아키텍처.html`](../briefing/A-COP_여행Team모듈_아키텍처.html)
(2026-09-09 작성). **이 문서는 계획서가 아니라 그 브리핑을 다시 그리기 위한 작업
지시서**다. 기준선은 [v11](A-COP_구현계획서_v11.md).

★**교차검증 상태.** 코덱스 두 계정(`~/.codex` · `~/.codex-alt`)이 **둘 다 쿼터
소진**으로 2026-09-10 14:08 까지 막혔다. alt 계정으로 돌린 첫 실행이 **범위 제한 없이
저장소를 훑다가**(로그 466KB) 쿼터를 태우고 중단됐다. **다만 중단 직전까지의 실측은
남았고, 그것이 아래 §1 의 줄수 항목을 독립적으로 확인해 줬다.** 나머지는 내가 코드를
직접 열어 확인한 것이다. **14:08 이후 §3 의 설계 제안을 코덱스에 반박시킬 것.**

---

## 0. 결론 — 다시 그려야 한다

**대조한 16개 중 8개가 어긋난다(50%).** 그리고 **브리핑에 논문 대조가 아예 없다** —
그 대조는 다른 브리핑에만 있고, **거기 적힌 상태마저 낡았다**(§2).

---

## 1. 무엇이 어긋나나 — 항목별 판정

`[실측 2026-09-10]` ★표는 코덱스(gpt-6-astra)가 **중단 전에 독립적으로 같은 값을 낸 것**이다.

| # | 브리핑이 말하는 것 | 실제 | 판정 |
|---|---|---|---|
| 1 | 배지 `V10 TRAVEL` | 기준선 **v11** | 낡음 |
| 2 | `기준선 A-COP_구현계획서_v10.md §5` | v11 §5 | 낡음 |
| 3 | `travel_ops/` 에 **파일 5개** | **9개** — `feedback.py`(152) · `verification_policy.py`(96) 가 새로 들어왔다 | 낡음 |
| 4 | 도해 `activity.py 204 lines` | **274** ★ | 틀림 |
| 5 | 본문 `Activity — 274줄` | 274 ★ | 맞음 · **한 문서가 204 와 274 를 둘 다 말한다** |
| 6 | `_base.py 231 lines` | **177** ★ | 틀림 |
| 7 | `dining.py 83 lines` | **96** ★ | 틀림 |
| 8 | `mobility.py 80` | 80 ★ | 맞음 |
| 9 | `booking_handoff.py 94` | 94 ★ | 맞음 |
| 10 | `locked_bookings.py 73` | 73 ★ | 맞음 |
| 11 | 6팀 `active: true` | 맞음 ★ | 맞음 |
| 12 | capability 이름 여섯 팀분 | 전부 일치 | 맞음 |
| 13 | **`Place Verification` — 미등록 · 유일한 A2A 자리 · 뺀 건지 빠진 건지 안 정해졌다** | **이미 만들어졌다** — `app/presentation/a2a/travel_remote_agent.py` 202줄, "Place Verification Remote Team" | **가장 크게 낡음** |
| 14 | 커머스 6팀 가드 통계 `degraded 5/6 · capability 4/6 · team_id 1/6` | 커머스 구현이 저장소에서 걷어내졌다 | **근거가 저장소에 없다** |
| 15 | TravelTeamBase 를 여섯 팀이 상속 · 부품 일곱 | 맞음 | 맞음 |
| 16 | Team 은 side effect 를 실행하지 않는다 | 맞음 | 맞음 |

**어긋남 7 + 근거 소실 1 = 8/16 = 50%.**

### 브리핑에 아예 없는 것 넷

코드가 v11 을 따라잡았는데 브리핑이 안 따라왔다.

| 없는 것 | 지금 코드 |
|---|---|
| **라우팅 두 축** | `controller.py:72` · `:175` 가 `resolve(case_type=case_type_of(issue_code, fallback=intent), intent=intent)`. **09-09 에는 한 축으로 뭉개져 여행 Case 가 아무 데도 못 갔다** |
| **분류 어휘** | `travel_ops/feedback.py` 152줄 — `INTENTS` 다섯 · `ISSUE_CODES` 17개 |
| **`select_capability`** | 여섯 팀 중 `mobility` 하나만 |
| **`response_review`** | `project.yaml` 에 `enabled: false` 로 자리만. **켜면 기동이 막힌다** |

### 버려야 할 문장 둘

도해 생성 메모가 본문으로 샜다. 읽는 사람에게 뜻이 없다.

> *"제공 원문이 `_result` 구현 중간에서 끝나므로 뒤쪽 반환 분기는 과제에 명시된 계약을 표시한다"*
> *"도구 예외를 특정 반환 분기로 연결하는 처리는 원문에서 확인할 수 없어 생략한다"*

---

## 2. 논문 대조 — 반영은 돼 있는데 그 반영이 낡았다

논문: **LLM-Enabled Multi-Agent Systems: Empirical Evaluation and Insights into
Emerging Design Patterns & Paradigms** (arXiv:2601.03328, 2026-01).

대조표는 **다른 브리핑**([`A-COP_Team모듈_제작_브리핑.html`](../briefing/A-COP_Team모듈_제작_브리핑.html) §4)에 있고
**아키텍처 브리핑에는 없다.** 그리고 그 표가 09-09 기준이라 두 칸이 틀렸다.

| 논문 패턴 | 그 브리핑(09-09) | 지금 코드 `[실측 2026-09-10]` |
|---|---|---|
| Role/Capability Declaration | 6/6 | 그대로 — `TeamManifest.capabilities` · `accepted_case_types` |
| Tool Permission Scoping | 강제됨 | 그대로 — `allowed_tools` + `ToolNotAllowed` |
| Orchestration vs Autonomy | 구현됨 | 그대로 — Controller 가 흐름을 쥔다. Team 끼리 안 부른다 |
| Human Approval Boundaries | 구현됨 | 그대로 — `ActionProposal` + 승인 직전 재대조 |
| **Output Verification** | **부분 — 꺼져 있다** | ★**켜졌다.** `composition.py:270` 이 `travel_ops/verification_policy.py`(96줄, 신규)를 물고 `controller.py:332` 가 `check_proposal` 을 부른다 |
| **반복 상한 `max_steps`** | **선언만 되고 아무도 안 읽는다** | ★**강제된다.** `_base.py:78` 이 `budget=self.manifest.max_steps` 를 넘기고 `read_tools.py` 가 `ToolBudgetExceeded` 를 던진다 |

★**논문이 짚은 구멍 둘이 다 메워졌다.** 그런데 **두 브리핑 다 그걸 모른다.**

★**이것이 논문을 쓴 값어치다.** 다섯 패턴과 대조하지 않았으면 `max_steps` 가
선언만 되고 아무도 안 읽는 상태를 **아무도 못 봤을 것이다.** 다시 그릴 때
**「대조가 무엇을 찾아냈나」를 보여야** 논문을 인용한 뜻이 산다.

---

## 3. 다시 그린다면 — 장 구성 여섯

★**지금 브리핑의 구성은 「무엇이 있나」다.** 제안은 **「무엇을 어떻게 막나」**로 바꾼다.
심사에서 물어보는 것이 그것이고, 논문 다섯 패턴도 전부 *막는 실패*로 정의돼 있다.

### 1장 · 한 장으로 보는 전체

**지금 도해를 살리되 넷을 고친다.**

| | |
|---|---|
| 고칠 것 | 배지를 **v11**로 · 줄수를 실제로 · `Place Verification` 을 **OPEN → LIVE**(`travel_remote_agent.py` 202줄) |
| 더할 것 | **분류 층** — 지금 도해는 외부 에이전트 → Controller → Team 인데, **그 사이에 `feedback.py`(어휘)와 두 축 라우팅이 있다.** 그게 09-09 에 여행 Case 를 다 막았던 자리다 |
| 더할 것 | **`response_review` 자리** — `enabled: false` 인 빈 칸으로. 있는 척도 없는 척도 하지 않는다 |

### 2장 · ★라우팅 — 왜 두 축인가

**새 장이다. 지금 브리핑에 없다.**

도해 하나 — 같은 Case 가 **한 축일 때 어디로 가고 두 축일 때 어디로 가는지**.

```
issue_code = "activity_weather_risk"
                ↑ case_type            ← 팀을 고른다
intent     = "incident_report"         ← capability 를 좁힌다
```

★**보여줄 것은 실패였던 상태다.** 09-09 에 `resolve(case_type=intent, intent=intent)`
였고 요청 종류 다섯이 여섯 팀 어느 것과도 안 맞아 **전부 라우팅 실패**했다.
지금은 `controller.py:72,175` 가 두 축을 쓴다.

### 3장 · Team 하나의 내부

**지금 2장을 살린다.** 가드 셋 → 조회 → 근거 → 반환 네 갈래. 다만 —

| | |
|---|---|
| 고칠 것 | `_base.py` **177줄**(231 아님) |
| 더할 것 | ★**예산(`max_steps`)이 `_read` 에 실제로 걸린다** — `_base.py:78` → `read_tools.py` `ToolBudgetExceeded`. **이것이 논문 대조가 찾아낸 구멍이었다** |
| 더할 것 | `select_capability` 훅 — **여섯 중 하나만 있다.** 빈 칸을 빈 칸으로 그린다 |
| 버릴 것 | §1 의 「샌 문장」 둘 |

### 4장 · 팀별 구현

**지금 3장을 살린다.** 줄수만 고치면 된다(activity 274 · dining 96).

**더할 것 하나** — `activity.py` 가 **예약이 없으면 아무것도 판정 못 한다**
(`:66` `read.booking` → `:76` 예약 없으면 「모름」 → `:78` 규정 없어도 「모름」).
v11 §5-D 가 **판정 입력을 「일정 항목」으로 올리라**고 정한 자리다.
**경복궁을 넣으면 두 번 막힌다** — 이걸 보여야 다음에 뭘 고칠지 보인다.

### 5장 · ★논문 다섯 패턴이 어디에 붙나

**새 장이다.** §2 의 표를 그대로 쓰되 **도해에 앵커를 찍는다** — 1장 도해 위에
다섯 패턴 배지를 얹어 **어느 부품이 어느 패턴인지** 보이게.

```
Role/Capability      → TeamManifest (팀 상자마다)
Tool Permission      → allowed_tools (Team → 도구 화살표 위)
Orchestration        → Controller 상자
Human Approval       → ActionProposal → 승인 게이트
Output Verification  → check_proposal (승인 직전)
반복 상한            → _read 의 budget
```

★**「다섯 중 넷」이 아니라 「여섯 중 여섯」으로 바뀐 것**을 이 장이 말한다.
그리고 **무엇을 고쳐서 그렇게 됐는지**를 같이 적는다 — 그게 대조의 값이다.

### 6장 · 아직 안 된 것

★**따로 장을 둔다.** 지금은 「OPEN」 배지 하나로 흘려 놓아 심사에서 캐물으면 방어가 안 된다.

| 항목 | 상태 |
|---|---|
| `select_capability` | 필요한 팀 넷 중 **하나만** |
| 멱등 키의 대상 | v11 §4-E 가 정했는데 `controller.py:374` 는 아직 `case_id` 고정 |
| 무예약 활동 판정 | 예약이 없으면 못 돈다 (4장) |
| `response_review` | 여행판이 **없다.** `enabled: false` |
| `A2A` 원격 | 만들어졌지만 **시뮬레이터**다 — 실제 장소 원장에 안 붙는다 |

---

## 4. 다시 그릴 때 지킬 것

| | |
|---|---|
| **숫자는 세어서 넣는다** | 이번 어긋남 8개 중 **4개가 줄수**였다. 도해와 본문이 서로 다른 값을 말한 자리도 있었다. **한 곳에서만 세고 그 값을 쓴다** |
| **삭제된 코드를 인용하지 않는다** | 커머스 가드 통계는 근거가 저장소에서 사라졌다. 인용하려면 **커밋 해시를 같이 적는다** |
| **작업 메모를 본문에 남기지 않는다** | 「제공 원문이 …에서 끝나므로」류 |
| **배지에 판과 실측 시각을 박는다** | 그게 있어서 이번에 낡은 걸 바로 알았다. **없애지 말고 갱신한다** |

`[미확보]` **이 재설계안 자체는 아직 코덱스 반박을 못 거쳤다** — 쿼터가 14:08 에
풀린다. 특히 §3 의 장 구성은 **내 판단**이고 반박받아야 한다.

---

## 관계

- [`A-COP_구현계획서_v11.md`](A-COP_구현계획서_v11.md) — §5-B 라우팅 · §5-C capability · §5-D 무예약 활동 · §4-E 멱등 키
- [`../briefing/A-COP_여행Team모듈_아키텍처.html`](../briefing/A-COP_여행Team모듈_아키텍처.html) — 다시 그릴 대상
- [`../briefing/A-COP_Team모듈_제작_브리핑.html`](../briefing/A-COP_Team모듈_제작_브리핑.html) — §4 논문 대조표 (두 칸이 낡았다)
- `program/research/_회의_2026-09-09.md` — 논문을 보고 보완 작업을 시작한 기록
