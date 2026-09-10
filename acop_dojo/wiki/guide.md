---
type: guide
title: 도장 사용법
description: 트랙 7개와 명령. 정답은 pytest와 실측 트레이스가 판정한다
status: draft
tags: [testing, documentation]
owners: [human:미배정]
domain: neutral
---

# 도장 사용법

`acop_dojo/`

`final_project_cs`의 구조와 동작을 **실행 증거로** 배우는 학습 프로그램이다.

## 명령

`[실측]`

| 명령 | 하는 일 |
|---|---|
| `doctor` | 대상 저장소·파이썬·테스트 수집 점검 |
| `trace [--verify]` | 시나리오 트레이스를 뜬다. `--verify`는 두 번 돌려 같은지 본다 |
| `learn 0` | 해설된 완주. 채점 없음 |
| `learn 1` | 복원 — 빈칸에 들어갈 함수를 고른다 |
| `learn 2` | 대조 — 예상 순서를 세우고 실측과 겹친다 |
| `defect [ID] [--fix 패치]` | 결함 문제. `--fix`를 주면 pytest가 판정한다 |
| `boss [--fix 패치]` | 보스전 — **안 배운 모듈에서 같은 규칙**을 찾고 고친다 |
| `tracks` | 학습 트랙 7개 |
| `placement --track X` | 어디부터 시작할지 실측 문제로 잰다 |
| `scenarios [--verify-all]` | 시나리오 목록. 전부 두 번 떠서 같은지 검사 |
| `answers` | 서술 답안을 동료 검토용 루브릭과 함께 내보낸다 |
| `review` | 예약된 복습 — **같은 규칙을 다른 코드에서 묻는다** |
| `status` | 진행 상황 |
| `report` | [테스트 사각지대 실측](../../final_project_cs/wiki/quality/blind-spots.md) 생성 |
| `invariants` | 규칙 원장과 결함 카탈로그가 맞는지 본다 — **0.3초** |
| `patches` | 결함 patch가 아직 유효한지 본다 — **4초, 테스트 안 돌림** |
| `defects [--rebuild] [--only ID,ID]` | 결함 카탈로그 등록 게이트 — **20분** |
| `stability [--repeats N]` | 결함이 매번 같은 신호를 내는지 |
| `map` | 웹 지도. 간선이 숨겨져 있다 — 아래 |

`[실측]` 2026-09-06 [README](../README.md)와 대조해 위 다섯을 채웠다. `boss`에는 `--defect ID`·`--force`도 있다. 파이썬 3.12 이상(`sys.monitoring`)과 대상 저장소의 PostgreSQL이 필요하다 — 470개 테스트 중 상당수가 DB를 쓴다.

**세 명령의 시간 차이가 쓰는 순서를 정한다.** `invariants`(0.3초) → `patches`(4초) → `defects`(20분). 전체 게이트는 매번 돌릴 수 없어서 앞 둘이 있다.

## ★ `--verify`가 두 번 돌린다

`trace --verify`와 `scenarios --verify-all`이 **같은 것을 두 번 떠서 비교한다.**

**트레이스가 재현되지 않으면 학습 자료로 쓸 수 없다.** 매번 다른 걸 보여주면 무엇이 규칙이고 무엇이 우연인지 구분이 안 된다.

## 트랙 7개

`[실측]` 전체 1개와 파트 6개.

**경계를 사람이 아니라 디렉터리로 긋는다.** `docs/handoff/05_분업_규칙.md`가 같은 이유로 그렇게 한다.

| 트랙 | 담당 | 반드시 설명할 수 있어야 하는 것 |
|---|---|---|
| `all` | 전원 | Case가 만들어지고 라우팅되고 처리된 뒤 닫히는 전 구간 |
| `core1` | 코어 1 | **상태는 이벤트를 접은 결과다.** `transition_case`만이 상태를 바꾼다 |
| `core2` | 코어 2 | 같은 요청을 열 번 보내도 side effect는 한 번. scope 없는 호출은 거부 |
| `team-voc` | 팀 모듈 1 | 분류 실패를 조용히 넘기지 않는다. 배치는 tenant 안에서 멱등 |
| `team-review` | 팀 모듈 2 | 근거 없는 답변을 만들지 않는다. PII는 재시도하지 않고 넘긴다 |
| `team-commerce` | 팀 모듈 3 | Team은 side effect를 실행하지 않는다. 정책 값을 바꾸지 않는다 |

★`[실측 2026-09-10]` **팀 트랙 셋(`team-voc`·`team-review`·`team-commerce`)의 대상 코드가 cs 작업 트리에서 지워졌다.** 결함 카탈로그(`acop_dojo/defects/catalog.json`) **49개 중 10개 = 20%** 가 `app/modules/customer_ops/*` 를 가리킨다 — INV-CLASSIFY-001 · INV-COMMERCE-002~005 · INV-REVIEW-002 · INV-TEAM-001·002 · INV-VOC-001·002. **지금 cs 에 대면 이 열 개는 대상 파일이 없어 적용되지 않는다.** 그중 인라인 분류(`feedback.py`)는 지워진 게 아니라 `travel_ops/` 로 옮겨졌으니 **경로만 바꾸면 산다.** `[미확보]` 나머지 아홉을 여행 Team 으로 옮길지 버릴지는 dojo 담당 몫이다.
| `front` | 프론트 | 근거 없는 제안은 화면에서 결정할 수 없어야 한다 |

`[실측]` 이 표가 "7개"라면서 `front`를 빼고 6개만 적고 있었다(2026-09-06 정정). 트랙마다 자기 시나리오·결함·지도가 붙는다 — `--track core2`처럼 준다.

`[추정]` **팀 모듈 3분할은 저장소에 사람 배정 문서가 없어 모듈 성격으로 나눈 것이다.** 담당이 다르면 `acop_dojo/tracks.py`의 `owns`만 고치면 결함·지도·시나리오가 따라온다.

**각 트랙의 "설명할 수 있어야 하는 것"이 그대로 불변식이다.** → [../../final_project_cs/wiki/quality/invariants.md](../../final_project_cs/wiki/quality/invariants.md)

## 지도는 먼저 그려 보고 대조한다

`map`을 열면 실측 호출 간선이 **숨겨져 있다.** 요청이 지나갈 모듈을 순서대로 눌러 예상을 만든 다음 "실측과 대조"를 누른다. 그때 간선이 열리고 **빠뜨린 것과 없는데 넣은 것**이 나온다.

**보기만 하는 시각화는 효과가 약하고, 조작하거나 답할 때 효과가 난다** — [design-review.md](design-review.md) 권고 4(읽기 전용 그래프 → 가설 검증 지도)가 이렇게 반영됐다.

## 보스전이 핵심이다

`boss`는 **안 배운 모듈에서 같은 규칙을 찾아 고치게 한다.**

`learn`과 `defect`가 "이 코드에서 이 규칙"이라면, `boss`는 **"규칙을 이해했는가"**를 묻는다.

같은 규칙을 다른 자리에서 못 찾으면 외운 것이지 안 게 아니다.

`review`도 같은 원리다 — **예약된 복습에서 같은 규칙을 다른 코드로 묻는다.**

## 정답은 사람이 안 정한다

```
pytest 통과 여부
실측 실행 트레이스
```

**둘이 판정한다.** 그래서 `defect --fix`에 패치를 주면 채점이 자동이다.

## 원본을 안 건드린다

**임시 사본에서만 결함을 적용하고 되돌린다.**

`[실측]` 사각지대 리포트가 그 사실을 명시한다.

> 원본 저장소는 건드리지 않았다. 사본에서만 적용하고 되돌렸다.

## 관계

- [index.md](index.md) — 도장이 무엇인가
- [generation.md](generation.md) — 자동 생성물
- [../../final_project_cs/wiki/quality/blind-spots.md](../../final_project_cs/wiki/quality/blind-spots.md) — 부산물
- [../../final_project_cs/wiki/quality/invariants.md](../../final_project_cs/wiki/quality/invariants.md) — 트랙이 겨냥하는 규칙
