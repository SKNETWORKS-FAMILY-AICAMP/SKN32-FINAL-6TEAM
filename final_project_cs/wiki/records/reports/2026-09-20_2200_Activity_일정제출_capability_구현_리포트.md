---
type: report
title: Activity — 일정 제출(itinerary_submit) capability 구현
status: done
domain: travel
---

# Activity — 일정 제출(itinerary_submit) capability 구현

## 1. 작업 목표

사용자가 "weather_sensitive는 가데이터에만 존재하는 것 아닌가"라는 질문에서 출발해, `places` 테이블에 실제로 행을 만드는 프로덕션 경로가 없다는 걸 함께 확인했다. 이후 사용자가 정정 — 이 시스템은 예약 생성 시스템이 아니라 CS 시스템이고, "일정 제출"은 고객이 최초로 입력한 일정이다. 그 관점에서 "뭐부터 해야 돼?"에 답해 순서를 설계하고, 1단계(capability 라우팅)부터 구현했다.

## 2. 조사 — 두 가지 실측

1. `intent="itinerary_submit"`은 `issue_code` 접두(`activity_*`)로 ActivityTeam까지는 라우팅되지만, `capability_for()`가 intent를 이름으로 못 맞춰(`activity.*` 네임스페이스와 안 겹침) 항상 `default_capability="activity.check_feasible"`을 고르고, `check_feasible`이 `read.booking`부터 불러 예약이 없어서 **100% `unknown_예약 내역`으로 escalate**되고 있었다.
2. 이 시스템 전체(`activity.change` 포함 모든 action type)에 "승인 후 실제로 실행하는 계층"이 없다 — `scripts/run_outbox_worker.py`의 `publish()`가 "Transport is intentionally an injected boundary in Phase 1"이라 명시한 no-op 스텁. `/v1/cases/.../approve`도 Case 상태만 바꿀 뿐 `action_type`별 실행기가 없다. 사용자에게 확인해 **Phase 1(제안까지만)에 맞추기로 결정**했다.

## 3. 실제 수행 내용

### 라우팅 — 코어 안 건드림
- `app/modules/travel_ops/activity.py`: `select_capability(intent, input_text)` 신설(`registry.py:105~114`의 기존 훅, `mobility.py`가 선례) — `intent=="itinerary_submit"` → `"activity.submit_itinerary"`

### manifest
- `capabilities`에 `activity.submit_itinerary` 추가
- `allowed_tools`에 `read.place_search` 추가

### `execute()` 재구성
- 이 capability만 `read.booking` 호출 **전에** 분기 — 나머지 셋(`check_cancelable`·`check_feasible`·`propose_change`)은 기존처럼 예약을 먼저 읽는 공통 경로 유지

### `app/tools/read_tools.py`
- `place_search(name, kind)` 신규 도구 — `place()`(아는 `place_id`로 우리 DB 조회)와 다르게 **아직 모르는** 장소를 이름으로 TourAPI에서 찾는다. `tour_api.py.find()`를 그대로 위임. 정확일치 1건이 아니면 확정하지 않고 `None`

### `_submit_itinerary()`
- `current_state`에서 `requested_place_name`·`requested_activity_time`을 읽음(자연어 파싱은 이 Team의 경계 밖으로 명시)
- 필수값 없으면 `_unknown()` escalate
- 장소를 찾으면 `activity.submit`(`risk="low"`) 제안 생성 → `WAIT_FOR_APPROVAL`
- 못 찾으면(애매함 포함) **escalate 대신** `WAIT_FOR_INPUT` + `required_input_schema` — 계약에 선언만 되고 아무도 안 쓰던 필드의 첫 실사용

### 구현 중 발견해 고친 버그
`read.place_search`가 `None`을 줄 때 `_evidence()`가 근거를 안 쌓아서, `WAIT_FOR_INPUT`(answer 있음)이 "근거 없는 확정 답변 금지" 계약 검증(`TeamResult` pydantic validator)에 실제로 걸렸다(`ValidationError`). 고객이 제출한 값 자체(`case.current_state`)를 근거로 남기도록 고쳐 해결.

## 4. 검증 방법과 결과

```bash
python -m py_compile app/modules/travel_ops/activity.py app/tools/read_tools.py

# 라우팅 + 전체 흐름 즉석 확인
python -c "... TeamRegistry([ActivityTeam(None)]).capability_for(entry, 'itinerary_submit', ...)"
# → "activity.submit_itinerary" (고치기 전엔 "activity.check_feasible")

python -m pytest tests/unit/travel/test_activity_submit_itinerary.py -v   # 11 passed
python -m pytest tests/unit/travel tests/unit/core tests/contract tests/architecture -q \
  --ignore=tests/contract/test_declared_refs_are_savable.py
# → 565 passed, 3 skipped, 5 failed(전부 기존 무관 이슈 — acop_composer·prompts 미등록·
#    2026-09-11 날짜 debug report 상태표기, 오늘 작업과 무관함을 파일 날짜로 확인)
```

## 5. 미해결 이슈·다음 작업 제안

- **Phase 2 — 승인된 `activity.submit` 제안을 실제로 `activities`/`places`에 쓰는 실행기가 없다.** Activity 하나의 범위를 넘는 시스템 전체(outbox worker) 설계가 필요하다.
- `activity.propose_change`(기존 예약 변경)의 라우팅 미도달은 이번에 안 건드렸다 — `submit_itinerary`와 별개 문제로 남아 있다.
- `read.place_search`가 kind로 좁히는 매핑을 `watch.py`의 `KIND_TO_CONTENT_TYPES`와 별도로 작게 복제했다 — 값이 갈리면 두 자리를 다 고쳐야 한다.

## 참조

- `app/modules/travel_ops/activity.py`, `app/tools/read_tools.py`
- `tests/unit/travel/test_activity_submit_itinerary.py`
- `wiki/teams/activity.md`
- 이전 리포트: `2026-09-20_2117_...`
