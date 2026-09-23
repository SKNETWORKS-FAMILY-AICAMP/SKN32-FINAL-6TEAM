---
type: contract
title: 여행 밀도 API
status: draft
domain: travel
---

# 여행 밀도 API (선택 확장 1.2)

`POST /v1/trips`의 기존 `constraints` 안에 아래 선택 입력을 저장한다. 등록과 조회 응답의 `density`에 현재 버전 측정을, `warnings`에 초과/미측정 경고를 준다. 미설정은 `density: []`, `warnings: []`이며 기존 거절 판정은 그대로다.

```json
{"density":{"level":"normal","days":{"2026-09-23":{"starts_at":"2026-09-23T10:00:00+09:00","ends_at":"2026-09-23T22:00:00+09:00","buffer_minutes":30}}}}
```

level은 low/normal/high/very_high이며 현재 연구 보정값은 `low=0.40`, `normal=0.55`, `high=0.70`, `very_high=0.80`이다. Low 0.40은 관광 일정 연구에서 낮은 temporal occupation 결과가 약 40%로 관찰된 값을 기준으로 한다. 나머지는 같은 연구의 low/high 선호 구분과 이동시간 약 10% 관찰을 일정 운영 구간으로 보간한 값이다. 안전 보증이나 서울 모집단의 최적값으로 해석하지 않는다. `"target_density": 0.72`처럼 사용자의 목표를 직접 지정할 수도 있다(0 초과 1 미만의 유한수). level과 target_density는 정확히 하나만 지정한다.

days 키는 서울 기준 활동 시작 날짜. 시작·종료는 오프셋 필수이고 시간 창은 서로 겹칠 수 없으며 최대 24시간. `buffer_minutes`는 항목 시간에 아직 포함하지 않은 추가 완충시간이며 필수다(명시한 0 허용). 창을 넘긴 일정은 잘라서 계산하지 않는다.

모든 항목에 양의 소요시간이 있어야 한다. 이동 항목은 선택 경로의 유효한 `eta_min`이 있고 배정 시간이 그 이상이어야 한다. `average_eta_min`과 `p95_eta_min`이 있으면 FHWA 방식으로 `max(0, p95-average)`를 추가 완충으로 계산하며 일률 15%를 더하지 않는다. `distance_m`과 `constraints.mobility_ease=needs_rest`가 있으면 영국 교통부 Inclusive Mobility의 장거리 보행 휴식 기준(30m마다 2분)을 적용한다. 연속된 비이동 항목의 장소 식별자가 다르거나 없으면 뒤 항목의 `detail.min_transfer_time_seconds`(GTFS 환승 표준) 또는 확인한 `detail.transfer_minutes_before`를 명시한다. 명시 이동시간은 앞 항목 종료~뒤 항목 시작 간격 안에 들어가야 한다. 같은 장소 식별자이면 이동 0으로 계산한다.

분자는 항목 소요 합 + 항목 밖 이동 합 + 추가 완충시간. 중복/겹침은 측정 불가. 빈 날은 완충시간만 계산한다. 서울 날짜별로 계산하며 야간 일정은 시작일 창 안에 완전히 포함되어야 한다.

측정 결과: `date`, `status`(ok/exceeded/unmeasurable), `target_density`, `policy_basis`(research_calibrated/user_preference/undetermined), `occupied_minutes`, `available_minutes`, `actual_density`, `reasons`. 미측정 수치는 null이다. 잘못된 밀도 입력도 거절하지 않고 이유를 가진 `unmeasurable` 경고로 낸다. 경고에는 `code`, `date`, `reason`, `remedy`, `policy_basis`가 있다. 미측정은 안전 또는 여유 판정이 아니다. 이 정보는 API 소비자가 표시하는 관측 정보이며 계획서 화면에는 아직 추가하지 않는다.

1.1 추가 결과는 `policy_id`, `research_as_of`, `measurement_scope: submitted_schedule`, `buffer_placement: unallocated`, `breakdown`이다. 설정 식별자와 조사 기준일은 guardrails에서 읽는다. `breakdown`은 미측정일 때 null이며, 그 외에는 다음을 담는다.

- `scheduled_minutes`: 모든 항목 시간 합. 식사·예약·이동·대기가 이미 포함됐으면 한 번만 센다.
- `transfer_minutes`: 항목 밖에 명시한 이동시간 합.
- `buffer_minutes`: 아직 시간 위치를 배정하지 않은 하루 추가 여유.
- `travel_minutes`: scheduled 중 mobility 소요 + transfer. 위 합산의 부분집합이며 다시 더하지 않는다.
- `known_queue_minutes`: 각 항목 `detail.queue_minutes` 주석 합. 이 주석은 항목 구간 **안에 이미 포함된 대기**만 나타내며 일정 시간에 더하지 않는다. 0 이상 항목 길이 이하의 유한수여야 한다. 이동 항목에는 쓰지 않는다(환승 대기는 경로 소요에 포함).
- `queue_unannotated_items`: queue_minutes가 없는 비이동 항목 수. known_queue_minutes가 0이어도 실제 대기가 없다는 뜻은 아니다.
- `unallocated_minutes`: available − occupied. 음수면 시간 예산 초과다. 양수여도 고정 예약 직전에 그 시간이 확보됐다는 보장은 없다.

예약 항목은 `detail.reservation=true`로 표시한다. 식당 예약은 운영 지침의 15분 도착 여유를, 그 외 예약은 루브르 단체 입장 지침의 30분 수속 여유를 기본값으로 넣되 `arrival_buffer_minutes`로 시설값을 덮어쓸 수 있다. `constraints.first_visit=true`이면 첫 항목에 30분 오리엔테이션 여유를 넣는다. 대기가 항목 밖에서 필요하면 대기 시작/종료를 일정 항목으로 명시하고 방문 항목과 겹치지 않게 한다. 별도 대기 항목과 방문 항목에 같은 대기시간을 이중으로 넣지 않는다. 건강·장애·나이별 고정 점유율 차감은 적용하지 않고, 필요한 휴식은 `mobility_ease`와 거리로 계산한다.

추가 조사: [2026-09-22 여행 밀도 근거 자료](../records/reports/2026-09-22_2300_여행밀도_근거자료.md).

근거: [D-019](../../../wiki/decisions/D-019-travel-density.md).
