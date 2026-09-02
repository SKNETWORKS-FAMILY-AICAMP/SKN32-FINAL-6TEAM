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
final_project_sample/wiki/      없음
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

`[실측]` 2026-09-03 스크립트로 다시 셌다. **앞서 89곳으로 적은 건 `program/wiki/*/` 한 층만 센 값이었다.**

```bash
python program/scripts/cutover_rewrite.py
```

| 무엇 | 곳 |
|---|---|
| **깊이가 바뀌는 링크** | **305** |
| 코드·원본 문서 참조 | **224** |

저장소별로는 이렇다.

| | 링크 |
|---|---|
| `program/wiki` | 138 |
| `program/final_project_cs/wiki` | 110 |
| `program/final_project_sample/wiki` | 15 |
| `datasets`·`acop_dojo` | 42 |

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

## ★ [2026-09-03] 시점이 정해졌다 — 발표 후

> **중간발표(2026-09-15) 이후에 전환한다.** → [D-012](../decisions/D-012-cutover-timing.md)

**그때까지 두 구조가 공존한다.**

### 남은 결정 셋

`[미확보]` 발표 후에 정한다.

1. **놓을 자리** — `<저장소>/wiki/` vs `docs/wiki/`
2. `docs/` 와의 읽기 순서
3. 팀에 알릴 시점

### 그때까지 하는 것

| 한다 | 안 한다 |
|---|---|
| 남은 대조 33건 | 저장소로 옮기기 |
| 검사기 유지 · 낡음 검사 | `CLAUDE.md` 진입점 추가 |
| ~~경로 재작성 스크립트 준비~~ **완료** | **그 스크립트 실행** |

**세 번째가 중요하다.** 도구는 미리 만들고 **실행만 미룬다.**

## 관계

- [structure-guide.md](structure-guide.md) — 배치 규칙
- [work-loop.md](work-loop.md) — `RULE.md` 파일명 규칙
- [migration-scope/status.md](migration-scope/status.md) — 이관 현황
- [migration.md](migration.md) — 이관 계획
