---
type: report
title: 감시 혼합 결과·proposal 검증 및 기본 Case 성공 안내 연결 수정
status: draft
domain: travel
---

# 모니터링 결함 수정·기본 Case 안내 연결

2026-10-24 23:41 KST. 로컬 격리 unit 검증 결과입니다. 부모 독립 검토와 실DB·채널·운영 검증은 별도이며 배포 완료를 뜻하지 않습니다.

## 결과·정확한 수

| 검증 범위 | 결과 |
|---|---:|
| 기존 지정 73개 nodeid 보존 회귀 | **73/73 = 100%** |
| 신규 결함·실제 적용기·notices 시험 | **31/31 = 100%** |
| 위 고유 node 합계 | **104/104 = 100%** |
| 수정 직전 dirty 적용기와 원문 payload 직접 비교(별도) | **5/5 = 100%** |

[JUnit 기반 counts.json](../evidence/2026-10-24_monitoring-fix/counts.json)의 기존 nodeid 누락은 0입니다. 합계에 다른 child 시험을 합산하지 않았습니다. 전체 서비스 검증률의 분모는 모릅니다.

## 변경 내용

- `WatchBatch._arguments`가 항목별 `item_id/kind/reasons/checked_at`를 안내 전용 `batch.outcomes`로 싣고, 기존 적용기가 이를 `AppliedAction.summary.batch.outcomes`에 보존합니다. `decide`, 실행 순서, 실제 적용 조건, 재검증, retry 재개 의미는 바꾸지 않았습니다.
- `response/monitoring.py`가 일부 저장판과 전체 완료를 분리합니다. applied+no_alternate/recheck_failed/retry는 failed/partial, asked는 awaiting_choice/partial, unknown 및 미등록 kind는 unknown/partial입니다. 모든 종류가 섞여도 unknown이 우선하며 실제 `saved_version`과 원래 summary는 남습니다. 옛 batch의 asked/retry 및 consents 표현도 읽습니다.
- proposal ref는 정확한 현재 trip prefix, 비어 있지 않은 단일 proposal suffix, 저장된 summary 또는 batch.asked의 proposal_id 일치를 확인합니다. 타 trip, 빈 suffix, 다른 proposal, 추가 colon은 unknown으로 남깁니다. 이 검사는 응대 상태용이며 업무 승인/선택 실행 권한을 추가하지 않습니다.
- 기본 Case `_version_notice`의 기존 outbox 한 건만 장식합니다. 기존 `trip.notice` topic, `{trip_id}:v{version}` 키, 원문·링크·판·rollback·guardian과 승인 필드는 유지합니다. 저장 후 동일 `AppliedAction.outbox` 반환으로 코어의 기존 트랜잭션 경로를 그대로 사용하며 tick 재발행은 추가하지 않았습니다.
- `_open_ask/_open_consent`의 기존 신규 메시지만 awaiting_choice로 장식합니다. 기존 `already` 분기에서는 작성기를 부르거나 알림을 다시 만들지 않습니다. 두 번 호출해 outbox 한 건임을 시험했습니다.
- 새 `action_notice`는 상태 계산과 공통 writer 전체를 실패 경계 안에 둡니다. 작성 실패 시 기존 payload와 실제 저장 결과를 유지하고 `writing_status=failed/writing_error=<예외종류>` 및 타입 전용 오류 로그로 드러냅니다. 원문 예외/비밀 문자열은 기록하지 않습니다. 완료 enum을 지우고 업무를 재실행하지 않습니다. 실패 표시는 내부 outbox metadata이며 고객 notices에 내부 오류를 노출하지 않습니다.
- 공유 `trip_api.py`에서는 **web_notices 함수만** 부분 패치했습니다. 기존 allowlist 필드에 검증된 `response_status/question_status` enum만 더하고 scope/evidence/workflow/token/실행참조는 복사하지 않습니다. writer가 없는 과거 알림은 상태를 추정하지 않으며 잘못된 신규 enum은 거부합니다. `_web_view`, 메시지 API, intake는 건드리지 않았습니다.

## TDD와 실행 증거

계약을 먼저 [감시 응대 계약](../../external/travel-monitoring-response.md)에 명시한 뒤 다음 RED→GREEN을 실행했습니다. [증거 폴더](../evidence/2026-10-24_monitoring-fix/)에 고유 로그를 보존합니다.

1. `red01`: 혼합 summary 여섯 조합이 전부 applied로 잘못 표시되는 최초 재현 → `green01`.
2. `red02`: 타 trip/빈 값/다른 제안/추가 suffix 및 producer outcomes 누락 재현 → `green02`.
3. `red03`: 기본 성공 outbox 메타데이터 누락과 writer 실패 표시 부재 → `green03`.
4. `red04`: action ask/consent와 실제 notices endpoint 상태 투영 부재 → `green04`.
5. `red05`: writer 본문뿐 아니라 상태 계산 예외도 저장 뒤 밖으로 탈출하던 결함 → `green05`.
6. `red06`: 옛 consents batch를 complete로 올리던 결함 → 최종 GREEN.

[최종 로그](../evidence/2026-10-24_monitoring-fix/final.log)·[JUnit](../evidence/2026-10-24_monitoring-fix/final.xml)·[실행 전후 해시/argv](../evidence/2026-10-24_monitoring-fix/source-hashes.json)에서 104 passed, exit 0, source stable=true를 확인했습니다. [원문 비교 로그](../evidence/2026-10-24_monitoring-fix/compat.log)는 자동 변경/고객 선택/rollback/ask/consent의 기존 payload를 새 메타데이터 제외 후 수정 직전 백업과 직접 비교한 5 passed입니다.

실행기는 기존 `monitoring-unit-run.py`를 사용합니다. socket.connect/connect_ex/create_connection와 psycopg.connect를 차단하고 정확한 stdlib Windows socketpair code object만 허용합니다. 앱 loopback 차단·socketpair 자체를 선확인하며 standalone_services/이동 엔진 초기화를 기존 fixture와 맞췄습니다. HTTP 앱/서버는 띄우지 않고 `build_trip_router().routes`의 실제 notices endpoint를 직접 호출했습니다. 새 의존성 설치나 프로젝트 설정 우회는 없습니다.

재현 명령: 프로필 scratch `travel-writing-s1-venv/Scripts/python.exe`로 [verify.py](../evidence/2026-10-24_monitoring-fix/verify.py)를 실행합니다. 정확한 선택 파일·명령은 source-hashes.json에 있습니다. `git diff --check`는 관련 tracked 파일에서 exit 0이며 Git의 기존 LF→CRLF 경고만 있었습니다.

## 수정 파일·보존

- 수정 `app/domains/travel_ops/components/response/monitoring.py`
- 수정 `app/domains/travel_ops/components/watch/trip_watch_batch.py`
- 수정 `app/domains/travel_ops/components/actions/itinerary_actions.py` (안내 장식·summary 복사만)
- 부분 수정 `app/domains/travel_ops/entry/trip_api.py:web_notices`
- 신규 `tests/unit/travel/test_monitoring_fix_contract.py`
- 수정 계약 `wiki/external/travel-monitoring-response.md`
- 신규 이 보고서 및 `wiki/records/evidence/2026-10-24_monitoring-fix/`

편집 전 dirty/untracked 대상 5개를 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/monitoring-fix-backup/`에 보존했습니다. child delta는 증거 폴더의 `*.child.diff`입니다. 공유 trip_api는 sibling 변경을 덮지 않고 web_notices 함수 범위 diff만 남겼습니다. root wiki/index/handoff는 부모 담당이며 수정하지 않았습니다. conversation의 trip_messages/decision_unit, 공통 writer/public, pending, Core/Controller/DB schema/업체 거래는 변경하지 않았습니다.

## 미완료·한계

- 실DB commit/rollback 및 UNIQUE outbox 중복 제약과 배달은 미검증입니다. unit은 실제 적용기에 동일 connection이 전달되고 저장 후 정확히 한 outbox를 반환함, 같은 기준판 재실행은 기존 ActionConflict로 막혀 append가 한 번임을 확인했습니다. 이것을 실DB 원자성 검증이라고 부르지 않습니다.
- 기존에 summary에서 이미 소실된 과거 batch 결과를 복구하거나 기존 outbox를 재장식·재발행하지 않습니다. 신규 처리에서 결과가 남도록 고쳤습니다.
- 알림 뒤 ‘왜 바꿨어?’ 읽기, TTL/권한/역전 검증은 다른 child 담당이며 이번 완료 범위에 넣지 않습니다.
- 실모델 품질, 실제 채널·UI 렌더링, 앱/서비스, 운영 배포는 미검증입니다. 외부 DB·모델 호출, 서비스 기동, 커밋·푸시는 하지 않았습니다. 부모가 결합 트리에서 최종 재실행·독립 검토해야 합니다.
