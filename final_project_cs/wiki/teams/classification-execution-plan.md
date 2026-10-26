---
type: contract
title: 분류 에이전트의 여행 문제 실행 계획
description: 모델 계획 검증, 팀별 계산 권한과 여행별 원자적 적용
status: draft
domain: travel
decision_status: accepted
implementation_status: implemented
validation_status: verified
verified_at: 2026-10-12T04:43:59.881485+09:00
---

# 분류 에이전트의 여행 문제 실행 계획

분류 에이전트가 한 회차·한 여행의 문제를 처리할 팀, 순서, 우선순위와 의존 관계를 정합니다. Activity는 다른 팀의 조정자가 아닙니다. 이 계약은 [D-017](../../../wiki/decisions/D-017-watch-cadence-golden-time.md), [D-018](../../../wiki/decisions/D-018-decision15-stop-paths.md), [D-020](../../../wiki/decisions/D-020-trip-survey-and-ask-first.md)의 후속 구현 계약입니다.

## 입력과 출력

입력은 마스킹한 고객 질의, 현재 여행·일정 버전·일정 항목, 발견된 문제, 저장된 설문·성향과 현재 조립 판의 실행 가능한 팀입니다. 성향 입력은 해당 여행에 저장됐고 직접 답한 표시가 있는 값만 사용합니다. 기본으로 채워진 설문 값을 고객 성향으로 주장하지 않습니다. 다른 고객의 기억을 조회하거나 미확보 성향을 생성하지 않습니다.

검증하는 계획은 `schema_version="1.0"`, `base_version`, `steps`입니다. 각 단계는 아래 필드를 모두 갖고 추가 필드를 허용하지 않습니다. `[2026-10-26 라우팅 감사 12c]` 필드마다 정하는 쪽이 다릅니다 — 분류 에이전트(모델)는 [D-017](../../../wiki/decisions/D-017-watch-cadence-golden-time.md)대로 담당·순서·우선순위·의존·이유만 정하고, 도구 범위와 호출 상한은 담당 Team의 등록 선언(manifest `allowed_tools`·`max_steps`)에서 옵니다.

| 필드 | 형식·제약 | 의미 | 정하는 쪽 |
|---|---|---|---|
| item_id | 현재 문제 항목의 UUID 문자열 | 계산할 일정 항목 | 모델(답의 키) |
| team_id | 활성·등록·계산 제공 팀 | 담당 팀; 항목 종류의 계산 소유자와 일치 | 모델 |
| order | 1부터 연속된 정수 | 출력 배열과 같은 실행 순서 | 모델 |
| priority | 설정 범위의 정수 | 작은 값이 높은 우선순위; 순서 결정 이유와 함께 보존 | 모델 |
| depends_on | 앞 단계 항목 id의 중복 없는 배열 | 선행 단계가 실패·보류하면 이 단계도 보류 | 모델 |
| tools | 담당 manifest 안의 중복 없는 도구 목록 | 이 단계의 허용 도구 | 담당 Team 선언(`allowed_tools`) |
| max_calls | 1 이상, 담당 manifest 상한 이하 | 이 단계 도구 호출 상한 | 담당 Team 선언(`max_steps`) |
| reason | 비어 있지 않은 짧은 문자열 | 배정·순서의 근거 | 모델 |

모델 답은 항목 id를 키로 한 `assignments`(값: `team_id`·`order`·`priority`·`depends_on`·`reason`)이고, 묶음마다 만든 JSON 스키마로 받습니다. 코드는 모델이 고른 `team_id`의 등록 선언으로 `tools`·`max_calls`를 채운 뒤 아래 검증을 그대로 돌립니다. 모델 답에 `tools`·`max_calls`·`item_id` 등 다른 필드가 있으면 덮어쓰지 않고 `plan_schema_invalid`로 거절하며, 활성 팀 목록에 없는 `team_id`는 `plan_team_forbidden`입니다. 모델 입력의 팀 목록은 팀 id만 보냅니다. 근거: 모델에게 도구·예산을 고르게 했을 때 로컬 E4B가 모든 항목에 `read.disruptions` 1회만 줘 Team 계산이 첫 조회에서 끝났고(대체 후보를 찾을 수 없음), 도구를 더 고르게 한 지시문은 6항목이 66초로 당시 제한시간(`plan_timeout_seconds` 50초)을 넘었습니다(2026-10-26 라우팅 감사 12·12c 보고서). 묶음 상한(`travel.watch.batch_max_items`) × 감시 Team 최대 `max_steps`는 `travel.watch.plan_max_tool_calls` 이하여야 하며 시험이 확인합니다. 주입한 다른 계획기가 더 작은 예산을 주면 실행기는 그 값을 그대로 강제합니다.

계획 호출의 시간은 고정 제한시간이 아니라 답 조각 감시입니다(`[2026-10-26 사용자 결정]`, 계획 읽기·채팅 해석과 같은 `model_stream.collect`): 모델이 조각을 계속 보내는 동안 기다리고, 가드레일 `travel.watch.plan_stream`의 첫 조각(`first_token_seconds`)·조각 사이(`stall_seconds` 5초)·맨 위 상한(`max_seconds`, 묶음 시간 안) 중 하나를 넘으면 받다 만 답을 버리고 `plan_provider_failed` → `classification_failed`로 드러냅니다(고정 순서·고정 대기 호출로 대체하지 않음).

모든 입력 문제를 정확히 한 번 포함해야 합니다. 타 여행 항목·오래된 버전·없는 팀·다른 팀 계산·추가 도구·순환·뒤 단계 의존·중복·총 호출 예산 초과는 거절합니다. 모델 실패나 잘못된 출력은 `classification_failed`로 명시하고 고정 순서로 대체하지 않습니다. 프롬프트 판·해시, 계획 해시와 검증된 출력은 실행 결과의 결정·적용 요약에 보존합니다.

## 실행·적용

조립의 로컬 실행 어댑터가 묶음 요청을 여행 도메인 실행기에 넘깁니다. Controller에는 여행 어휘나 새 팀을 넣지 않습니다. Case의 단일 담당 라벨은 실행 진입 표지이고 다중 팀 계획의 판단자가 아닙니다. 각 계산은 등록된 해당 팀 객체·manifest·도구 상한으로 수행합니다. 임시 초안은 요청 메모리 안에만 있고 뒤 단계가 앞 단계의 적용 가능한 변경을 받습니다.

전체 재검증 후 `itinerary.apply` 제안 하나를 반환합니다. 적용기는 고객 소유권, 최신 버전, 현재 항로 지킴이·고정 항목·재난 정지를 다시 확인하고 기존 CAS·멱등·outbox 경계에서 저장합니다. 항로 지킴이는 명시적 켜짐만 자동 적용하며 미응답·기본값만 있는 옛 여행은 먼저 묻습니다. 업체 거래 승인 경로를 사용하지 않거나 우회하지 않습니다.

## 실패·복구·진단 접합

조회 실패는 해당 단계와 의존 단계만 보류합니다. 독립 변경은 합친 일정 재검증을 통과한 경우에만 적용합니다. 고객에게 확인 시각·오류 코드·기존 일정 유지·다음 회차 재확인을 안내하고 `batch.retry` 또는 `retry:<item_id>`로 기존 제한된 재시도 경로를 엽니다. 대체 조회·재시도는 기존 자료 Port를 사용합니다. 자료가 복구되면 최신 일정·최신 설정으로 새로 검증합니다.

진단 저장 서비스는 이 실행기가 만들지 않습니다. 조립에서 주입한 운영 진단 콜백이 실행기의 실패를 별도 트랜잭션에 저장하고 DB 실패 시 영속 대기 파일로 넘깁니다. 고정 오류 코드와 UUID만 전달하며 고객 원문·접속 정보·예외 응답 본문은 저장하지 않습니다. 수집 자체의 실패는 `collection_degraded`로 드러냅니다. [연결·삭제·경쟁 시험](../records/reports/2026-10-12_0520_diagnostic-delete-integration.md)은 Team 실행·여행 묶음·감시 경계를, [최초 분류·라우팅 시험](../records/reports/2026-10-12_0603_initial-diagnostics-integration.md)은 고객 접수·분류 되잡기·대화 분류·담당 실패 경계를 확인합니다. 선택 시험과 전체 인수·운영 반영은 구분합니다.

## 확인 상태

구현·실행 증거는 [담당 보고서](../../../program/research/baseline_completion_2026-10-12/tasks/orchestration/report.md)에 추가합니다. 독립 검토자는 미배정이며 작업자가 계약 검토를 겸합니다. 로컬 모델 품질·운영 반영·원격 A2A 다중 팀 조정은 이 문서만으로 완료로 판정하지 않습니다.

## 환경별 확인

이 계약의 구현·검증 범위는 로컬 실행 어댑터의 감시 묶음입니다.

| 환경·범위 | 상태 | 근거 |
|---|---|---|
| 로컬 작업 트리·계획/조회/Core 경계 | 179/179 통과 | 담당 보고서와 unit-final.xml |
| 전용 격리 PostgreSQL·저장/장애/설정/안전 | 129/129 마지막 결과 통과 | 담당 acceptance-summary.json |
| 실제 모델 품질·외부 자료 응답·원격 A2A·운영 반영 | unverified | 이번 실행 범위 밖 |

독립 문서 검토 미배정이므로 문서 상태는 draft로 유지합니다. 검증 시각은 2026-10-12T04:43:59.881485+09:00입니다.
