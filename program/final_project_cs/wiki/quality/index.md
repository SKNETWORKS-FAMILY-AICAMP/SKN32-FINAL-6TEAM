---
type: guide
title: Quality
description: 무엇으로 보증하는가. 불변식 카탈로그·테스트 지도·평가 하네스·사각지대
status: draft
---

# Quality

**코드를 고치기 전에 [invariants.md](invariants.md)를 본다.**

## 읽기 순서

1. [invariants.md](invariants.md) — 깨면 안 되는 규칙 **51개**
2. [test-map.md](test-map.md) — 무엇을 어디서 검사하는가
3. [blind-spots.md](blind-spots.md) — 검사가 없는 지점
4. [eval-harness.md](eval-harness.md) — 평가 실행
5. [evidence.md](evidence.md) — **DoD 29항목의 실측 증거가 어디 있나**

## 각 문서

| 문서 | 답하는 질문 |
|---|---|
| [invariants.md](invariants.md) | 무엇을 깨면 안 되는가 |
| [test-map.md](test-map.md) | 이 규칙은 어느 테스트가 지키는가 |
| [blind-spots.md](blind-spots.md) | 어긴 걸 못 잡는 곳이 어딘가 |
| [eval-harness.md](eval-harness.md) | 평가를 어떻게 돌리는가 |
| **[evidence.md](evidence.md)** | **어느 DoD 가 무엇으로 증명됐고 어디가 낡았나** |
| **[guardrails.md](guardrails.md)** | **가드레일 수치 단일 출처.** 코드 두 곳에 나타나면 결함이다 |

## 테스트 현황

`[실측]` 2026-09-01 기준 70개 파일

| 분류 | 파일 | 무엇을 |
|---|---|---|
| `tests/unit` | 28 | 단위 |
| `tests/integration` | 22 | 통합 |
| `tests/contract` | 7 | 계약·격리·idempotency |
| `tests/e2e` | 4 | 종단 |
| `tests/security` | 4 | 인증·스코프·PII |
| `tests/architecture` | 2 | **계층 경계** |
| `tests/live` | — | 실 LLM 호출 |

## 불변식 현황

| 영역 | 총 | automated | 사람 판정 |
|---|---|---|---|
| 아키텍처 | 6 | 6 | 0 |
| Team 계약 | 5 | 2 | **3** |
| Action | 3 | 3 | 0 |
| 보안 | 8 | 8 | 0 |
| 도메인 검증 | 7 | 7 | 0 |
| Runtime | 20 | 20 | 0 |
| Context | 2 | 2 | 0 |
| **합계** | **51** | **48** | **3** |

**남은 사람 판정은 Team 경계 3개뿐이다.** import 검사로 자동화 가능해 보인다.

`[실측]` 2026-09-01 기준 **코드 역방향 표식 48개**가 붙었다. 양방향이 잠겼다.

```
코드에만 있는 ID  0개
문서에만 있는 ID  3개  ← 판정이 review 라 테스트가 없다
```

## 이 영역의 특징

**불변식이 문서에만 있는 게 아니라 테스트에 연결돼 있다.**

```markdown
| INV-CS-ARCH-001 | Core 계층은 도메인 어휘에 의존하지 않는다 | automated |
  tests/architecture/test_basement_is_domain_free.py::test_basement_layers_do_not_know_the_business_domain
```

문서가 "지켜주세요"라고 부탁하는 게 아니라 **실행이 막는다.**

## 자주 쓰는 명령

```bash
pytest tests/architecture
```

```bash
pytest tests/contract tests/security
```

```bash
python -m eval.run --arm Proposed
```

## 인접 영역

- [../../../program/wiki/evaluation/index.md](../../../wiki/evaluation/index.md) — 평가 지표와 프로토콜
- [../../../program/wiki/delivery/dod.md](../../../wiki/delivery/dod.md) — DoD
- [../teams/team-boundary.md](../teams/team-boundary.md) — Team 불변식의 설명
