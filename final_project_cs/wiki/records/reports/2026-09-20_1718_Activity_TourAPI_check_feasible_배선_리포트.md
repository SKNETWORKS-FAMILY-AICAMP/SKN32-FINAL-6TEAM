---
type: report
title: Activity — TourAPI 클라이언트를 check_feasible에 배선
status: done
domain: travel
---

# Activity — TourAPI 클라이언트를 check_feasible에 배선

## 1. 작업 목표

`tour_api.py`의 TourAPI 클라이언트를 `activity.py`의 `check_feasible` 판정 경로에 연결한다.

## 2. 조사 — 이전 리포트의 정정

작업 중 이전 리포트(`2026-09-20_1553_...`)의 결론이 부정확했음을 발견했다. `app/infrastructure/travel/base.py`의 `build_travel_sources()`가 이미 `sources.place = TourApiPlace(...)`로 클라이언트를 조립하고 있었고, `app/composition.py:160~163`이 그 결과를 `ReadToolbox(travel=...)`에 실제로 주입하고 있었다 — 즉 클라이언트도 배선 진입점도 이미 있었다. 빠진 것은 `ReadToolbox.place()`(=`read.place` 도구 구현)가 `self.travel.place`를 전혀 참조하지 않는다는 것 하나였다.

## 3. 실제 수행 내용

변경 파일:

- `app/tools/read_tools.py`
  - `_PLACE_COLUMNS`·`place()`의 SELECT에 `source_content_id`·`source_content_type_id`(013) 추가
  - `_fill_operating()` 신설 — 신원이 해소된 장소만, `self.travel.place.operating(content_id, content_type_id)`를 불러 `place["operating"]`에 원문(`usetime_text`·`restdate_text`)을 담는다. 신원 미해소·소스 없음이면 채우지 않는다(모름 유지)
  - `place()`가 `_fill_coordinates()` 다음에 `_fill_operating()`을 거치도록 연결
- `app/modules/travel_ops/activity.py`
  - `_check_feasible()`에서 `place["operating"]`을 읽어 evidence(`read.place.operating`)로 추가
  - `_operating_note()` 신설 — `usetime_text`·`restdate_text`를 **원문 그대로** 안내 문구로 만든다. `tour_api.py.operating()`이 `answers_open_at_slot: False`로 명시하는 것과 같은 이유로 **boolean으로 해석하지 않는다** — `decisions["feasible"]`은 이 값으로 바뀌지 않는다
  - 새 도구 이름을 만들지 않았다 — `allowed_tools`(`read.place`)·budget 변경 없음

`wiki/teams/activity.md` 갱신:
- "판정 순서" 절의 앞선 정정(클라이언트가 seed_travel.py/테스트에서만 쓰인다는 서술)을 재정정 — `build_travel_sources()`/`composition.py` 배선이 이미 있었다는 사실과 이번에 이은 한 곳을 명시
- "사용 필드·DB 연계" 표에서 TourAPI 행을 판정 경로(원문, `places` 경유)와 카탈로그(`tour`)로 구분
- "데이터 저장" 절의 `activities` 테이블 설명이 015·016 이후에도 옛 컬럼(`tour_api_content_id`·`disaster_api_content_id`)을 나열하고 있던 것을 발견해 함께 정정 — 지금 구조(`place_id` FK, `watch_observations`)로 갱신
- "걸리는 것" 표에 이번 작업 닫힘 처리

## 4. 검증 방법과 결과

```bash
python -m py_compile app/tools/read_tools.py app/modules/travel_ops/activity.py
python -m pytest tests/unit/travel tests/contract tests/unit/tools/test_tool_budget.py \
  tests/unit/test_composition_root.py tests/unit/test_project_composition.py -q \
  --ignore=tests/contract/test_declared_refs_are_savable.py
# → 304 passed, 3 skipped, 3 failed
```

실패 3건(`test_active_prompts_are_the_deployed_set.py`)은 이 로컬 DB에 `scripts.register_prompts`를 한 번도 안 돌려서 `prompts` 테이블이 비어 있는 환경 문제이고, 이번 변경과 무관함을 확인했다(관련 코드를 안 건드림).

라이브 DB에 실제 SQL 실행 확인:
```python
box.place(scope, place_id=<존재하지 않는 uuid>)   # → None, 에러 없음(신규 컬럼 포함 SELECT 정상)
box2._fill_operating(row)                          # 가짜 TourAPI 소스로 operating 채움 확인
ActivityTeam._operating_note({...})                 # 안내 문구 출력 확인
```

## 5. 미해결 이슈·다음 작업 제안

- 실제 서비스 키(`ACOP_TOUR_API_KEY`)가 없는 환경에서는 `sources.place`가 안 붙어 `operating`이 항상 비어 있다 — 실키로 end-to-end 확인은 못 했다.
- `tick_places()`(watch.py)는 여전히 `operating()`을 안 부른다 — 배경 감시가 아니라 요청 시점 조회로만 연결했다. 배경 감시까지 필요하면 별도 작업.
- 재난문자API 클라이언트는 여전히 없음(이전 리포트와 동일).

## 참조

- `app/tools/read_tools.py`, `app/modules/travel_ops/activity.py`
- `app/infrastructure/travel/base.py`(`build_travel_sources`), `app/composition.py:160~163`
- `wiki/teams/activity.md`
- 이전 리포트: `2026-09-20_1553_...`(이번에 정정한 리포트)
