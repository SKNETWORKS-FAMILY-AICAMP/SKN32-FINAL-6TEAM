---
type: report
title: Activity — TourAPI 클라이언트 실존과 places 공유 관계를 activity.md에 정정 반영
status: done
domain: travel
---

# Activity — TourAPI 클라이언트 실존과 places 공유 관계를 activity.md에 정정 반영

## 1. 작업 목표

지난 세션에서 `activity.md`에 "TourAPI 연동은 신규, 세부 사양 미정"이라고 반영했는데, 코드 조사 결과 부정확했다. 이를 정정하고, 별도로 확인한 "`places` 테이블은 Activity 전용이 아니다"(Dining과 공유, Mobility는 미사용)도 함께 반영한다.

## 2. 실제 수행 내용

변경 파일: `wiki/teams/activity.md`

1. "TourAPI · 재난문자API 연동" 절, 판정 순서 아래에 정정 추가 — `app/infrastructure/travel/tour_api.py`(313줄)에 TourAPI 클라이언트가 이미 구현돼 있음(`find`·`operating`·`by_content_id`·`area_page`·`changed_since`). 단 `activity.py`·`watch.py` 어디서도 import되지 않고, 실제로 쓰이는 곳은 `scripts/seed_travel.py`와 단위 테스트뿐. "세부 사양 미정"은 클라이언트 부재가 아니라 판정 경로 배선 미완을 뜻한다고 명확히 함. 재난문자API는 코드 0줄로 스펙 문서 말이 맞다고 확인.
2. "데이터 저장 — 제안 스키마" 절에 신규 서브섹션 "실제 `places` 테이블 — Activity 전용이 아니다" 추가 — `010_domain_travel.sql`의 `kind` 컬럼 주석(activity/dining/lodging/flight)과 코드 근거(`activity.py:138`, `dining.py:52~53` 둘 다 `read.place` 사용, `mobility.py`는 `read.route`/`read.transit`만 사용)를 표로 정리. `watch.py:120`의 `target_kind='place'`가 Team 무관하게 전체를 도는 것도 명시.

## 3. 검증 방법과 결과

```bash
grep -rln "tour_api\|TourAPI" scripts/ tests/   # → seed_travel.py, test_rate_limit.py, test_open_meteo_live.py
grep -n "TourAPI\|tour_api" app/modules/travel_ops/watch.py app/modules/travel_ops/activity.py  # → 무결과
grep -n "read.place\|place_id" app/modules/travel_ops/dining.py app/modules/travel_ops/mobility.py app/modules/travel_ops/activity.py
grep -n "target_kind\|kind ==" app/modules/travel_ops/watch.py  # → target_kind = 'place' (line 120)
```

모두 실행해 출력을 직접 확인했다(문서 반영 전 grep 결과를 근거로 씀).

## 4. 미해결 이슈·다음 작업 제안

- TourAPI 클라이언트를 `check_feasible` 판정 경로에 배선하는 작업이 남아 있다 — 클라이언트는 있고 배선만 없다는 걸 명확히 했으니, 이 작업의 범위는 더 좁아졌다.
- `places`를 Dining과 공유하는 채로 TourAPI 연동을 얹을지, Activity 전용 테이블(`activities`)을 새로 팔지는 여전히 미확보(§ 걸리는 것 표에 이미 있음).

## 참조

- `wiki/teams/activity.md` (이번 수정 대상)
- `app/infrastructure/travel/tour_api.py`
- `app/modules/travel_ops/{activity,dining,mobility,watch}.py`
- `app/infrastructure/db/migrations/010_domain_travel.sql`
