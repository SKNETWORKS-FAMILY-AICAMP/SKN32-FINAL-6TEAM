---
type: contract
title: 감시 실행 결과·선택 안내 공통 응대 adapter
status: draft
domain: travel
---

# 감시 응대 연결 절

2026-10-24. monitoring child 소유. 부모 소비자 검토·운영 검증은 별도입니다. [공통 입력·결과](travel-response.md)의 내부 adapter이며 기존 API·TeamResult·DB 계약은 바꾸지 않습니다.

- 기존 watch/planning이 점검·재계획·승인·재검증·저장을 소유합니다. adapter는 전달받은 결과만 작성하며 도구·DB·모델·재실행 권한이 없습니다.
- 입력은 기존 고객 payload, 확인된 여행 scope/현재 version, 실행 status, 저장 결과(saved_version), workflow와 원인/대상 followup 스냅샷입니다. `applied`는 실제 저장 결과와 현재 version이 일치할 때만 허용합니다. 계획 단계 digest나 Controller의 resolved만으로 완료를 만들지 않습니다.
- 상태는 `applied`(적용 완료), `awaiting_choice`(미변경·선택 대기), `failed`(실패·미해결), `unknown`(결과 미확인)을 구별합니다. 공통 completion은 응대 종결이며 업무 완료와 혼동하지 않습니다. applied 외에는 partial로 둡니다.
- 기존 text/문장 순서·원인·시각·금액·고유명사·선택지·경고·되돌리기 값은 그대로 보존하고 `response` 메타데이터와 최소 공개 종결 enum만 추가합니다. 승인 상태·required_input_schema·resume_token은 독립 사본으로 보존합니다.
- planning의 기존 메시지 저장 직전(같은 트랜잭션), append_version 성공 후 변경 통지에 연결합니다. 트랜잭션 실패면 메시지와 저장은 같이 롤백됩니다. commit 전 반환을 외부 배달 완료라 부르지 않습니다.
- Case watch 실행 후에는 저장 Case/applied_actions와 최신 여행을 읽어 별도 responses에 작성합니다. 성공 변경 outbox 자체의 소유자는 기존 적용기이며 이 adapter가 두 번째 통지를 만들지 않습니다. 감시 실패·미해결의 기존 outbox 안내에는 adapter를 연결합니다.
- 기존 dedupe key·만료·승인·재난 재개·거래 경계를 수정하지 않습니다. 작성 오류로 업무를 재실행하지 않습니다. 이미 존재한 알림 재전송은 배달 loop 책임입니다.
- 정기 안내 trip_reminders/Phrase는 변경하지 않습니다. Case 없는 문구틀·원값 주입·no-LLM 경로를 보존합니다.

## 결함 수정·기본 Case 성공 안내 연결 계약 (2026-10-24)

- 묶음의 항목별 `item_id/kind/reasons/checked_at` 결과를 제안 인자와 적용 summary의 `batch.outcomes`에 복사 보존합니다. 이 자료는 안내 전용이며 실행 판정·retry의 기존 의미를 바꾸지 않습니다. no_alternate/recheck_failed/source_failed/error/retry/unavailable는 failed, unknown/알 수 없는 kind는 unknown, asked/consent는 awaiting_choice로 종결합니다. 미확인 → 실패 → 선택대기 순으로 전체 비완료를 보수적으로 표시하며 일부 저장판은 그대로 기록합니다.
- proposal ref는 정확한 `trip:{scope.trip_id}:proposal:{id}`이고 id가 같은 저장 summary의 proposal_id 또는 batch.asked의 proposal_id와 일치해야 합니다. 타 trip·빈 값·불일치는 unknown이며 summary의 asked 표지만으로 검증을 우회하지 않습니다. 기존 waiting_input/waiting_approval 자체는 독립 대기 근거입니다.
- 기본 Case `_version_notice`의 기존 OutboxMessage 한 건에만 response와 공개 enum 상태를 추가합니다. 키/topic/원문/되돌리기/승인 및 코어의 동일 트랜잭션 적재 경로는 유지합니다. `_open_ask/_open_consent`도 기존 신규 outbox만 장식하고 already이면 재작성·재발행하지 않습니다.
- 작성 실패는 기존 문구와 저장 결과를 유지한 채 `writing_status=failed`, `writing_error=<예외종류>`로 드러냅니다. 완료 상태를 만들거나 적용기 예외로 업무 재실행을 유도하지 않습니다. 작성기는 순수 메타데이터 부착이며 DB 저장 성공/트랜잭션의 권위가 아닙니다.
- web notices는 기존 필드에 `response_status/question_status` enum만 추가 투영합니다. response의 scope/evidence/workflow/token과 내부 실행 참조는 공개하지 않습니다. writer가 없는 과거 알림의 상태를 추정하지 않습니다.

로컬 수정 검증: 기존73 + 신규31 = **104/104 = 100%**, 원문 호환 **5/5 = 100%**. [수정 결과·RED/GREEN·미완료 경계](../records/reports/2026-10-24_monitoring-fix-case-notices.md). 실DB/채널/운영 완료는 아닙니다.

검증은 DB·외부 접속 차단 unit 대역으로 한정합니다. 실제 모델·DB commit/outbox 배달·고객 후속 권한/TTL/순서 역전·운영 환경 검증은 남습니다.
