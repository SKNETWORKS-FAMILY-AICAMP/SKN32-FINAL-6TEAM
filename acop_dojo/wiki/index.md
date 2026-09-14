---
type: guide
title: acop_dojo 지식 지도
description: cs의 구조와 동작을 실행 증거로 배우는 학습 프로그램. 부산물로 테스트 사각지대를 찾아낸다
status: draft
domain: neutral
---

# acop_dojo 지식 지도

`final_project_cs`의 구조와 동작을 **실행 증거로** 배우는 학습 프로그램이다.

**정답은 pytest와 실측 실행 트레이스가 판정한다.** 원본 저장소는 건드리지 않고 임시 사본에서만 결함을 적용한다.

## 지금 범위 — 베이스먼트만 (2026-09-14)

`[결정 2026-09-14]` 제품 도메인이 커머스에서 여행으로 바뀌었다. 도장은 도메인을 모르는 코어(베이스먼트)만 다룬다 — Case 생명주기, 계약, Controller·Registry, 동시성·멱등성·바깥함, 검증 엔진. 커머스 Team 을 겨누던 결함 10 · 시나리오 8 · 트랙 3 · 원장 규칙 5는 **지우지 않고 중지했다.** 보스전은 검증 엔진(`app/core/verification.py`)으로 옮겼다 — 도메인이 바뀌어도 안 바뀌는 쪽이다. 자세한 것은 [guide.md](guide.md).

도장이 만들다 찾은 cs 쪽 문제 중 직접 고치지 않는 것은 [handoff-2026-09-14.md](handoff-2026-09-14.md)에 담당별로 넘겼다(멱등 키 대상 · 결정 15 기동 중단 · RAG 외부 의존 · 리포트 상태 표시 · 낡은 문서, 그리고 결정이 필요한 둘).

`[실측 2026-09-14]` 결함 게이트는 **결함 없이도 깨지는 테스트를 기준선으로 빼고** 새 실패만 센다. 그날 기준선 실패 5건 — RAG 3건(외부 API 잔액 소진), 디버그 리포트 상태 표시 1건(다른 작업), API 키 파일 1건(사본에 `.git` 이 없어서). 전에는 기준선이 하나라도 깨지면 게이트가 멈추고 **빈 결과로 카탈로그를 덮어써** 39건 기록이 지워졌다. 둘 다 고쳤다.

## 어떻게 동작하는가

```text
원본 cs 저장소
   ↓ 사본 생성 (원본 불변)
임시 사본
   ↓ 결함 패치 적용
결함이 있는 사본
   ↓ pytest 실행
테스트가 우는가?
   ├─ 운다  → 정상. 그 불변식은 지켜지고 있다
   └─ 안 운다 → ★ 테스트 사각지대
```

## ★ 부산물이 더 중요할 수 있다

결함 카탈로그의 **등록 게이트**가 부산물로 **테스트 사각지대**를 찾아낸다.

**불변식을 어겼는데 테스트가 울지 않는 지점**의 목록이 나온다. 이건 사람이 찾기 어려운 종류의 정보다.

```bash
python dojo.py report
```

목록은 `program/research/테스트_사각지대_실측.md`에 있다. **손으로 고치지 않는다.**

## 자동 생성 문서

`[정정 2026-09-10]` 「이 저장소가 만드는 문서는 전부 재생성 대상」은 넓었다 — **`python dojo.py report` 가 쓰는 것은 보고서 하나**(`program/research/테스트_사각지대_실측.md`, `cli.py` 의 `cmd_report`)다. **이 wiki 의 문서는 손으로 쓴다** — 재생성 대상이 아니다.

```yaml
automation:
  command: python dojo.py report
  owner: process:dojo-report
  manual_edit: false
```

**손으로 고치면 다음 생성 때 사라진다.** 고쳐야 하면 생성 스크립트를 고친다.

→ [중앙 허브 문서 표준](../../wiki/governance/document-standard.md)

## 불변식과의 관계 — 원장이 둘이다

`[실측]` 2026-09-06 정정. **이 절이 "cs 카탈로그에 33개, 26 automated, 사람 판정 7(Runtime 4·Team 3)"이라고 적고 있었다. 둘 다 틀렸다.**

| | 어디 | 몇 개 |
|---|---|---|
| **dojo 원장** | `acop_dojo/data/invariants.json` | 활성 규칙 **33개** — 전부 결함이 하나 이상 붙어 있다 |
| **cs wiki 카탈로그** | [invariants.md](../../final_project_cs/wiki/quality/invariants.md) | 60개 넘는 ID. **review는 셋뿐** — `INV-CS-TEAM-003`·`004`·`005` |

33은 cs 카탈로그가 아니라 **dojo 자기 원장의 수**였고, "Runtime 4개 사람 판정"은 [shared-state.md](../../final_project_cs/wiki/runtime/shared-state.md)가 `INV-CS-RT-001~004`에 잘못 붙였던 문장에서 온 것이다 — 정본은 넷 다 automated다. **dojo가 겨냥할 사람 판정 규칙은 Team 계약 셋이다.** → [generation.md](generation.md)

`[실측]` [README](../README.md). 처음 원장을 만들었을 땐 9개 규칙이 비어 있었다. 그 9개에 결함을 만들어 걸어 보니 **5개는 이미 테스트가 잡고 있었고 4개는 안 잡혔다** — 비어 있던 규칙이 잡히는 결함으로 바뀌는 것이 진전이다. 생존한 결함은 무엇을 테스트해야 하는지 알려주지만, 결함이 없는 규칙은 아무것도 알려주지 않는다.

> **"생존 0건"은 결함이 붙은 규칙에 한한 이야기다.** 원장이 그 분모를 드러낸다.

## [2026-09-02 추가] 설계 근거

| 문서 | 무엇 |
|---|---|
| [learning-methodology.md](learning-methodology.md) | 교수법 10가지와 각각의 출처 |
| [design-review.md](design-review.md) | **치명적 약점 7가지.** 그대로 구현할 단계가 아니라는 판정 |
| [trace-review.md](trace-review.md) | 추적 화면 교차검증. 지적 6개 중 4개는 이미 고쳐졌다 |

## 관계

- [../../final_project_cs/wiki/quality/invariants.md](../../final_project_cs/wiki/quality/invariants.md) — 검증 대상 불변식
- [../../final_project_cs/wiki/quality/blind-spots.md](../../final_project_cs/wiki/quality/blind-spots.md) — 사각지대 목록
- [../../wiki/architecture/repository-map.md](../../wiki/architecture/repository-map.md) — 저장소 관계
