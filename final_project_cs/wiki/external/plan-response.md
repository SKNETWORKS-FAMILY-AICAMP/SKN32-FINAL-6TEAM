---
type: contract
title: 계획서 접수·확정 최종 응대 어댑터
status: draft
domain: travel
---

# 계획서 응대 연결 계약 — 2026-10-24

공통 [여행 응대](travel-response.md)의 ResponseInput/ResponseResult를 재사용합니다. 기존 intake/confirm 응답 키와 값, 고객 운영시간, 승인·고정 항목·누락/조회실패 근거는 변경하지 않습니다. 선택적인 `response`만 추가합니다. 내부 request/scope/원문/예약번호/토큰/오류 상세를 새 고객 response에 투영하지 않습니다. 기존 상세 검토 화면의 원래 자료 계약을 삭제하거나 재작성하지 않습니다.

- 실제 pipeline.view의 review는 `needs_input`/`review_required`이며 등록 완료가 아닙니다. ready=true도 승인·등록을 대신하지 않습니다. reading은 진행 중, fatal은 `failed`입니다. 검사 오류·blocked 근거는 실패 종결로 남깁니다.
- confirmed 접수 행만으로 저장 완료를 주장하지 않습니다. confirm handler가 _create_trip의 트랜잭션 종료 후 여행을 다시 읽고, mark_confirmed의 트랜잭션 종료 후 소유자·revision·여행 연결을 재조회한 경우에만 `registered`/`answered`를 표현합니다. 재조회 불일치/누락은 성공 응답을 만들지 않습니다. 예외는 기존 오류 경계로 전달하며 업무를 재시도하지 않습니다.
- 중복 confirm은 기존 여행 소유권과 재조회 결과를 재사용하고 create/mark/model을 다시 실행하지 않습니다. 공통 작성기는 I/O·LLM·prefill 적용·상태 갱신을 하지 않습니다. 실행/승인/고정 항목 스냅샷은 내부 결과에 사본 보존합니다.
- 고객 `response`는 answer, completion, question_status, execution_status만 허용합니다. 공통 결과 전체를 노출하지 않습니다. 기존 API status/스키마 의무 필드는 유지합니다. confirmed view는 확인된 접수 상태만 표시하며 저장 재확인 전에는 완료 문구가 없습니다.

## 별도 생성·등록 입구

- `/v1/trips/plan`의 `drafted`는 `plan_generated`/`needs_input`입니다. 생성기 판정 통과는 저장·등록 완료가 아닙니다. 기존 status/draft/planner/coverage/checks와 trip 모양은 보존하고 `response`만 추가합니다.
- 접수가 없는 생성 입구는 접수 행을 합성하지 않습니다. 별도 `generated_payload`와 `registered_plan_payload`를 사용합니다. 등록 어댑터는 handler가 실제 생성 후 별도 연결로 재조회한 여행 id·고객·양의 정수 판을 검증하며 I/O를 하지 않습니다. 중복 요청도 권한·소유권 확인 후 저장된 여행만 재조회하여 모델·생성을 반복하지 않습니다.
- 웹 `/v1/web/trip-intakes/{intake_id}/plan`은 기존 고정 일정 병합·설문을 유지합니다. 생성 후 여행 재조회, 접수 연결 후 scoped 접수/여행 재조회가 모두 일치해야 `registered`입니다. 중복 경로에서도 링크와 판을 재검증합니다. 저장·연결·조회·문구 오류는 완료로 바꾸지 않으며 작성 실패 뒤 재생은 업무를 반복하지 않습니다. JSON과 SSE result는 같은 선택 response를 냅니다.
- tenant API는 기존 `trip:write` dependency, 웹은 기존 고객 인증과 scoped draft를 유지합니다. 다른 고객 여행을 가리키는 멱등 키 결과는 성공 응답을 만들지 않습니다. 내부 id·토큰·원문은 새 response에 넣지 않습니다.

로컬 unit만 검증합니다. [별도 plan 정상입구 검증 보고서](../records/reports/2026-10-25_plan-generation-response.md)에 기존 318건 + 신규 42건 단일 실행, TDD 로그와 한계를 남겼습니다. 외부 HTTP/LLM/실DB 적용·앱·서비스·배포는 금지 범위입니다. root wiki/index/handoff 갱신은 부모 담당입니다.
