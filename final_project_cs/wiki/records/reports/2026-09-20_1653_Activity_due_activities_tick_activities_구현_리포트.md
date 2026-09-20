---
type: report
title: Activity — due_activities()·tick_activities() 감시 함수 구현
status: done
domain: travel
---

# Activity — due_activities()·tick_activities() 감시 함수 구현

## 1. 작업 목표

앞선 결정(016 — 재난문자 관련성을 `watch_observations`로 이관)에서 범위 밖으로 남겨뒀던 감시 루프 배선, `due_places()`에 대응하는 `due_activities()`(대상 선정)와 `tick_activities()`(한 틱 실행)를 `app/modules/travel_ops/watch.py`에 구현한다.

## 2. 실제 수행 내용

변경 파일: `app/modules/travel_ops/watch.py`

- `TravelWatcher.due_activities(limit)`: `activities` JOIN `places`(place_id로) LEFT JOIN `watch_observations`(target_kind='activity')를 조회. `due_places()`와 같은 "가장 오래전에 본 것부터, NULLS FIRST" 정렬을 쓰되, 두 조건을 쿼리에 직접 반영했다 — ① `activity_time`이 지금부터 3시간 이내(activity.md에 이미 확정된 재검토 주기), ② `places` INNER JOIN이라 `place_id`가 해소 안 된 활동은 애초에 후보에서 빠진다(어느 지역을 볼지 모르므로).
- `TravelWatcher.tick_activities(limit)`: `due_activities()`가 고른 대상마다 `self.sources.disaster.near(lat, lng, within=activity_time)`을 부른다. `tick_places()`가 `self.sources.place`에 duck-typed로 의존하는 것과 같은 패턴 — 실제 재난문자API 클라이언트는 없고(코드 0줄), 기대 인터페이스(`source.name`, `source.near(...)`)만 정의했다. 지문(`watched`)은 활성 메시지의 `SN:EMRG_STEP_NM` 정렬 목록으로 만들어, 메시지 발령/해제뿐 아니라 긴급단계 변경도 변화로 잡는다. `_record()`(기존 공용 로직)를 그대로 재사용해 `watch_observations`/`watch_changes`에 기록한다.
- `affected_bookings`는 항상 빈 리스트로 뒀다 — 무예약 활동엔 예약이 없고, 예약이 있는 경우의 역추적 방법이 아직 없어서 임의로 만들지 않았다.

`wiki/teams/activity.md` 갱신:
- "재난문자 관련성 — `watch_observations`로 결정" 절에 구현 완료 사실과 인터페이스, 남은 미확보(클라이언트 부재, affected_bookings) 추가
- "걸리는 것" 표에서 `due_activities()` 항목 닫힘 처리, 신규 미확보 2건 추가

## 3. 검증 방법과 결과

```bash
python -m py_compile app/modules/travel_ops/watch.py   # 문법 확인
python -c "
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.watch import TravelWatcher
w = TravelWatcher(connection_factory=get_connection, tenant_id='demo', sources=object())
print(w.due_activities())     # → []
print(w.tick_activities())    # → 검사 0 · 변화 0 · 모름 0 · 재난문자 소스가 안 붙어 있다(키 없음)
"
```

라이브 DB(`acop_cs`)에 대고 실제 SQL을 실행해 스키마와 어긋나지 않음을 확인했다. `activities` 테이블이 비어 있어 빈 결과가 정상이다. `sources`에 `disaster` 속성이 없을 때(`object()`를 넘김) `tick_activities()`가 예외 없이 안내 메시지를 반환하는 것도 확인했다(`tick_places`의 기존 패턴과 동일).

기존 프로젝트에 `watch.py`를 겨냥한 단위 테스트가 하나도 없어(grep 결과 무결과), 새 테스트 파일은 추가하지 않았다 — 요청 범위(함수 구현)를 넘어서는 판단이라 판단만 리포트에 남긴다.

## 4. 미해결 이슈·다음 작업 제안

- 재난문자API 실제 클라이언트(`self.sources.disaster`의 구현체)가 없다 — TourAPI(`tour_api.py`, 313줄)와 달리 완전히 새로 만들어야 한다.
- `tick_activities()`의 `affected_bookings`를 채우는 방법(장소·시각으로 예약 역추적) 미정.
- `watch.py`에 대한 단위 테스트 자체가 없다는 더 큰 공백은 이번 작업 범위 밖으로 남긴다.

## 참조

- `app/modules/travel_ops/watch.py`
- `wiki/teams/activity.md`
- 이전 리포트: `2026-09-20_1647_...`(watch_observations 이관 결정)
