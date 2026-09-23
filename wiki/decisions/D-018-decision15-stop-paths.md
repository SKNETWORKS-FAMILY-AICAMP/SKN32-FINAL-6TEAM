---
type: decision
title: 결정 15의 「서버를 끈다」는 세 층으로 나뉜다 — 조립·실행·배치
description: 값을 못 내면 멈춘다는 원칙은 그대로다. 멈추는 자리가 기동 조립·Case 실행·배치 스위퍼 셋이고, 요청 처리 중에는 서버를 내리지 않고 사람에게 넘긴다
status: draft
tags: [architecture, runtime, travel]
domain: travel
---

# D-018 결정 15의 「서버를 끈다」는 세 층으로 나뉜다

`[초안 2026-09-21]` v11 §0-4 결정 15 는 「1차 소스가 안 되면 대체로 값을 내고, **대체까지 안 되면 치명 결함 — 서버를 끈다**」로 한 문장이다.
코드는 그 원칙을 지키지만 **멈추는 자리가 셋**이고, 요청 처리 중에는 서버 프로세스를 내리지 않는다.
v11 은 읽기 전용이라 고치지 않고 이 문서가 그 자리를 대신한다(D-017 과 같은 방식).
합의되면 v11 사실표와 [architecture/notifications.md](../architecture/notifications.md) 에 한 줄로 반영한다.

## 맥락

문서 여러 곳이 「대체까지 실패하면 서버를 끈다」를 **현행 사양**으로 적고, 코드의 사람 인계 동작을 「사양을 구현한 해결책이 아니다」라고 적어 두었다(`final_project_cs/wiki/teams/mobility.md:31`·`dining.md:60`·`activity.md:228`·`booking-handoff.md:186`, 전부 2026-09-10 정정판).
그래서 지금 코드가 **미구현으로 보인다.** 실제로 코드를 읽으면 셋 중 둘은 이미 그대로 있고, 나머지 하나는 서버를 내리는 것이 오히려 해로운 자리다.

## 결정

> **「멈춘다」의 대상은 프로세스가 아니라 그 판정이다.**
> **기동 조립이 깨지면 기동을 거부하고, 배치 실행은 실패 종료로 끝내며, 고객 요청 처리 중에는 서버를 내리지 않고 그 Case 를 사람에게 넘긴다.**
> 어느 층에서도 **모르는 값을 지어내거나 「사건 없음」으로 넘기지 않는다** — 이 부분이 결정 15 의 본체이며 바뀌지 않는다.

| 층 | 언제 | 무엇을 한다 | 코드 |
|---|---|---|---|
| **조립(기동)** | 선언한 포트·Team 을 만들 수 없다 | `CompositionError` 로 **기동 거부** | `final_project_cs/app/composition.py:102`·`:106`·`:112`·`:192`·`:200` |
| 조립(기동) | 외부 소스 키가 없다 | 그 소스만 빠지고 기동은 된다. 무엇이 왜 빠졌는지 `unavailable` 에 남고 `/ui/admin` 이 보여 준다 | `app/infrastructure/travel/base.py:365`·`:411`~`:503` |
| **실행(Case)** | 1차·대체 소스가 모두 값을 못 냈다 | `verdict="fatal"` → 일정을 바꾸지 않고 `escalated(fatal_source_failure)` 로 **사람 인계** | `app/infrastructure/travel/disruptions.py:117`·`:148`, `app/modules/travel_ops/activity.py:83`, `mobility.py:69`, `itinerary_team.py:179` |
| **배치(스위퍼)** | 회차 안에 `fatal` 이 하나라도 있다 | stderr 로 사유를 내고 `--once` 는 **exit 1** — cron 이 실패로 본다 | `scripts/run_sweepers.py:186`·`:214` |

## 선택지와 이유

| 안 | 채택 | 이유 |
|---|---|---|
| 문구 그대로 — 요청 처리 중 실패면 프로세스를 내린다 | ❌ | 여행 한 건의 조회 실패로 **다른 고객의 여행까지 멈춘다.** 한 건의 불확실을 전체 장애로 키우는 쪽이 더 큰 피해다 |
| 실패를 삼키고 「사건 없음」으로 진행 | ❌ | 결정 15 가 막으려던 바로 그것이다. 근거 없는 문장 금지(`CLAUDE.md` §0.1) |
| **층별로 멈춘다 — 기동 거부 · 사람 인계 · 배치 실패 종료** | ✅ | 멈추는 단위가 **실패의 단위**와 같다. 아무도 「모름」을 받지 않고, 실패가 로그 속에만 남지도 않는다 |

## 결과

- 코드는 이미 세 층을 구현하고 있다. **이 결정으로 고칠 제품 코드는 없다.**
- 위에 적은 문서 네 곳의 「서버를 끈다」 문장은 이 문서를 가리키도록 고친다. 고치지 않으면 다음 사람이 구현된 것을 미구현으로 읽는다.
- 못 하게 되는 것: 「값을 못 내면 서버가 죽는다」를 단일 규칙으로 설명할 수 없다. 설명할 때 층을 같이 말해야 한다.

## 근거

`[실측 2026-09-21]` 코드를 직접 읽어 확인했다. 검증 기록은 `final_project_cs/wiki/records/reports/2026-09-21_0100_결정15_적용경로_실측.md`.

- `app/infrastructure/travel/base.py:368` — 「키가 없으면 **그 소스만** 빠진다. 앱이 죽지도 않고, 가짜로 채우지도 않는다」
- `app/infrastructure/travel/disruptions.py:148` — 「1차·대체 소스가 모두 값을 못 냈다」 → `status="failed"` → 같은 파일 `:117` 에서 `verdict="fatal"`
- `app/modules/travel_ops/activity.py:85` · `mobility.py:69` — `self._escalate(task, "fatal_source_failure", …)`
- `app/modules/travel_ops/scenario_mode.py:209` — 「점검 소스가 답하지 않은 항목이 … 일정을 바꾸지 않고 사람에게 넘겼어요(결정 15)」
- `scripts/run_sweepers.py:186` — 「결정 15 — 대체 소스까지 실패한 치명은 **사람이 봐야 한다.** 세기만 하고 넘기지 않는다」, `:214` — `return 1 if _report_errors(result) else 0`

## 아직 정하지 않은 것

- **기동 시 어느 소스까지 필수인가.** 지금은 어떤 외부 소스가 빠져도 기동한다. 「이것이 없으면 기동하지 않는다」 목록은 없다.
  대표 시연에 필요한 소스(기상·재난문자·교통 중 무엇)를 필수로 올릴지는 팀 확인이 필요하다.
- 이 문서의 상태는 `draft` 다. **사용자·팀 확인 전까지 결정이 아니라 현행 동작의 기록으로 읽는다.**

## 관계

- [../architecture/notifications.md](../architecture/notifications.md) — 통지에서 조회가 안 될 때
- [D-017](D-017-watch-cadence-golden-time.md) — 감시 주기. v11 을 고치지 않고 결정 문서가 대신하는 같은 방식
- `final_project_cs/wiki/teams/mobility.md` · `dining.md` · `activity.md` · `booking-handoff.md` — 층을 가리키도록 고친 자리
