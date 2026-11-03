---
type: contract
title: 고객 웹 응대 상태 소비 계약
status: draft
domain: travel
---

# 고객 웹 응대 상태 소비 — 2026-10-24

담당: frontend 응대 소비 child. 검토자: 부모 매니저·API 담당(독립 검토 대기). 기존 공통 [응대 계약](travel-response.md)의 선택 필드를 소비하며 API 버전·필수 요청·업무 상태를 바꾸지 않습니다.

## 입력·보존

- 문의 JSON/SSE result·duplicate·저장 chat reply와 알림 목록의 선택 `response_status`는 `complete|partial`, `question_status`는 `answered|needs_input|unsupported|failed` 배열만 허용합니다. 없으면 기존 화면 그대로이며 성공을 추정하지 않습니다. 잘못된 신규 enum/배열은 고정된 계약 오류로 거부하고 원값을 오류 문장에 싣지 않습니다.
- 접수 GET·edits·restore 등 조회 결과 및 confirm/plan 결과의 `response`는 `answer`, `completion`, `question_status`, `execution_status`만 소비합니다. execution enum은 현재 생산자의 `reading|review_required|confirmation_recorded|registered|failed`만 허용합니다.
- 화면용 객체에는 scope/request/evidence/workflow/token 등 추가 원문 필드를 복사·펼치거나 JSON 렌더링하지 않습니다. answer는 기존 API의 고객용 문장으로 일반 React 텍스트만 렌더링합니다. 기존 개발 전용 basis 표시 정책을 새 상태 표시로 확장하지 않습니다.
- 저장된 대화 및 탭 내부 보관 응대 상태도 같은 allowlist로 읽습니다. 신규 상태를 누락하는 기존 서버는 호환하되, 명시된 잘못된 상태를 이전 정상 상태로 덮지 않습니다.

## 최소 표시·업무 경계

- 문의 답변/알림 본문 바로 아래에 짧은 보조 문장. partial은 ‘일부 확인이 필요해요’; needs_input/unsupported/failed는 각각 추가 입력·지원 범위·확인 실패를 짧게 덧붙입니다. complete는 업무 등록·실행 완료를 뜻하지 않으므로 완료 배지를 만들지 않습니다.
- 접수 검토 결과는 기존 계획 확인 안내 위치에서 response.answer와 상태를 보여 줍니다. reading/review_required는 아직 등록 전, confirmation_recorded는 현재 여행 재확인이 필요한 기록 상태로 구분합니다. registered는 confirm 결과 또는 서버의 실제 확인 상태와 맞을 때만 등록 결과 자리에서 보여 줍니다.
- confirm/plan 이후 여행 화면으로 이동하는 기존 흐름을 유지하면서 고객용 등록 응대 문장을 전달합니다. 토큰·원문 scope를 URL/브라우저 저장소에 추가하지 않습니다.
- 등록 요청의 소유자는 실제 발신 시점(최초 게스트 세션 생성 이후)의 세션과 세대입니다. 요청 중 세션 교체·로그아웃·A→B→A 재진입이 있으면 늦은 결과를 메모리에 저장하거나 상위 호출부에 성공 반환하지 않고 고정 `stale_registration_session` 오류로 거부합니다. 이동·후속 사용도 성공 반환 경계에서 차단합니다. SSE 재연결과 CSRF 재시도도 다른 세대로 요청을 옮기지 않습니다. 같은 세션의 정상/중복 응답과 legacy response 부재는 유지합니다. CSRF 값·원문 응대·세션 식별자는 오류·로그·URL·저장소에 출력하지 않습니다. 서버의 이미 수행한 등록을 취소하거나 재실행했다는 뜻은 아닙니다.
- 새 상태 문장은 승인·등록 가능성·제안 선택·재실행·알림 클릭 자동 focus를 결정하지 않습니다. 기존 선택 질문/알림 경계와 디자인을 유지합니다.

## 검증·승인 경계

Vitest에서 실제 gateway JSON/SSE·duplicate·서버 대화 재조회/탭 보관·알림 투영·접수 및 confirm 응대와 표시 문장을 RED→GREEN으로 검증합니다. npm package-lock/엔진을 확인하고 관련·전체 unit, 타입 검사·빌드를 실행합니다. 앱/서비스/브라우저 기동·실모델·실DB·외부 HTTP·배포는 승인되지 않았으며 화면은 미확인으로 보고합니다. 루트 wiki/index/handoff 통합은 부모 소유입니다.
