---
type: guide
title: 팀 코드·시험을 두는 자리
description: Activity·Dining·Mobility 가 각자 폴더에서 작업하는 규칙. 파일 하나·폴더·파일+엔진 세 방식 모두 같은 등록 문자열로 불리고 같은 시험을 통과한다
status: draft
tags: [agent]
owners: [human:미배정]
domain: travel
---

# 팀 코드·시험을 두는 자리

`[2026-09-28]` 세 팀(Activity·Dining·Mobility)이 각자 폴더에서 작업한다. 이 문서는 **어디에 두면 시험이 통과하는지**만 적는다.

## 코드 — `app/modules/travel_ops/<팀>/`

`develop` 은 세 팀을 폴더로 옮겨 두었다. 본체는 `team.py`, 입구 `__init__.py` 는 다시 내보내기만 한다.

```
app/modules/travel_ops/
  activity/   __init__.py  team.py   (+ 이 팀의 도우미 파일·하위 폴더)
  dining/     __init__.py  team.py
  mobility/   __init__.py  team.py
  mobility_engine/ ...               (Mobility 가 따로 둔 엔진 — 다른 이름이라 허용)
```

**세 방식 모두 허용한다.** 등록 문자열(`config/project.yaml` 의 `app.modules.travel_ops.activity:ActivityTeam`)은 어느 방식이든 그대로다.

| 방식 | 모양 | 조건 |
|---|---|---|
| 폴더 | `activity/__init__.py` + `team.py` | `__init__.py` 에서 클래스를 다시 내보낸다. 본체를 `__init__.py` 에 직접 써도 된다 |
| 파일 하나 | `activity.py` | 예전 방식 그대로 |
| 파일 + 엔진 | `mobility.py` + `mobility_engine/` | 엔진 폴더는 **팀 이름과 다른 이름**으로 |

★**하면 안 되는 것 하나 — 같은 이름의 파일과 폴더를 같이 두지 않는다.** `activity.py` 와 `activity/` 가 같이 있으면 파이썬은 폴더를 불러오고 파일은 **오류 없이 무시한다.** 병합 충돌을 풀다가 둘 다 남기기 쉽다. [`tests/contract/test_team_layout.py`](../../tests/contract/test_team_layout.py) 가 막는다.

★**폴더 안 `.py` 는 전부 팀 코드로 본다.** 인프라 직접 import 금지(DoD-22) 검사가 팀 폴더를 통째로 훑는다 — 옆 파일로 옮겨도 규율은 같다([`test_team_tool_discipline.py`](../../tests/contract/test_team_tool_discipline.py)). 전에는 등록 문자열을 `activity.py` 경로로만 바꿔 찾아서, 폴더로 옮기면 이 검사가 실패했다(2026-09-28 고침).

## 시험 — 두 자리 다 CI 가 돌린다

| 자리 | 누가 쓰나 | CI |
|---|---|---|
| `final_project_cs/tests/unit/travel/<팀>/` | 권장. 공용 가짜 도구는 `from ..helpers import ...` | develop·main 의 cs 시험 단계 |
| 저장소 맨 위 `tests/<팀>/` | Mobility 방식 | develop·main 의 「팀 시험(저장소 맨 위 tests/)」 단계 |

여러 팀을 함께 보는 시험(예: `test_evidence_accumulates.py`)은 `tests/unit/travel/` 에 그대로 둔다.

★**저장소 맨 위 `tests/` 는 pytest 형식만 CI 가 확인한다.** `def test_...` 함수가 없거나 불러오는 순간 `sys.exit()` 가 도는 스크립트 방식 파일은 모으지 않고 끝에 목록만 보인다([`tests/conftest.py`](../../../tests/conftest.py)). `[실측 2026-09-28]` `role-mobility` 의 13개 파일 중 6개가 스크립트 방식이었다 — CI 가 보게 하려면 함수로 바꾼다. 시간표 같은 데이터가 없으면 시험 스스로 건너뛰는 것(`skip`)은 실패가 아니다.

## 확인한 것

`[실측 2026-09-28]` 임시 사본에서 방식을 바꿔 가며 돌렸다.

| 사본 | 결과 |
|---|---|
| Activity 파일 하나 · Dining 폴더 · Mobility 파일+엔진 | 구조 관련 시험 687 통과 |
| 팀원 브랜치의 `activity/`·`dining/`·`mobility_engine/` 를 그대로 넣음 | 구조 시험 184 통과 |
| `dining.py` 와 `dining/` 를 같이 둠 | `test_team_layout.py` 1 실패 — 의도대로 막힘 |
| `role-mobility` 의 맨 위 `tests/mobility/` | 70 통과 · 60 건너뜀(데이터 없음) · 스크립트 6개 목록 표시 |

★**구조가 아니라 내용 때문에 깨지는 시험은 이 규칙으로 안 풀린다.** 팀원 브랜치가 옛 `develop` 에서 갈라져, 우리 쪽에서 새로 생긴 동작(예: `ActivityTeam._terms_hours`)을 기대하는 시험이 팀원 코드에서 실패한다. `develop` 을 받아 병합하면서 맞춘다.
