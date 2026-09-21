---
type: policy
title: 도메인 축
description: 이 문서가 도메인에 묶여 있는가를 front matter 에 적는다. 다음 교체 때 대상 목록이 grep 이 아니라 목록으로 나온다
status: draft
tags: [governance, documentation]
owners: [human:미배정]
impl_scope: cs — domain-swap.md 가 cs 에만 있다. sample 은 도메인 교체 대상이 아니라 계약 선검증체다
domain: neutral
domain_note: 도메인 교체 자체를 다루는 문서다. 두 도메인 어휘가 예시로 나온다
---

# 도메인 축

## 왜 생겼나

`[실측]` 2026-09-08 에 도메인이 **커머스 → 여행**으로 통째로 바뀌었다. 그런데 **어느 문서가 그 교체에 걸리는지 알 방법이 없었다.**

그래서 `grep "쇼핑몰\|주문\|배송"` 으로 훑었고, **grep 이 놓쳤다.**

| 놓친 문서 | 왜 놓쳤나 |
|---|---|
| `wiki/architecture/pack-model.md` | 구조 표가 `CS Pack` · `Commerce Ops Pack` 이라 **커머스 낱말이 한국어로 안 들어 있었다** |
| `wiki/architecture/index.md` | 같은 그림 |
| `wiki/architecture/diagrams.md` | 그림 라벨 안에만 있었다 |

`[실측 2026-09-09]` 그 결과 `wiki/architecture/` 10개 문서 중 **v10 을 인용하는 것이 0건**인 채로 하루가 지났다. 이게 세 번째 반복이다 — [drift-case-voc.md](drift-case-voc.md) 와 [`core-vs-team.md`](../architecture/core-vs-team.md) 의 「2026-09-03 정정」이 같은 기제다.

★**낱말을 뒤지는 방식은 도메인 교체에 안 맞는다.** 문서가 도메인에 묶여 있다는 사실은 **낱말이 아니라 성질**이고, 성질은 문서가 스스로 밝혀야 한다.

## 규칙

front matter 에 `domain:` 한 줄을 적는다.

```yaml
domain: neutral   # 또는 travel · commerce
```

| 값 | 뜻 | 도메인이 바뀌면 |
|---|---|---|
| `neutral` | **도메인이 바뀌어도 안 바뀐다.** 계약·생명주기·동시성·감사·거버넌스·평가 도구 | 손대지 않는다 |
| `travel` | **지금 도메인에 묶여 있다.** Team 명세·분류 라벨·골든셋·페르소나·업무 어휘 | **다시 쓴다** |
| `commerce` | **지난 도메인의 문서.** 그때 무엇이었는지를 말한다 | 안 고친다. 기록이다 |

`wiki/records/` 아래는 적지 않는다. 기록은 전부 그때의 도메인이고 안 고친다.

### 판정 질문 하나

> **도메인을 갈아 끼웠을 때 이 문서를 다시 읽어야 하는가?**

읽어야 하면 그 도메인 이름을, 안 읽어도 되면 `neutral` 이다.

★**애매하면 도메인 이름 쪽으로 적는다.** `neutral` 을 잘못 적으면 **교체 때 조용히 빠진다** — 지금까지 난 사고가 전부 이쪽이다. 반대로 잘못 적어 봐야 다음 교체 때 한 번 더 읽는 것뿐이다.

## 검사

```bash
python program/scripts/check_wiki.py
```

| 검사 | 판정 |
|---|---|
| `domain:` 값이 `neutral`·`travel`·`commerce` 밖 | **위반** |
| `domain: neutral` 인데 도메인 업무 어휘가 3회 이상 | **위반** — 주장이 거짓이다 |
| `domain:` 없음 | 위반 아님. **집계로만 낸다** |

세 번째를 위반으로 안 만든 이유는 251개 문서가 한꺼번에 붉어지면 아무도 안 고치기 때문이다. 대신 매 실행마다 미표시 개수가 찍힌다.

### 면제

`neutral` 인데 도메인 어휘가 정당하게 나오는 경우가 있다 — 판올림 자체를 설명하는 문서, 두 도메인을 비교하는 표.

```yaml
impl_scope: cs — domain-swap.md 가 cs 에만 있다. sample 은 도메인 교체 대상이 아니라 계약 선검증체다
domain: neutral
domain_note: 커머스↔여행 대조표를 싣는 문서다. 기제는 도메인 무관이다
```

`size_exempt_reason` 과 같은 방식이다. **이유 없이 면제하지 않는다.**

### 교체 때 쓰는 명령

```bash
python program/scripts/check_wiki.py --domain travel
```

**그 도메인에 묶인 문서 목록이 나온다.** 이게 다음 교체의 작업 목록이다.

★**미표시 문서는 이 목록에 안 들어 있다.** 목록이 완전해지기 전까지는 grep 을 같이 돌려야 한다 — 명령이 그렇게 경고한다.

## 어휘 목록은 지우지 않고 더한다

검사기의 `DOMAIN_VOCAB` 은 도메인마다 한 벌씩 쌓인다. **커머스 벌을 지우면** 커머스 어휘가 `neutral` 문서로 다시 새 들어와도 안 잡힌다.

★**코드 쪽 `DOMAIN_WORDS`(`test_basement_is_domain_free.py`)도 같은 규칙이다.** `[실측 2026-09-09]` 지금 그쪽에는 여행 어휘가 **0개**다 — 커머스 어휘만 막고 있다. 코드 수정은 담당 세션 몫이다.

## 옛 도메인 값은 두 부류다

`domain:` 이 지금 도메인(`travel`)도 `neutral` 도 아니면 검사기가 **이유가 붙어 있는지**로 가른다.

| | 뜻 | 검사기 출력 |
|---|---|---|
| `domain_note` **있음** | 그때의 기록이거나, 그 도메인이 맞는 문서(커머스 데이터셋 문서 등) | "그대로 둔다" |
| `domain_note` **없음** | **판올림을 못 따라간 것.** 다시 써야 한다 | ★"옛 도메인인데 이유가 없다" |

★**이 줄이 이 규칙의 실제 산출물이다.** 지금까지는 "어느 문서가 낡았나"를 물으면 grep 을 돌려야 했고 답이 매번 달랐다. 이제 검사기가 목록을 준다.

## 지금 상태

`[실측 2026-09-09]` 검사기 실행 결과가 정본이다. 아래는 신설 당일 값이다.

| | |
|---|---|
| 비-기록 문서 | 252개 — **전부 표시됨 (100%)** |
| `neutral` | 169 |
| `travel` | 19 |
| `commerce` | 64 — 이유 있음 34 · **이유 없음 30** |
| 기록(`records/`) | 800개 — 대상 아님 |

★**첫 표시는 낱말 세기로 초벌을 냈고 실제로 판정한 것만 손으로 덮었다**(아키텍처 10 · 여행 Team 5 · 진입점 5 · 교체를 다루는 문서 6 · 커머스 Team 7 등 50여 개). **나머지는 초벌이라 틀린 것이 섞여 있다.** 문서를 만질 때 그 문서의 `domain:` 을 같이 확인한다 — 특히 `neutral` 은 틀리면 다음 교체에서 조용히 빠지므로 의심되면 도메인 이름 쪽으로 고친다.

## 이 규칙이 못 하는 것

| | |
|---|---|
| **내용이 낡았는지는 모른다** | `domain: travel` 이 붙어 있어도 그 안이 **옛 판(v10) 여행 명세**일 수 있다. `[정정 2026-09-10]` 「v9 여행 명세」로 적혀 있었다 — **v9 는 커머스**다. 이 축은 **대상 목록**을 주지 판정을 하지 않는다 |
| **`neutral` 오표시를 완전히는 못 잡는다** | 업무 어휘를 안 쓰면서 도메인에 묶인 문서가 있을 수 있다 — 위 `pack-model.md` 가 정확히 그런 경우였다. 그래서 **사람이 붙이는 표시**가 필요하다 |
| **판올림 반영 여부는 안 본다** | **현재 기준선(지금 v11)**을 인용하는지는 [drift-check](../../program/scripts/check_drift.py) 쪽 일이다 |

## 관계

- [`cs/domain-swap.md`](../../final_project_cs/wiki/domain-swap.md) — **무엇을 갈아 끼우고 무엇을 안 끼우나.** 이 축은 그 목록을 문서 단위로 옮긴 것이다
- [drift-case-voc.md](drift-case-voc.md) — 정정이 한 곳에만 가는 사고
- [document-standard.md](document-standard.md) — 문서 표준
- [front-matter.md](front-matter.md) — front matter 필드
- [../architecture/pack-model.md](../architecture/pack-model.md) — 교체가 성립하는 조건
