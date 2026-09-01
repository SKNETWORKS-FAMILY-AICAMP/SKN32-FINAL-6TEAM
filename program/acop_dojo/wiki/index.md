---
type: guide
title: acop_dojo 지식 지도
description: cs의 구조와 동작을 실행 증거로 배우는 학습 프로그램. 부산물로 테스트 사각지대를 찾아낸다
status: draft
---

# acop_dojo 지식 지도

`final_project_cs`의 구조와 동작을 **실행 증거로** 배우는 학습 프로그램이다.

**정답은 pytest와 실측 실행 트레이스가 판정한다.** 원본 저장소는 건드리지 않고 임시 사본에서만 결함을 적용한다.

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

이 저장소가 만드는 문서는 전부 재생성 대상이다.

```yaml
automation:
  command: python dojo.py report
  owner: process:dojo-report
  manual_edit: false
```

**손으로 고치면 다음 생성 때 사라진다.** 고쳐야 하면 생성 스크립트를 고친다.

→ [중앙 허브 문서 표준](../../wiki/governance/document-standard.md)

## 불변식과의 관계

cs의 [불변식 카탈로그](../../final_project_cs/wiki/quality/invariants.md)에 33개가 있고 그중 26개가 automated다.

**나머지 7개가 dojo가 겨냥할 대상이다.** 사람 판정에 의존하는 규칙은 결함을 넣어도 테스트가 안 운다.

| 영역 | 사람 판정 |
|---|---|
| Runtime | 4개 |
| Team 계약 | 3개 |

## 관계

- [../../final_project_cs/wiki/quality/invariants.md](../../final_project_cs/wiki/quality/invariants.md) — 검증 대상 불변식
- [../../final_project_cs/wiki/quality/blind-spots.md](../../final_project_cs/wiki/quality/blind-spots.md) — 사각지대 목록
- [../../program/wiki/architecture/repository-map.md](../../wiki/architecture/repository-map.md) — 저장소 관계
