---
type: contract
title: 여행 공통 응대 입력·결과 — 문의 첫 slice
status: draft
domain: travel
---

# 여행 공통 응대 계약 초안

2026-10-24. 구현 담당: 라이팅 1절 child. 통합·독립 검토 책임: 부모(매니저 개발 역할). 계약 소비자 검토·운영 승인은 미완료입니다. 내부 신규 계약이며 기존 TeamResult/API 계약 버전을 올리지 않습니다.

## 소유자·범위

- 기존 decision_unit/fact_context/read_requests가 질문 해석·대상 확인·조회·도구 예산을 소유합니다. 작성기는 조회나 일정 변경을 실행하지 않습니다.
- 이번 첫 연결은 `trip_messages._run_decision → read_requests.reply`의 복합 사실 질문입니다. 기존 조회 결과를 받아 결정론적으로 문단·더보기·질문별 종결을 작성합니다. 외부 LLM을 새로 호출하지 않습니다.
- 공통 모듈은 여행 components/response에 둡니다. 계획서 등록·감시·실행 변경 결과·장기 이력 저장 연결은 다음 절이며 구현 완료를 주장하지 않습니다. 정기 안내는 Case 없는 기존 문구틀·원값 주입을 유지합니다.

## 입력 의미

- `source`: 생산 경로 식별자. 인증은 기존 API/조회 소유자의 책임입니다.
- `scope`: 확인된 tenant_id/customer_id/trip_id. 실제 문의 입구가 DB에서 읽은 여행 범위를 전달합니다. 기존 helper 직접 호출과의 호환을 위해 None을 허용하지만 **범위 미제공**으로 기록하며 인증 완료로 해석하지 않습니다. 작성기는 이 값으로 조회하지 않습니다.
- `version`: 답변의 일정 기준판. 확인 시각은 각 질문의 `checked_at`; 조회 시각과 외부 자료 생성 시각을 혼동하지 않습니다.
- `question_ids`: 기존 해석기의 질문 목록 식별자. 작성기는 누락/중복/여분의 종결을 거부합니다. 원문에서 질문을 새로 추출하는 보장은 이번 범위가 아닙니다.
- `questions`: 질문별 id·원래 질문(request 사본)·문장·더보기·종결(answered/needs_input/unsupported/failed)·근거·확인시각·후속 대상. 미확인 근거를 성공으로 올리지 않습니다.
- `execution`: 실제 실행 결과 스냅샷. 첫 slice는 read_only이며 일정 저장·거래 완료 주장을 만들지 않습니다. 후속 실행 연결은 저장 재조회·결과 버전을 기존 workflow에서 공급해야 합니다.
- `workflow`: 승인/대기·제안·required_input_schema·resume_token 등 기존 상태 스냅샷. 작성기는 해석·대체·갱신하지 않고 복사 보존합니다. 첫 읽기 slice는 빈 스냅샷이며 TeamResult를 읽거나 바꾸지 않습니다.
- `followup`: 원인 이벤트·대상·판·대기 제안의 호출자 제공 스냅샷. 첫 slice는 기존 읽기 focus만 전달하며 저장·권한 재확인·만료·중복·순서 역전 처리를 추가하지 않습니다. 단답을 승인으로 승격하지 않습니다.

## 결과 의미·호환·승인 보존

작성 결과는 `answer`, `more`, 질문별 종결 및 동일 scope/version/execution/workflow/followup 스냅샷입니다. 입력을 수정하지 않습니다. 기존 문장 순서·중복 제거·social·더보기 출력은 보존합니다. 모든 질문이 answered일 때만 `completion=complete`, 그 외 `partial`로 남깁니다. 기존 `outcome.status=answered`는 답변 전달 호환값이지 전 질문 검증 완료가 아니며 `basis.response`에서 구분합니다.

질문별 기존 evidence는 `basis.questions`에 그대로 둡니다. `basis.response`만 추가하며 원래 question 원값·근거·시각·버전·후속 대상이 기록됩니다. API 응답에 새 의무 필드를 만들지 않습니다. 작성기 오류는 숨기거나 일반 지식으로 대체하지 않습니다. 실패 시 업무를 재실행하지 않습니다.

## 고객 소비 계약 — 2026-10-24 로컬 결함 수정 절

담당: 고객 소비 계약 child. 부모 및 웹 소비자 독립 검토는 대기입니다. 기존 `status`·`answer`는 바꾸지 않습니다. writer가 있는 메시지 결과에만 선택 필드 `response_status: complete|partial`, `question_status: [answered|needs_input|unsupported|failed, ...]`를 별도로 제공합니다. 질문 순서는 작성기 입력 순서이며 질문 ID·scope·원문 request·근거·target·workflow·토큰은 이 두 필드에 넣지 않습니다. 누락된 예전 응답에 완료 상태를 추정해서 만들지 않습니다. 잘못된 신규 상태는 조용히 무시하지 않고 거부합니다.

일반 웹 JSON과 SSE result는 같은 `_web_message_result → _web_view` 투영을 사용합니다. 개발 모드 꺼짐에서도 두 필드는 남으며, 기존 basis/decision/basis_sources 제거 정책은 유지합니다. 개발 모드 켜짐에서는 기존 basis 근거 전체를 보존하고 **신규 basis.response의 scope와 각 questions[].request 사본만 제외**합니다. 내부 Case 근거 저장과 원본 객체는 수정하지 않습니다. 기존 개발 근거에 대한 새로운 전면 삭제·PII 정제 정책은 도입하지 않습니다.

`trip_messages`는 동일 최소 상태를 `chat_reply`에 저장하고 duplicate의 기존 허용 목록에 연결합니다. 저장된 예전 chat_reply에는 두 필드가 없을 수 있으며 이를 새로 조회·재계산하지 않습니다. 공개 상태는 enum allowlist로 재검증하며 임의 저장 문자열·원문·토큰은 통과시키지 않습니다. 이는 기존 answer 자체의 PII 정책을 교체하는 기능이 아닙니다.

작성기는 빈 문자열/공백 질문 ID와 `answered`이면서 미해결 `evidence.unresolved`가 있는 모순을 거부합니다. 생산자의 미해결 질문은 명시적인 비완료 종결로 전달해야 하며 작성기가 성공으로 바꾸지 않습니다. DB·앱·외부 모델 없이 격리 unit에서 실제 작성·웹 JSON/SSE·저장 reply·duplicate 경로를 검증합니다.

로컬 검증: 기존 105/105·153/153 선택 회귀를 최신 파일로 재실행했고, 날씨 35 + 신규 소비 계약 26을 포함한 결합 시험 214/214가 통과했습니다. 독립 검토·운영 검증은 미완료입니다. [소비 계약 절 보고서·RED/GREEN·한계](../records/reports/2026-10-24_travel-response-consumer.md).

## 수용 기준과 한계

질문 누락/중복 거부, 미확인 종결, 원값·근거·판·후속 보존, 승인/대기 스냅샷 불변, 기존 출력 호환을 격리 unit 시험으로 확인합니다. DB/LLM/앱/서비스/배포 시험은 하지 않습니다. 도구 조회·저장 완료 표현의 claim 검사·알림 이후 이력 참조·원문 질문 추출 완결성·실모델 품질은 미검증이며 다음 절로 남깁니다.

10월 18일 사본의 read_requests 시간 기준·선택 장소 보정, trip_messages 재개·스냅샷 보정, case_dispatch named destination/새 요청 분리는 직접 대조했습니다. 이를 오래된 사본으로 덮지 않고 읽기 결과 수집·최종 작성 자리만 작은 변경으로 연결합니다.

## 로컬 첫 slice 검증

2026-10-24: 공통 작성기를 실제 복합 문의에 연결했으며 격리 unit 105/105, 기존 출력 정확 비교 18/18을 확인했습니다. [1절 결과·실패 로그·남은 범위](../records/reports/2026-10-24_travel-writing-slice1.md). 전체 에이전트·계획서/감시·운영 완료는 아닙니다.

## 2026-10-24 문의 선별 통합 — 로컬 부분 구현

- `49dd6cb44`의 문의 입력 검증·목적지/조건 보호·새 요청/대기 분리와 `011f4e7e3 → af4a9723c`의 시간 기준 계산을 현재 공통 작성기 연결에 선별 통합했습니다. 새 필수 웹 입력·승인 우회·DB 구조 변경은 없습니다.
- 시간 기준은 일정/시각/지금/직전 답변과 앞뒤 관계를 분리합니다. 직전 대상의 현재 판·TTL·현재 여행 포함 여부를 검증하며 기준이 만료·불명·범위 밖이면 모델의 추측 대상에 조용히 대체하지 않고 `needs_input`으로 남깁니다.
- 종료 시각이 없는 일정에 60분 체류를 만들지 않습니다. 확인된 시작 시각만 사용하며 시각 조회는 기존 다음 시작 우선 규칙을 유지합니다. 공통 작성기의 원래 질문 request는 계산된 fact/target으로 덮지 않고, 계산 근거·실제 대상은 evidence/target에 따로 보존합니다.
- 명시적으로 연결된 대기 건이 있어도 저장된 질문 형식의 짧은 답이 아닌 완결된 새 요청이면 독립 처리합니다. 같은 해석을 재사용하며 원래 대기 건을 재개·수정하지 않습니다. 기존 소유권 확인과 재전송 경계를 유지합니다.
- `27ea017c6`의 weather/outdoor 및 저장 수정 뒤 focus 보호는 비교·RED 재현까지만 진행됐고 쓰기 승인 대기 시간 초과로 미통합입니다. 해당 기능·운영 완료를 뜻하지 않습니다. [2절 부분 결과·정확한 회귀·차단 사항](../records/reports/2026-10-24_travel-writing-slice2-selective-inquiry.md).

## 관계

- [기존 검토·독립 수용 기준 6개](../../../wiki/records/reports/2026-10-24_travel-writing-review.md)
- [채팅 문맥](trip-chat-context.md)
