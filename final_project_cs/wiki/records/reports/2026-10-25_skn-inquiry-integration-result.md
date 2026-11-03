---
type: report
title: SKN pin 문의 의미 통합 결과와 소유 밖 chat reload 누락
status: documented
domain: travel
---

# 결론

**문의 소유 경계의 핵심 hunk는 통합했으나 전체 수락은 아직 실패입니다.** 현재 단일 실행은 **280/281 = 99.64% 통과, 실패 1, 오류 0, skip 0**입니다. 실패는 소유 밖 `conversation/chat_log.py:48`의 공개 reply allowlist가 `response_status/question_status`를 버리는 실제 재조회 경로입니다. 이 파일은 명시 소유 목록 밖이므로 수정하지 않았습니다. 부모가 이 hunk를 소유하거나 소유를 확장한 뒤 동일 manifest로 재실행해야 합니다.

## 기준·문서 선행

- candidate: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/skn-develop-step1-20261025-014848/candidate`
- pin: `325ba25d88c91ce97da61f2bda635e5888fe3b40`
- 증거: 상위 `evidence/inquiry/manifest.json`, `final-inquiry-single.log/json`, `run.py`, `environment-comparison.json`, 각 RED/GREEN 로그.
- 구현 전 [문의 통합 계약](2026-10-25_skn-inquiry-integration-contract.md)을 추가했습니다. 원본 cs `2026-10-25_skn-pinned-writing-branding-independent.md`와 상위 step1 `report.md`/classification/conflicts를 읽고 실제 base/local/incoming 대조를 사용했습니다. 원본 과거 시험 총합은 재사용하지 않았습니다.

## 변경 소유

- `conversation/read_requests.py`: 원래 질문 사본·순서·checked_at·computed target을 순수 writer로 전달. 기존 clock/anchor·고객 선택 장소 안내·weather/outdoor·query/focus 보존. 한 대상이라도 날씨 조회 실패면 해당 질문 `failed`, 전체 `partial`; 성공한 독립 질문 유지.
- `conversation/trip_messages.py`: 실제 저장 여행의 tenant/customer/trip scope 전달, 읽기 전용 change reader 주입. Case chat_reply에 공개 enum 저장, duplicate에 enum만 재생. 기존 pick/focus/edit_goal 보존.
- `conversation/decision_unit.py`: `change_explanation` 읽기 종류·모델 안내·질문별 변경 별칭 검증·단독 질문 정규화만 병합. 저장 원인 정보는 마스킹하여 자료로 제공. 모호한 변경 후보를 첫 실행으로 승격하지 않으며 **mixed business clarify는 원형 유지**. 최신 편집/도착/완료/새 요청 분리 유지.
- 신규 `conversation/change_read.py`: 원본 로컬 신규 모듈을 검토 후 이식. 현재판·대상/선택/focus/TTL·scoped 연결 Case의 정확 result_ref를 SELECT 재조회. 출처/확인시각 누락과 미적용은 실패. 추가로 matching ref가 있어도 summary.status failed/unknown/asked면 적용 증거로 인정하지 않는 회귀를 RED 후 보강했습니다. 최신 적용기가 status 없이 저장하는 정상 summary는 허용합니다.
- `entry/trip_api.py`: 최신 파일을 다시 읽고 **중첩 `_web_view`만 부분 패치**. JSON/SSE 공용 공개 enum과 developer basis 신규 scope/request 제거. 계획 handler 변경은 다른 child 소유이며 건드리거나 되돌리지 않았습니다. `owned-web-view.patch`가 이 child의 정확 hunk입니다. `owned-tracked.patch`에는 생성 시점의 공유 파일 다른 child hunk가 포함될 수 있으므로 전체를 문의 소유로 재생하면 안 됩니다.
- 신규 시험: `test_skn_inquiry_integration.py`, `test_skn_change_explanation.py`. 후자는 보존한 로컬 변경 설명 시험을 후보 고유 이름으로 가져오고 독립 합성 item fixture 및 신규 음성 경계를 추가했습니다.
- `case_dispatch.py`, `time_anchor.py`, `weather_read.py`는 **pin SHA256과 동일**합니다. weather 전체 덮어쓰기를 하지 않았습니다. time_anchor의 로컬 종료시각 누락 정책 차이는 자동 채택하지 않았습니다.
- 공유 `response/{writing,public}`·composition·파이프라인·계획·감시·프런트·공급자는 수정하지 않았습니다.

## 정확 검증

현재 최종 실행은 14개 명시 시험파일에서 **고유 nodeid 281개**를 수집했습니다. 중복 nodeid 없음, 실행 전후 conversation 전체/공유 trip_api/선택 시험 SHA256 동일, 네트워크·DB 차단 audit 시도 0건입니다. root conftest를 제외하고 socket connect/connect_ex/create_connection/server bind와 psycopg.connect를 차단했으며 Windows 표준 socketpair의 정확 code object만 예외입니다. 서비스/HTTP 서버는 띄우지 않고 실제 중첩 endpoint와 SSE body_iterator를 직접 실행했습니다.

보존 회귀는 최신 `test_read_requests`, `test_time_anchor`, `test_chat_saved_edit_weather`, `test_outdoor_fact_reads`, decision now/target/unsupported, fact recovery, implicit reply recency, unfound place pick을 포함합니다. JSON/SSE·normal/dev·duplicate·기존 status 없는 답, Case 저장 reply·중복 재생, 변경 설명 정상/외국 tenant·customer/잘못된 trip ref/판 이동/누락 출처·시각/모호한 선택·TTL·미적용 summary를 검증했습니다.

기능 RED는 writer 미연결, scope 미전달, 공개 enum 저장·재생 없음, `_web_view` 투영 누락, 날씨 실패인데 complete, 변경 설명 미구현, 원인 prompt/모호성 및 failed/unknown/asked 오인 경계에서 관측 후 GREEN했습니다. 처음 web 시험은 합성 Settings 미설정 오류였으므로 기능 RED로 세지 않았고 비밀 .env를 복사하지 않은 합성 설정 runner로 다시 유효 RED를 남겼습니다.

기존 venv는 현재 candidate requirements와 대조했습니다. 설치된 직접 의존성 18개 버전은 모두 일치합니다. 전체 requirements 환경 설치/수락을 뜻하지 않으며 미설치 항목도 비교 JSON에 보존했습니다. 추가 설치·네트워크 호출은 하지 않았습니다.

## 충돌·미해결

- conversation 소유 7경로의 기존 기계적 분류: 수정 충돌 4파일/38 marker block + add/add 충돌 2파일(time/weather) + 로컬 신규 1파일(change_read). 즉 충돌 파일 6개. 이는 기능 결함 수가 아닙니다.
- 공유 trip_api 전체 파일을 포함하면 수정 충돌 5파일/42 block + add/add 2파일 = 충돌 7파일입니다. 계획 handler 충돌을 문의 담당이 모두 해결했다는 의미가 아닙니다.
- 현재 시험으로 재현된 **미해결 누락 1건**: `tests/unit/travel/test_skn_inquiry_integration.py::test_saved_reply_metadata_survives_actual_chat_reload`. `chat_log.recent`의 기존 focus/pick allowlist를 보존하면서 검증된 두 enum을 공개 투영해야 합니다. 공개 helper 소유 변경은 하지 않았습니다.
- 실행 전후 파일 hash 안정은 해당 최종 실행에 대한 증거이며 부모의 최종 전체 결합 트리 검증을 대신하지 않습니다.

원본 `C:/_proj/final_workspace`의 관련 소스 7경로는 보존 manifest SHA256과 일치했습니다. 원본에는 고유 보고서 추가만 수행합니다. DB/실모델/외부 네트워크/서비스/배포/커밋/푸시는 실행하지 않았습니다. 전체 구현·실DB 저장·운영 배포 완료 주장은 하지 않습니다.
