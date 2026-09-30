---
type: guide
title: 팀 코드·시험 폴더 구조 변경 안내 (2026-09-28)
description: Activity·Dining·Mobility 팀원에게 — 팀 코드는 travel_ops/<팀>/ 폴더, 시험은 tests/unit/travel/<팀>/ 한 자리. 브랜치별로 develop 을 받을 때 할 일
status: draft
tags: [agent]
owners: [human:미배정]
domain: travel
---

# 팀 코드·시험 폴더 구조 변경 안내 (2026-09-28, `develop` 반영 완료)

규칙 전체는 [code-layout.md](code-layout.md)에 있다. 이 문서는 팀원에게 보내는 안내문이다.

## 1. 무엇이 바뀌었나

각 팀 코드는 이제 **자기 팀 폴더** 안에 둔다. `develop` 은 이미 이렇게 바뀌어 있다.

```
final_project_cs/app/modules/travel_ops/
  activity/   __init__.py  team.py   ← Activity 팀 폴더
  dining/     __init__.py  team.py   ← Dining 팀 폴더
  mobility/   __init__.py  team.py   ← Mobility 팀 폴더
```

- `team.py` 에 팀 본체(`ActivityTeam` 등)가 있다. `__init__.py` 는 그 클래스를 밖으로 다시 내보내기만 한다.
- 바깥에서 부르는 방법은 그대로다 — `from app.modules.travel_ops.activity import ActivityTeam` 같은 import 와 `config/project.yaml` 의 등록 문자열을 고칠 필요가 없다.
- 팀 폴더 안에 도우미 파일(`xxx.py`)이나 하위 폴더를 자유롭게 더 둬도 된다.

`travel_ops/` 바로 아래의 다른 `.py`(`itinerary.py`·`trip_api.py`·`planner.py` 등)와 `intake/`·`scenarios/`·`static/` 은 팀 코드가 아니라 **세 팀과 여행 API 가 함께 쓰는 공용 코드**다. 팀이 고칠 곳이 아니다.

## 2. 허용하는 방식 세 가지 (어느 것이든 시험 통과)

| 방식 | 모양 |
|---|---|
| 폴더 (기본) | `activity/__init__.py` + `team.py` — 본체를 `__init__.py` 에 직접 써도 된다 |
| 파일 하나 | `activity.py` (예전 방식) |
| 파일 + 엔진 | `mobility.py` + `mobility_engine/` — 엔진 폴더는 **팀 이름과 다른 이름**(`<팀>_engine`)으로 |

★**하면 안 되는 것 — `activity.py` 와 `activity/` 폴더를 함께 두지 않는다.** 둘 다 있으면 파이썬은 폴더만 불러오고 파일은 **오류 없이 무시한다** — 고쳐도 반영이 안 된다. 병합 충돌을 풀다 둘 다 남기기 쉽다(시험 `tests/contract/test_team_layout.py` 가 막는다).

## 3. 팀 폴더 전체에 걸리는 규칙

팀 폴더·엔진 폴더 안의 `.py` 는 **전부 팀 코드**로 본다. 아래는 팀 코드에서 직접 import 하지 않는다 — 도구는 코어가 넘겨주는 것만 쓴다.

`app.infrastructure` · `app.application` · `app.presentation` · `psycopg` · `openai`

## 4. 시험은 한 자리에, pytest 만

| 무엇 | 두는 곳 |
|---|---|
| 우리 팀만 보는 시험 | `final_project_cs/tests/unit/travel/<팀>/` (폴더는 만들어 두었다) |
| 여러 팀을 같이 보는 시험 | `final_project_cs/tests/unit/travel/` |
| 시험이 읽는 데이터(JSON 등) | 그 시험 파일 옆 — 파일 위치 기준으로 읽는다: `Path(__file__).parent / "xxx.json"` |

- 공용 가짜 도구는 `from ..helpers import FakeTools, ...`
- ★**시험 폴더에는 pytest 로 도는 시험만 둔다.** `def test_...` 함수가 없는 직접 실행 스크립트는
  - 데이터 없이 도는 검사 → 맨 끝의 `sys.exit(...)` 를 `if __name__ == "__main__":` 안으로 넣고 `def test_...` 확인 함수를 하나 붙인다
  - 내 PC 의 데이터(`DATA_DIR`)가 있어야 도는 점검·생성기 → 시험 폴더 밖 `scripts/` 로
- CI 서버에는 시간표 같은 데이터가 없다. 데이터가 없으면 `pytest.skip(...)` 으로 건너뛰게 한다 — 건너뛰기는 실패가 아니다.

## 5. CI(자동 검사)가 도는 때

- **`develop` 으로 PR 을 열거나 `develop` 에 푸시할 때** 자동으로 돈다 — ruff 린트 + `final_project_cs` 안의 `pytest tests/architecture tests/contract tests/unit`.
- 자기 브랜치(`role-*`)에 푸시하는 것만으로는 돌지 않는다. **PR 을 열어 결과를 확인**한다.
- `main` 은 보호 규칙이 켜져 있어 직접 푸시가 안 되고 매니저가 직접 관리한다.
- CI 서버는 한국 시간(`Asia/Seoul`)으로 돌도록 맞춰 두었다.

## 6. 팀별로 할 일 (2026-09-28 오후 기준)

먼저 공통 — 자기 브랜치에서 `develop` 을 받아 합친다.

```bash
git fetch origin
git merge origin/develop
cd final_project_cs
pip install -r requirements.txt
python -m pytest tests/architecture tests/contract tests/unit -q
```

`requirements.txt` 에 파일 읽기 패키지 4개가 추가됐다 — `pip install` 을 꼭 한 번 다시 한다.

`[실측 2026-09-28]` 각 브랜치를 지금 `develop` 에 합쳐 보면(실제로 합치지는 않고 `git merge-tree` 로 계산):

| 브랜치 | 상태 | 할 일 |
|---|---|---|
| `role-mobility` | **충돌 없음** | 저장소 맨 위 `tests/mobility/` 시험은 **매니저가 `final_project_cs/tests/unit/travel/mobility/` 로 옮겨 두었다**(커밋 `3c73687e`) — 작업 전에 꼭 `git pull`. 데이터가 있어야 도는 점검 스크립트·생성기는 `scripts/mobility_checks/` 로 옮겼고, 스크립트 기본 경로도 새 위치로 고쳤다 |
| `role-dining` | **충돌 2곳** | `dining/__init__.py` · `dining/team.py` — 양쪽 다 `dining/team.py` 구조라 Team 코드 내용을 합친다 |
| `role-activity` | **충돌 8곳** (`develop` 보다 26커밋 뒤) | `activity/__init__.py` 는 `develop` 에 새로 생긴 `activity/team.py` 와 합쳐 **본체를 한 곳에만** 남긴다. 나머지는 `settings.py` · `read_tools.py` · `tour_api.py` · `disaster_msg.py`(와 그 시험) · `requirements.txt` · `wiki/teams/activity.md`. `develop` 에 새로 생긴 동작(예: 취소 규정 계산)을 기대하는 시험이 있으니 합친 뒤 시험을 꼭 돌린다 |
| `role-eval-ui` | 충돌 없음 | 프론트엔드만 — 영향 없다 |

## 관계

- [code-layout.md](code-layout.md) — 팀 코드·시험을 두는 규칙(정본)
- [index.md](index.md) — 팀 문서 목록
