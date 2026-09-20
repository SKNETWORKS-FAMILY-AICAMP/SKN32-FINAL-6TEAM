---
type: report
title: Activity — disaster_api_content_id를 watch_observations로 이관 결정
status: done
domain: travel
---

# Activity — disaster_api_content_id를 watch_observations로 이관 결정

## 1. 작업 목표

015 마이그레이션에서 결정 범위 밖으로 남겨뒀던 `activities.disaster_api_content_id`의 설계(정적 FK vs 관측)를 결정하고 마이그레이션으로 반영한다.

## 2. 실제 수행 내용

신규 파일: `app/infrastructure/db/migrations/016_activities_disaster_to_watch.sql`

- `activities.disaster_api_content_id` 컬럼 제거(FK도 함께 사라짐)
- 대체: `watch_observations`를 `target_kind='activity'` · `target_id=activities.id` · `source='disaster_api'`로 사용

결정 근거: TourAPI 신원(`place_id`, 015)은 한 번 해소하면 안 바뀌는 값이지만 재난문자 관련성은 활동 시작 3시간 전부터 5분 간격으로 재검토하는 시간 가변 값이다(이미 activity.md에 확정된 주기). 정적 FK 한 칸은 "가장 최근에 본 것"만 담아 발령→격상→해제 같은 이력을 잃는다. `watch_observations`(012)가 이미 주기적 관측 append + fingerprint 기반 변화 감지(→`watch_changes`)로 이 모양을 구현하고 있고, TourAPI·장소 감시가 `target_kind='place'`로 같은 인프라를 쓴다 — 감시 방식을 두 개로 쪼개지 않기 위해 같은 메커니즘을 재사용한다. `target_kind`를 `activity`로 둔 이유는 재난 관련성이 장소가 아니라 활동의 예정 시각에 달려 있기 때문이다. FK는 걸지 않는다(payload jsonb, TourAPI 관측이 place_catalog에 FK 안 거는 것과 같은 패턴).

`wiki/teams/activity.md` 갱신:
- "TourAPI · 재난문자API 연동" 절, 「사용 필드·DB 연계」 표의 재난문자API 대응 테이블을 `disaster`(원본) + `watch_observations`(관련성)로 정정
- 신규 서브섹션 "재난문자 관련성 — `watch_observations`로 결정" 추가
- "걸리는 것" 표에서 해당 항목 닫힘 처리, `due_activities()` 배선 미확보를 새로 추가

## 3. 검증 방법과 결과

```bash
python -m app.infrastructure.db.migrate   # 2회 연속 실행, 둘 다 정상 종료
psql -d acop_cs -c "\d activities"
```

`activities`가 이제 `id`·`tenant_id`·`name`·`lat`/`lng`·`activity_time`·`address`·`place_id`(FK→places)만 남았음을 직접 확인 — `disaster_api_content_id`·`tour_api_content_id` 둘 다 제거됨.

## 4. 미해결 이슈·다음 작업 제안

- `watch.py`의 `due_places()`에 대응하는 `due_activities()`가 아직 없다 — 감시 루프가 `activities`를 대상으로 돌게 하는 배선은 범위 밖으로 남겼다.
- 재난문자API 판정 기준(긴급단계 몇 단계부터 `feasible: False`)은 여전히 미확보.

## 참조

- `app/infrastructure/db/migrations/016_activities_disaster_to_watch.sql`
- `wiki/teams/activity.md`
- 이전 리포트: `2026-09-20_1626_...`(place_id 결정)
