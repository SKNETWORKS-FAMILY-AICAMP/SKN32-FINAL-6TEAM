---
type: guide
title: 자동 생성물
description: 도장이 만드는 문서는 손으로 고치지 않는다. 명령과 입력만 기록한다
status: draft
tags: [testing, documentation]
owners: [process:dojo-report]
---

# 자동 생성물

## 무엇을 만드나

| 산출물 | 명령 | 위치 |
|---|---|---|
| 테스트 사각지대 실측 | `acop-dojo report` | `program/research/테스트_사각지대_실측.md` |

원본 카탈로그는 `acop_dojo/acop_dojo/defects/catalog.json`이다.

## 손으로 고치지 않는다

```yaml
automation:
  command: acop-dojo report
  owner: process:dojo-report
  manual_edit: false
```

**고쳐야 하면 카탈로그나 생성 스크립트를 고친다.** 산출물을 고치면 다음 생성 때 사라진다.

루트 `CLAUDE.md`도 같은 말을 한다.

> 손으로 고치지 않는다.

## 생성물에 반드시 있는 것

`[실측]` 지금 리포트가 갖춘 것들. **이 형태를 유지한다.**

| 항목 | 왜 |
|---|---|
| 대상 revision | `git:04f6634` — 어느 코드에 대한 결과인지 |
| 기준선 | `486 passed, 4 deselected, 1 xfailed` — 비교 대상 |
| 방법 | 최소 변경을 사본에 적용하고 전체 테스트 |
| **분모에서 뺀 것과 이유** | 안 밝히면 0이 무엇에 대한 0인지 모른다 |
| **이 숫자가 아닌 것** | "커버리지가 아니다"를 명시 |

**뒤의 둘이 이 생성물의 정직함이다.**

## ★ 분모를 밝히는 규칙

`[실측]` 리포트 원문.

> 뺀 것을 밝히지 않으면 0이라는 수치가 무엇에 대한 0인지 알 수 없다.

현재 1건이 빠져 있다. `INV-CLASS-002`는 **관찰 가능한 동작이 안 바뀌는 중복 방어 제거**(subsumed mutant)라 신호가 안정적이지 않다.

**빼는 건 괜찮다. 안 밝히는 게 문제다.**

## 커버리지가 아니다

> 이 숫자는 저장소의 테스트 커버리지가 아니다. **사람이 고른 48개 가설에 대한 검출률**이다. 카탈로그에 없는 규칙은 여전히 보이지 않는다.

**0건 생존이 안전을 뜻하지 않는다.** 우리가 물어본 48가지에 대해서만 0건이다.

## 카탈로그를 늘리는 규칙

> 새 규칙을 만들 때 **그 규칙을 어기는 변경도 함께 만들어** 게이트에 걸어 본다. 규칙만 늘리고 세는 곳을 안 만들면 다시 벌어진다.

**불변식을 추가할 때 결함도 같이 추가한다.**

`[미확보]` 지금 겨냥해야 할 것은 사람 판정에 의존하는 3개다.

```
INV-CS-TEAM-003  side effect 를 실행하지 않는다
INV-CS-TEAM-004  read 도구를 직접 호출하지 않는다
INV-CS-TEAM-005  다른 Team 을 직접 호출하지 않는다
```

**셋 다 심을 결함은 만들 수 있는데 잡을 테스트가 없다.** 카탈로그에 올리면 생존한다.

## 재현성

`trace --verify`와 `scenarios --verify-all`이 **두 번 떠서 같은지 검사한다.**

재현되지 않는 트레이스는 학습 자료로 못 쓴다.

## 관계

- [guide.md](guide.md) — 명령
- [index.md](index.md) — 도장이 무엇인가
- [../../final_project_cs/wiki/quality/blind-spots.md](../../final_project_cs/wiki/quality/blind-spots.md) — 산출물 요약
- [../../wiki/governance/document-standard.md](../../wiki/governance/document-standard.md) — 자동 생성 문서 규칙
