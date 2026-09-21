---
type: guide
title: v8 분할 초안
description: 1,517줄 계획서를 28개 파일로 쪼갠 스테이징. 아직 wiki 본체가 아니다
status: draft
tags: [governance, documentation]
owners: [human:미배정]
domain: neutral
domain_note: 이관 전 스테이징 사본이다. 원문을 형식만 바꿔 담아 둔 곳이라 고치지 않는다
---

# v8 분할 초안

**여기는 스테이징이다. wiki 본체가 아니다.**

```bash
python program/scripts/split_v8.py --write
```

원본 `program/plan/archive/A-COP_구현계획서_v8.md`는 **읽기만 했다.** `md5 = 20159eb2…` 그대로다.

## 왜 따로 두나

**바로 wiki 본체에 넣으면 안 된다.** 이미 쓴 문서와 중복되기 때문이다.

```
wiki/product/positioning.md        ← 내가 쓴 것
wiki/_migration/v8/product/positioning.md   ← v8 §1·§4 원문
```

**두 개를 나란히 놓고 합쳐야** 무엇이 빠졌는지 보인다. 이관에서 세 번 누락을 찾은 방법이 그것이다.

## 결과

`[실측]` 42개 절 → **28개 파일**

| | 절 |
|---|---|
| 옮김 | 36 |
| 건너뜀 | 6 |
| **매핑 없음** | **0** |

### 목표 영역별

| 영역 | 파일 | 큰 것 |
|---|---|---|
| `architecture/` | 9 | external-ai 183줄 · pack-model 143줄 · core-design 129줄 |
| `product/` | 5 | positioning 62줄 · goals 41줄 |
| `delivery/` | 5 | dod 36줄 · roles 27줄 |
| `cs/` | 5 | team-contract **110줄** |
| `decisions/` | 2 | D-005 근거 게이트 46줄 |
| `research/` | 1 | graphrag 96줄 |
| `evaluation/` | 1 | protocol **101줄** |

## 건너뛴 6절

| 절 | 왜 |
|---|---|
| §0 문서 상태 | wiki는 `log.md`가 대신한다 |
| §0-1 한 줄 요약 | `quickstart.md`가 대신한다 |
| §0-2 절 색인 | `index.md`가 대신한다 |
| §17 개인 어필 문장 | 문서 표준 범위 밖 |
| §28 엑셀 입력용 요약 | 제출 양식. 별도 관리 |
| 참고 출처 | 각 문서의 `sources`로 분산 |

**앞의 셋이 재미있다.** v8이 한 파일이라 스스로 해야 했던 일을 **wiki 구조가 대신한다.**

## 다음 — 합치기

파일마다 이 순서로 본다.

```
1. 기존 wiki 문서와 나란히 놓는다
2. v8 에만 있는 내용을 찾는다      ← 여기가 핵심
3. 기존 문서에 합친다
4. 이 스테이징 파일을 지운다
```

**2번을 건너뛰면 안 된다.** 이관에서 세 번 다 여기서 누락이 나왔다.

### 합칠 우선순위

| 순위 | 파일 | 왜 |
|---|---|---|
| 1 | `cs/teams/team-contract/index.md` (110줄) | 계약 전문. 기존 문서가 요약본이다 |
| 2 | `evaluation/protocol.md` (101줄) | 평가 설계 전문 |
| 3 | `architecture/external-ai.md` (183줄) | §9-C 판별표는 이미 합쳤다. 나머지 확인 |
| 4 | `architecture/core-design.md` (129줄) | Core 8개 구성요소. wiki에 아직 얇다 |
| 5 | `architecture/pack-model.md` (143줄) | 기존 문서와 중복 많을 것 |

## 남은 것

| 항목 | 상태 |
|---|---|
| 28개 파일 합치기 | 시작 안 함 |
| 스테이징 정리 | 합친 뒤 |
| 원본 v8 처리 | `[미확보]` 보존할지 폐기할지 |

`[미확보]` **원본을 어떻게 할지 안 정했다.** 다른 문서와 티켓이 `v8 §21` 식으로 참조하고 있어서 그냥 지우면 안 된다.

## 관계

- [../../governance/migration-scope/index.md](../../governance/migration-scope/index.md) — 이관 범위
- [../../governance/document-standard.md](../../governance/document-standard.md) — 분할 트리거
- [../../index.md](../../index.md) — wiki 본체
