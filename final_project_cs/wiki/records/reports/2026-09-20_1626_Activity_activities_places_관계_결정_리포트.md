---
type: report
title: Activity — activities ↔ places 관계를 place_id FK로 결정
status: done
domain: travel
---

# Activity — activities ↔ places 관계를 place_id FK로 결정

## 1. 작업 목표

`014_activity_tour_disaster.sql`에서 미확보로 남겨뒀던 `activities`와 기존 `places`의 관계(FK로 묶을지 간접 연결만 할지)를 결정하고 마이그레이션으로 반영한다.

## 2. 실제 수행 내용

신규 파일: `app/infrastructure/db/migrations/015_activities_place_link.sql`

- `activities.place_id`(uuid, nullable) 추가 — `places.place_id` FK, `activities_place_idx` 인덱스
- `activities.tour_api_content_id` 컬럼 제거 — `places.source_content_id`(013)와 신원 해소가 중복되는 걸 막는다

결정 근거: `places`(013)가 이미 TourAPI 신원 해소 결과(`source_name`·`source_content_id`·`source_content_type_id`)를 갖고 있다. `activities`에 별도 TourAPI 식별자 칸을 두면 같은 신원을 두 곳에서 따로 해소하게 되고 어긋날 수 있다 — 013이 막으려던 문제의 재현이다. 역할을 `activities`=일정 사실(언제·무엇을), `places`=장소 사실(어디·판정에 쓰는 상태)로 가르고, `place_id`로만 연결한다. NULL 허용은 무예약 활동이 아직 `places`로 해소되지 않은 상태를 표현하기 위함(v11 §5-D).

`disaster_api_content_id`는 이번 결정 범위 밖으로 명시(신원이 아니라 시점 관측에 가까워 별도 판단 필요).

`wiki/teams/activity.md` 갱신:
- "데이터 저장 — Activity 전용 스키마" 절에 신규 서브섹션 "`activities` ↔ `places` 관계 — 결정" 추가
- "걸리는 것" 표에서 해당 항목 닫힘 처리, `disaster_api_content_id` 설계는 새 미확보로 추가

## 3. 검증 방법과 결과

```bash
python -m app.infrastructure.db.migrate   # 2회 연속 실행, 둘 다 정상 종료
psql -d acop_cs -c "\d activities"
```

`\d activities` 출력으로 `place_id`(FK→places) 존재, `tour_api_content_id` 부재, `disaster_api_content_id`는 그대로 남아 있음을 직접 확인.

## 4. 미해결 이슈·다음 작업 제안

- `activities.disaster_api_content_id`를 정적 FK로 둘지 `watch_observations`(target_kind='activity' 등)로 옮길지 결정 필요.
- `activities.place_id`가 NULL인 항목(무예약, 미해소)을 어느 시점에 `places`로 해소할지(배치 vs on-demand)는 아직 설계 안 됨.

## 참조

- `app/infrastructure/db/migrations/015_activities_place_link.sql`
- `wiki/teams/activity.md`
- 이전 리포트: `2026-09-20_1600_...`(014 작성)
