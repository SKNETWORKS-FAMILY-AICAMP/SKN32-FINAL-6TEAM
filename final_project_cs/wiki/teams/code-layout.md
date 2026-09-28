---
type: guide
title: 팀 코드·시험을 두는 자리
description: Activity·Dining·Mobility 가 각자 폴더에서 작업하는 규칙. 코드는 파일 하나·폴더·파일+엔진 세 방식 모두 허용, 시험은 final_project_cs/tests/ 한 자리에 pytest 만
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

## 시험 — `final_project_cs/tests/` 한 자리, pytest 만

`[2026-09-28 결정]` 팀 시험은 **cs 시험 폴더 한 자리**에 둔다. CI 는 `final_project_cs` 안에서 pytest 만 돌린다.

| 무엇 | 자리 |
|---|---|
| 이 팀만 보는 시험 | `final_project_cs/tests/unit/travel/<팀>/` — 공용 가짜 도구는 `from ..helpers import ...` |
| 여러 팀을 함께 보는 시험 | `final_project_cs/tests/unit/travel/` (예: `test_evidence_accumulates.py`) |
| 시험이 읽는 데이터(JSON 등) | 그 시험 옆. 파일 위치 기준으로 읽는다(`Path(__file__).parent / ...`) |

★**시험 폴더에는 pytest 로 도는 시험만 둔다.** `def test_...` 함수가 없거나 불러오는 순간 `sys.exit()` 가 도는
스크립트는 pytest 가 모으다 멈추거나 아무것도 확인하지 않는다. 그런 것은 둘 중 하나로 한다.

- **데이터 없이 도는 검사** → 끝의 `sys.exit` 를 `if __name__ == "__main__":` 안으로 넣고 `def test_...` 확인 함수를 붙인다.
- **이 기기의 자료(`DATA_DIR` 등)가 있어야 도는 점검·생성기** → 시험 폴더 밖(예: 저장소 맨 위 `scripts/mobility_checks/`).

데이터가 없어 시험 스스로 건너뛰는 것(`pytest.skip`)은 실패가 아니다 — CI 에는 시간표 같은 자료가 없다.

`[실측 2026-09-28]` `role-mobility` 가 저장소 맨 위 `tests/mobility/` 에 두던 시험을 매니저가 옮겼다(커밋 `3c73687e`):
pytest 시험 7개와 데이터 → `tests/unit/travel/mobility/`, 스크립트 방식 중 자료 없이 도는 3개는 확인 함수를 붙여 같은 자리로,
자료가 있어야 도는 3개·계약 점검·생성기는 `scripts/mobility_checks/` 로. 옮긴 뒤 cs 안에서 **73 통과 · 60 건너뜀**(옮기기 전 70 통과).
저장소 맨 위 `tests/` 를 돌리던 CI 단계는 이때 걷어 냈다.

## 확인한 것

`[실측 2026-09-28]` 임시 사본에서 방식을 바꿔 가며 돌렸다.

| 사본 | 결과 |
|---|---|
| Activity 파일 하나 · Dining 폴더 · Mobility 파일+엔진 | 구조 관련 시험 687 통과 |
| 팀원 브랜치의 `activity/`·`dining/`·`mobility_engine/` 를 그대로 넣음 | 구조 시험 184 통과 |
| `dining.py` 와 `dining/` 를 같이 둠 | `test_team_layout.py` 1 실패 — 의도대로 막힘 |
| `role-mobility` 시험을 `tests/unit/travel/mobility/` 로 옮긴 뒤 | 73 통과 · 60 건너뜀(데이터 없음) |

★**구조가 아니라 내용 때문에 깨지는 시험은 이 규칙으로 안 풀린다.** 팀원 브랜치가 옛 `develop` 에서 갈라져, 우리 쪽에서 새로 생긴 동작(예: `ActivityTeam._terms_hours`)을 기대하는 시험이 팀원 코드에서 실패한다. `develop` 을 받아 병합하면서 맞춘다.
