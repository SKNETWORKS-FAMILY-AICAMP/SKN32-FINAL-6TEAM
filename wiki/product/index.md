---
type: guide
title: Product
description: 무엇을 만들고 누구를 위한 것인가. 제품 정의·페인포인트·페르소나·범위·용어
status: draft
domain: travel
---

# Product

"이게 왜 필요한가"에 답해야 할 때 여기부터 본다.

★**[2026-09-08] 도메인이 여행으로 바뀌었다.** 이 영역에서 [scope.md](scope.md)만 여행으로 갱신됐다. `positioning`·`problem`·`personas`·`pitch-questions`·`glossary`는 **아직 쇼핑몰 CS 기준**이다 — 제품 정의는 계획서 v11 §0-1·§1·§2를 먼저 본다. 낡은 문서를 지우지 않는 이유는 그 시점 판단의 근거라서다.

## 읽기 순서

1. [positioning.md](positioning.md) — 무엇을 팔고 무엇을 팔지 않는가
2. [problem.md](problem.md) — 누가 무엇 때문에 괴로운가
3. [personas.md](personas.md) — 그 사람들이 누구인가
4. [scope.md](scope.md) — **여행 MVP 7주에 무엇까지 하는가** (이 영역에서 유일하게 여행으로 갱신된 문서)
5. [glossary.md](glossary.md) — 용어

## 각 문서

| 문서 | 답하는 질문 |
|---|---|
| [positioning.md](positioning.md) | 시장의 기존 제품과 무엇이 다른가 |
| [problem.md](problem.md) | 지금 사람들이 어떻게 버티고 있는가 |
| [personas.md](personas.md) | 누가 쓰고 **누가 돈을 내는가** |
| [scope.md](scope.md) | 무엇을 안 하는가 |
| [glossary.md](glossary.md) | Case·Team·Capability·Action이 각각 무엇인가 |

## 한 문장

> 멀티에이전트를 **동작하게** 만드는 건 어렵지 않다. **믿을 수 있게** 만드는 게 어렵다.

이 문장은 도메인이 바뀌어도 그대로다. 우리가 파는 것은 새 모델도 새 RAG도 아니고 **검증·감시층**이다. 여행에서는 그것이 "외부가 만든 일정이 현실에서 성립하는지 확인하고, 여행이 끝날 때까지 변화를 먼저 잡는 것"이 된다(v11 §0-1).

## 이 영역이 정하는 것

여기서 정한 것이 다른 영역을 구속한다.

| 여기서 정하면 | 저기가 따라온다 |
|---|---|
| 자동화율을 앞세우지 않는다 | [../business/pricing.md](../business/pricing.md) 가격 논거가 오류 비용이 된다 |
| human-on-the-loop | [../../../final_project_cs/wiki/actions/index.md](../../final_project_cs/wiki/actions/index.md) 승인 경계 |
| 도메인 팩 교체 가능 | [../architecture/pack-model.md](../architecture/pack-model.md) |
| 페르소나 3인 | [../evaluation/golden-set.md](../evaluation/golden-set.md) 골든셋 구성 — `[실측]` 지금 골든셋 72건은 쇼핑몰이라 교체 대상 |

## 인접 영역

- [../business/index.md](../business/index.md) — 이 제품이 얼마짜리인가
- [../architecture/index.md](../architecture/index.md) — 어떻게 나눠 만드는가
- [../decisions/index.md](../decisions/index.md) — 제품 결정의 이유
- [pitch-questions.md](pitch-questions.md) — 심사에서 물어볼 다섯 가지와 답

- [vision-backlog.md](vision-backlog.md) — **지금은 안 하는 것들.** 항목마다 관측 가능한 도입 트리거가 붙어 있다

