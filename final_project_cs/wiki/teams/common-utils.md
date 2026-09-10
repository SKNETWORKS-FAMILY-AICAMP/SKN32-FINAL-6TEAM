---
type: plan
title: Team 공통 뼈대 — 설계는 있고 구현이 없다
description: 반복되는 네 가지를 조합형 유틸로 빼자는 설계안. 실제로는 상속 기반 _base.py 가 생겼다
status: draft
tags: [architecture, contract]
domain: neutral
---

# Team 공통 뼈대

`[실측]` `program/plan/A-COP_예제Team모듈_확충설계.md` §5 에서 이관. **wiki 에 통째로 없었다.**

### 반복되는 네 가지

| # | 무엇 |
|---|---|
| 1 | `TeamManifest` 작성과 capability·case type·scope 정적 검증 |
| 2 | `TeamTask` 에서 evidence 를 복사하고 tool·remote 결과를 표준 `Evidence` 로 정규화 |
| 3 | degraded context · tool loop · 사실 누락을 `TeamResult` 로 변환 |
| 4 | `ActionProposal` 의 idempotency key · risk level · approval flag · rationale evidence ID |

### ★ 상속이 아니라 조합이다

> **과도한 도메인 상속 계층은 만들지 않는다.**

```
app/modules/customer_ops/team_utils.py     순수 함수 넷
  evidence_from_context · failure_result · approval_result · proposal
```

**`CustomerOpsTeamBase` 의 생명주기나 상태에 결합하지 않는다.**

`[실측]` **그래야 Remote·Mock·Local 구현이 같은 계약을 선택적으로 재사용한다.** 상속이면 Remote Team 이 안 맞는다 — 그건 다른 프로세스에서 돈다.

**업무 판단은 각 Team 에 남긴다** — capability 판정, 환불 가능 여부, 배송 예외, 응답 tone.

### 공통 prompt 도 합치지 않는다

**각 Team 의 `answer.v1.md`·`answer.repair.v1.md` 는 같은 파일명 규칙을 쓰되 prompt key 와 knowledge scope 를 Team 별로 분리한다.**

`[실측]` **`prompts/judge/*.txt` 는 평가 prompt 다.** 업무 prompt 와 같은 것으로 취급하지 않는다.

### ★ 아직 없다

`[실측]` 2026-09-03 확인.

```
app/modules/customer_ops/team_utils.py     없음
```

**설계만 있고 구현이 없다.** Team 6종이 각자 같은 코드를 들고 있다.

`[미확보]` **중복이 실제로 얼마나 되는지 안 세었다.** 만들 값이 있는지는 그걸 봐야 안다.

## ★ [2026-09-10] 공통 뼈대는 생겼다 — 다만 조합이 아니라 상속이다

`[실측 2026-09-10 작업 트리]` **`app/modules/travel_ops/_base.py` (177줄)** 가 있고 여행 Team 여섯이 그것을 **상속**한다. **`[실측 git]` 미추적이다.**

★**이 문서가 말하던 `team_utils.py` 는 여전히 없다.** 그런데 **「공통 뼈대 구현이 없다」고 읽으면 틀린다** — 뼈대는 생겼고 **방식이 이 문서의 제안과 다르다.**

| | 이 문서의 제안 | 실제 |
|---|---|---|
| 방식 | **조합형 유틸**(순수 함수 넷) | **상속**(`TravelTeamBase`) |
| 파일 | `team_utils.py` | `travel_ops/_base.py` |
| 무엇이 들어 있나 | — | `_guard`·`_read`·`_evidence`·`_result`·`_escalate`·`_unknown`·`_proposal` |

★**상속을 고른 대가가 이미 나왔다.** 공용 기반이라 **결함도 한꺼번에 물려받는다** — `business_subject` 3단 폴백이 여행 Team 전부에 걸린다(`_base.py:169`). 조합형이면 쓰는 Team 만 걸렸을 것이다. → [build-order.md](build-order.md)

`[미확보]` **조합형으로 되돌릴지 정한 기록이 없다.** 아래 설계안은 그 판단의 재료로 남긴다.

## 관계

- [index.md](index.md) — Team 영역
- [team-contract/index.md](team-contract/index.md) — 계약
- [remote-team-a2a.md](remote-team-a2a.md) — 상속이면 안 맞는 쪽
