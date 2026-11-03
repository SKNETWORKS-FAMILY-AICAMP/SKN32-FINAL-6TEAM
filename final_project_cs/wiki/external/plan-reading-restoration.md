---
type: contract
title: 계획 읽기 기준선 선별 복원 계약
status: draft
domain: travel
---

# 계획 읽기 복원 경계 — 2026-10-24

참고 Git의 D-025(`7d503bfb6`)와 `502da503c`를 현재 코드와 대조하여 복원합니다. 당시 평가·배포 기록은 현재 실행 증거가 아닙니다. 전체 라이팅 완료를 뜻하지 않습니다.

- 모델은 최종 정정이 반영된 계획·이동·조건·성향·요청 조각을 읽습니다. 코드는 원문 인용·시각·범위를 검사하고 기존 날짜/장소 조회 경로에 전달합니다. 정정된 계획에 옛 규칙 항목을 다시 끼워 넣지 않습니다.
- 원문에 없는 인용을 버리고 수를 기록합니다. 원문 기반 규칙 시각 보충은 같은 줄만 허용합니다. 고객 운영시간 편집·장소 변경 시 운영시간 제거·잠금·예약 보호는 유지합니다.
- 모델 연결/시간 초과는 `reading_model_failed`로 드러내며 같은 모델을 줄 읽기로 다시 부르지 않습니다. 답 모양 오류는 줄 읽기를 한 번 허용하되 실패를 성공 미리보기로 숨기지 않습니다.
- 스트리밍은 주입된 정책의 첫 응답·멈춤·전체 한도를 공급자에 전달하며 근거 인용이 나온 줄 수만 진행으로 냅니다. 실제 공급자 스트림/유료 전환은 별도 기반 구현을 요구합니다. 모델·임계값·경로를 새 운영 기본값으로 하드코딩하지 않습니다.
- 빈칸은 식당/활동/이동/계획/고객 확인으로 연결합니다. 담당은 제안만 반환합니다. 자동 채움은 고객의 장소·시각·잠금·예약을 대신 바꾸지 않습니다.

## 공유 의존과 적용 조건 (구현 전 기록)

1. `trip_api`는 현재 읽기 전용 chat만 주입합니다. D-025 에이전트와 스트리밍 어댑터를 실제 입구에서 주입하는 변경이 필요합니다. 이 절은 공유 입구를 변경하지 않고 명시적 pipeline 인자 경계를 검증합니다.
2. config에는 `travel.intake_reader`/`travel.intake_reading`이 없습니다. 실제 활성화 전 관리 설정·검증된 공급자·정책을 연결해야 합니다. 누락 정책을 임의 숫자로 대체하지 않습니다.
3. DB `intake_claims.method` 제약은 `llm_agent` 허용을 요구합니다(참고 `905_intake_claims_llm_agent.sql`). 기존 SQL 번호 중복 조사 전 신규 SQL을 만들지 않으며 DB에는 적용하지 않습니다. 본 절의 순수 unit 통과는 DB 저장 가능 증거가 아닙니다.
4. `502da503c`는 `model_stream`·`ollama_chat`·`llm_failover` 및 `llm_spans` 계약 변경을 동반합니다. 공유 인프라 무검토 통복사는 하지 않습니다. 주입된 structured_stream 경계를 넘는 실제 공급자 failover 복원은 별도 검증 대상입니다.
5. 후속 `bb321b0cd` 성향 전달·`93fe02793` 즉시 시작/출발지·숙소 공동 추천 등은 별도 의존이며, 이 절에서 현재 구현으로 과장하지 않습니다.

검증은 네트워크·DB 연결 차단 격리 unit만 수행합니다. root/index/handoff, conversation, response 작성기는 수정하지 않습니다.

## 실제 API 연결 절 계약 (2026-10-24, 구현 전)

- 정상 `POST /v1/web/trip-intakes`의 background `process`에 같은 조립 경로의 chat을 agent로 전달합니다. `process`는 `travel.intake_reader.mode/num_predict`와 `travel.intake_reading`의 첫 응답·멈춤·전체·진행 정책을 읽고 `read_source`에 전달합니다. 정상 구성 mode는 `on`; 누락·잘못된 설정·미조립 모델은 `reading_not_configured`로 접수 실패이며 규칙 성공으로 바꾸지 않습니다. 명시적 `off/shadow`는 현재 관리 설정의 선택일 때만 허용합니다.
- 모델명·주소·유료 키·호출 예산은 기존 조립 설정을 재사용하며 새로운 모델 기본값을 만들지 않습니다. 정책 수치는 참고 Git 설정에서 선별 복원하고 출처를 기록합니다. 읽기 모드는 정상 입구에서 활성화하되 실모델·DB 적용 완료를 뜻하지 않습니다.
- 공급자의 실제 HTTP/SDK stream을 연결하고 대역으로 검증합니다. 유료 넘김은 기존 breaker·PII 가림·호출 예산을 유지합니다. stream 정책이 있는 요청을 비스트림 성공으로 바꾸지 않습니다.
- 읽기 실패(`reading_model_failed`)는 fatal, 장소/검사 조회 실패는 기존 review·review_error/조회 근거에 남고, 일정 등록은 별도 confirm/plan 요청입니다. 읽기만으로 일정 등록/자동 채움/숙소 추천을 실행하지 않습니다. `sources[].reading.agent`에 결과를 추가하되 기존 reading.llm의 키는 보존합니다.
- SQL 905는 번호/동일 변경 중복을 검사한 후 파일로만 작성하며 DB에는 적용하지 않습니다. 고객 운영시간 dirty·원문 정정·예약 보호와 멱등성/고객 격리를 보존합니다.

## 공급자 안전 보완 계약 (2026-10-24, 코드 수정 전)

- 스트림 collector는 취소 상태를 공급자와 공유합니다. timeout 이후 새 read를 시작하지 않고, 헤더/SDK 응답이 늦게 도착하면 읽지 않고 소유자가 즉시 닫습니다. close는 caller의 deadline을 막지 않는 별도 정리 작업입니다. producer는 iterator를 finally에서 닫습니다. transport가 이미 블로킹 중이면 Python 스레드를 강제 종료하지 않으며, 해당 transport timeout/반환까지 daemon worker가 남을 수 있습니다. 자원 정리가 결국 완료된다는 보장은 transport의 반환/close 완료에 의존합니다.
- reader 스트림은 failover 전체 절대 deadline 하나를 공유하고 매 시도 직전 remaining을 확인하여 backend에 전달합니다. 재시도·API 전환이 시간을 새로 부여하지 않습니다. 기존 비스트림 계약은 유지합니다.
- 유료 reader의 **매 시도마다** 예산을 reserve합니다. gate 없음/예외는 fail-closed입니다. 기존 global fail-open budget을 reader용으로 사용하지 않고 별도의 엄격한 gate를 조립합니다.
- 호출 성공 provenance에는 실제 backend/model을 담고 agent 보고에 사용합니다. primary 모델을 유료 성공 모델처럼 기록하지 않습니다. 직접 로컬 공급자의 성공도 같은 메타데이터를 보고합니다. 직접 OpenAI 어댑터를 reader에 주입해 엄격한 gate를 우회하는 경로는 거부합니다.
- 답 모양 오류 후의 기존 줄 읽기에도 reader 전용 `reader_json` 정책/매 시도 reserve를 적용합니다. 다른 업무의 `chat.json`은 바꾸지 않습니다. 이 호환 비스트림 경로는 다음 시도 시작을 절대 deadline으로 제한하지만 진행 중인 호출은 기존 transport timeout에 의존합니다. 스트림과 같은 강제 caller 시간 보장을 주장하지 않습니다.
- 이름·예약번호·구분자 없는 전화번호를 포함한 자유 입력의 완전 마스킹은 보장할 수 없습니다. 따라서 reader 외부 fallback은 `travel.intake_reader.external_fallback_enabled: false`로 기본 차단합니다. 차단은 raw 원문뿐 아니라 이전 chunk를 담은 system state에도 적용합니다. 기존 다른 업무 API는 차단하지 않습니다. 이 값을 true로 해제하는 일은 후속 사용자 확인 대상이며, 현재 작업에서 승인/해제하지 않습니다. true는 완전 비식별화 보장이 아니라 명시적 외부 전송 허용입니다.
- 정상 mode=on은 모델을 부르거나 `llm_agent` claim을 쓰기 전에 DB의 실제 `intake_claims.method` CHECK 제약이 `llm_agent`를 허용하는지 명시적으로 점검합니다. pending 905 미적용/검사 오류/확인 불가는 `reading_schema_not_ready`로 실패하며 규칙 reader로 조용히 전환하지 않습니다. 이 작업에서는 DB 조회도 대역만 사용하며 migration 적용은 하지 않습니다.

## 스트림 정책 생략 우회 폐쇄 계약 (2026-10-25, 코드 수정 전)

- 하위 `read_source(agent=FailoverChat, agent_mode='on'/'shadow')`도 reader 경계입니다. `reading_stream` 생략 시 일반 업무용 `structured()`로 내려가면 외부 기본 거부와 strict reader 예산을 우회하므로, reader 전용 `reader_json` 인터페이스를 가진 정책 wrapper에는 명시적 스트림 정책을 필수로 요구합니다. 정책 누락은 모델 호출·global/reader reserve·줄 reader 전환 전에 명시 실패(`IntakeRejected.code=reading_model_failed`, 원인 RuntimeError)합니다.
- 정상 `process`의 검증된 정책 주입은 유지합니다. 일반 업무 API `FailoverChat.structured()` 정책은 변경하지 않습니다. 명시적 `agent_mode='off'`의 기존 줄 읽기는 `reader_json` 안전 정책을 유지하며, 정책 wrapper가 아닌 기존 로컬/순수 대역의 비스트림 `structured()` 호환은 보존합니다. 누락을 감추려고 `on`을 `off`로 바꾸거나 조용한 규칙/줄 fallback을 추가하지 않습니다.
- reader 외부 전송 기본값 false·매 유료 시도 strict reserve·기존 취소/DB driver timeout 한계는 그대로입니다. 이번 절은 독립 재현 1건의 로컬 폐쇄만 다루며 모델·DB·HTTP 앱서비스·운영 활성화는 검증하지 않습니다.

## 현재 산출물과 한계

[이전 순수 경계 절 보고서](../records/reports/2026-10-24_plan-reading-restoration.md)는 API 미활성 체크포인트입니다. [API 연결 절 보고서](../records/reports/2026-10-24_plan-reading-api-activation.md)에서 정상 입구→process→에이전트→실제 스트림 어댑터의 로컬 연결을 검증했습니다. 외부 모델/실제 DB 저장·SQL 적용·운영 활성화는 검증하지 않았으며 자동 채움·숙소 추천·화면 변경은 이 절의 범위가 아닙니다.

[공급자 안전 보완 보고서](../records/reports/2026-10-24_reader-provider-safety.md): 현재 결합 트리에서 기존 318/318·신규 안전 25/25 통과, 확장 전체 398/402(HTTP 격리 차단 4실패)입니다. reader 외부 fallback은 기본 차단이며 schema 미준비는 명시 실패합니다. 실DB·실모델·운영 적용 완료가 아닙니다.
