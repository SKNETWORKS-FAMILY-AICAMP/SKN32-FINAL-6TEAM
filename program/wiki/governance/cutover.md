---
type: plan
title: 이 wiki 를 실제로 쓰기 시작하는 조건
description: 지금은 아무도 안 읽는다. 두 CLAUDE.md 어디에도 wiki 가 0회 나온다
status: draft
tags: [governance, documentation, release]
---

# 이 wiki 를 실제로 쓰기 시작하는 조건

`[실측]` 2026-09-03.

## ★ 지금 상태 — 아무도 안 읽는다

```
program/wiki/ 외 wiki 문서   220건
루트 CLAUDE.md 의 "wiki" 언급   0회
cs  CLAUDE.md 의 "wiki" 언급    0회
final_project_cs/wiki/          없음
```

**만든 220건에 진입 경로가 없다.** 실제 규칙 문서는 여전히 `CLAUDE.md` 와 `docs/` 다.

> **이관률은 아무도 안 보는 폴더에 내용을 옮긴 비율이다.**

**전환하기 전까지 그 숫자는 제품 가치가 아니다.**

## 왜 지금까지 program/ 에 뒀나

`[실측]` 사용자 지시였다.

> **원래 문서들은 지우지 말고, 얼마나 잘 구축되나 확인하려고 별도 폴더에 만들어라.**

**시험이 목적이었고 그건 끝났다.** 검증 9회를 돌렸고 검사기가 돈다.

## 전환에 필요한 것

### 1. 놓을 자리를 정한다

`[미확보]` **안 정했다.** `RULE.md` 4.2 와 부딪힌다.

| 안 | 대가 |
|---|---|
| `<저장소>/wiki/` | `docs/` 와 나란히. **`RULE.md` 파일명 규칙과 별개 트리가 된다** |
| `<저장소>/docs/wiki/` | `docs/` 안. **4.2 의 `YYYY-MM-DD_HHmm_` 규칙과 한 트리에서 섞인다** |
| `docs/` 를 대체 | 가장 깨끗하지만 **`docs/` 를 가리키는 모든 참조가 깨진다** |

→ [work-loop.md](work-loop.md) 의 파일명 절

### 2. `CLAUDE.md` 에 진입점을 넣는다

**Level 0 이 wiki 를 가리키지 않으면 아무 일도 안 일어난다.** → [structure-guide.md](structure-guide.md)

`[실측]` **이게 가장 작은 변경이고 가장 큰 효과다.** 한 줄이면 된다.

### 3. 상대경로 89곳을 고친다

`[실측]` wiki 문서가 **저장소를 넘나드는 링크 89곳**과 **실제 코드 경로 83곳**을 들고 있다.

```
program/wiki/architecture/core-design.md
  → ../../final_project_cs/wiki/runtime/…
```

`program/` 을 떠나면 **깊이가 바뀐다.** 스크립트로 고칠 수 있지만 **한 번에 해야 한다.**

### 4. `docs/` 와의 관계를 정한다

`[실측]` 지금은 **겹치는 폴더가 없다.**

| `docs/` | wiki |
|---|---|
| `evidence` · `handoff` · `manuals` · `plans` · `vision` | 대응 폴더 **0개** |

**우연이 아니다.** wiki 는 주제로 나누고 `docs/` 는 성격으로 나눈다.

| | 담는 것 |
|---|---|
| `docs/` | **작업 기록.** 언제 썼는지가 정보다 |
| `wiki/` | **현재 지식.** 언제 썼는지는 front matter 에 있다 |

**둘 다 남는 게 맞다.** 다만 **어느 쪽을 먼저 읽는지**를 `CLAUDE.md` 가 정해야 한다.

## ★ 전환은 한 번에 한다

**부분 전환을 하지 않는다.** → [`_migration/datasets/index.md`](../_migration/datasets/index.md) 의 같은 원칙

**절반만 옮기면 "여기는 어디에 적혀 있지"가 다시 생긴다.** 이 정리가 없애려던 바로 그 문제다.

## 전환 전까지 할 일과 안 할 일

| | |
|---|---|
| **한다** | 검사기 유지 · 낡음 검사 · **누락 대조** |
| **안 한다** | 대조 33건을 끝까지 갈아 넣기 |

`[실측]` **대조는 계속할 값이 있다.** 지금까지 9번에 9건이 나왔고, 그중엔 **법정 지연이자를 2.7배로 적을 뻔한 것**도 있었다. → [migration-scope/status.md](migration-scope/status.md)

**다만 그건 원본 문서를 고치는 값이지 전환을 앞당기지 않는다.**

## 결정이 필요하다

`[미확보]` **네 가지가 다 사람 판단이다.**

1. 놓을 자리 (`wiki/` vs `docs/wiki/`)
2. 전환 시점 (중간발표 2026-09-15 전 / 후)
3. `docs/` 와의 우선순위
4. 팀에게 언제 알릴지

**2번이 나머지를 정한다.** 발표 전이면 위험을 지고, 후면 그때까지 두 구조가 공존한다.

## 관계

- [structure-guide.md](structure-guide.md) — 배치 규칙
- [work-loop.md](work-loop.md) — `RULE.md` 파일명 규칙
- [migration-scope/status.md](migration-scope/status.md) — 이관 현황
- [migration.md](migration.md) — 이관 계획
