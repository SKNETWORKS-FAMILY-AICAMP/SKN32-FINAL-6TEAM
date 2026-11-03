---
type: report
title: 감시 고객 전달 공통 응대 연결 — monitoring child
status: draft
domain: travel
---

# 감시 전달 라이팅 연결 결과

2026-10-24 23:19 KST. monitoring child의 로컬 구현·격리 unit 결과입니다. 부모 소비자 검토·운영 승인은 별도입니다.

## 결과

**기존 pending 고객 메시지와 감시 실패 outbox에 공통 응대를 연결했습니다.** 별도 `response/monitoring.py`가 실제 실행 상태와 원값을 받아 기존 `ResponseInput → write_response → ResponseResult`를 사용합니다. 모델 호출이나 업무 실행을 추가하지 않았습니다. 전체 라이팅 에이전트/후속 기억/운영 배포 완료를 뜻하지 않습니다.

| 검증 묶음 | 실제 결과 |
|---|---:|
| 새 adapter·실제 pending/watch 연결 unit | 33/33 = 100% |
| 기존 감시 경합 | 1/1 = 100% |
| 기존 출발 감시·조립 | 9/9 = 100% |
| 기존 묶음 감시 | 15/15 = 100% |
| 기존 Phrase 캐시·원값·no-LLM 경계 | 15/15 = 100% |
| 위 고유 pytest node 합계 | **73/73 = 100%** |
| 수정 전 dirty 백업과 안내 payload/문장 직접 비교(별도) | **7/7 = 100%** |

집계는 [JUnit에서 파싱한 counts.json](../evidence/2026-10-24_monitoring-writing-child/counts.json)이며 기존 문의153·접수285와 합산하지 않습니다. 전체 프로젝트 검증률 분모는 미확정입니다.

## 실제 연결·보존

- `planning/pending.py`: `forecast_attention`, `ask_consent`, `_consented`의 선택지 재질문, `apply_or_ask`의 묻기/재검증 실패/저장 후 변경 안내, `choose`의 저장 후 안내를 기존 enqueue 자리에 연결했습니다. 기존 반환 상태와 문장/키/선택지/경고/되돌리기 값은 유지하고 response 스냅샷을 추가합니다.
- `watch/trip_watch_cases.py`: 실제 `run_case` 뒤 `_after_run`에서 Case/applied_actions와 최신 여행판을 다시 읽어 `CaseTickResult.responses`에 씁니다. `_defer_notice`, 단일/묶음 미해결의 기존 고객 outbox에 공통 adapter를 연결했습니다.
- `applied`는 저장 결과판이 현재판과 맞아야 합니다. Controller `resolved`나 저장 전 `trip_watch_batch.digest`만으로 적용 완료를 만들지 않습니다. 선택 대기·실패·unknown과 섞인 batch는 partial로 남기고 적용 기록/저장판/미완료 항목을 보존합니다.
- 원인/대상/판/선택지와 승인 상태·required_input_schema·resume_token은 복사 보존합니다. 기존 approval_status가 있으면 자동으로 바꾸지 않습니다. D-020 실제 판정의 on/off/미응답/pinned 경계를 unit으로 실행했습니다.
- 작성 실패를 `writing_failed`로 기록하며 업무를 재실행하거나 기존 Case를 실행 실패로 닫지 않습니다. 같은 pending 제안의 두 번째 호출은 기존 분기에 따라 안내를 다시 enqueue하지 않습니다. 이미 배달한 outbox 재전송은 기존 배달 루프 책임입니다.
- **Case 성공 변경 outbox의 소유자는 기존 적용기입니다.** 이 절은 그 outbox를 다시 만들거나 재작성하지 않습니다. 실행 후 재조회한 응대는 tick 결과로 노출하며, 실제 고객용 적용 완료 adapter 연결은 pending의 저장 후 enqueue 경로에서 검증했습니다. 기본 Case 성공 변경 outbox 전체를 공통 메타데이터로 옮기는 일은 action 소유자와 별도 검토가 필요합니다.
- 정기 안내 `trip_reminders.py`/Phrase, Core/Controller/action/거래/DB schema, 다른 child의 `response/writing.py`는 수정하지 않았습니다. 기존 batch digest도 수정하지 않았습니다.

## 변경 파일·기준선

구현 전 [별도 adapter 계약](../../external/travel-monitoring-response.md)을 작성했습니다. root wiki/index/handoff는 부모 담당으로 건드리지 않았습니다.

1. 신규 `app/domains/travel_ops/components/response/monitoring.py`
2. 수정 `app/domains/travel_ops/components/planning/pending.py`
3. 수정 `app/domains/travel_ops/components/watch/trip_watch_cases.py`
4. 신규 `tests/unit/travel/test_monitoring_response_adapter.py`
5. 신규 `wiki/external/travel-monitoring-response.md`
6. 이 보고서와 고유 evidence 폴더

기존 dirty 본체는 현재 프로필 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/monitoring-child-backup/{pending.py,trip_watch_cases.py}`에 편집 전 백업했습니다. child 자체 delta는 [pending diff](../evidence/2026-10-24_monitoring-writing-child/pending.py.child.diff)와 [watch diff](../evidence/2026-10-24_monitoring-writing-child/trip_watch_cases.py.child.diff)입니다. 기존 원인 simulation scope/경합/재검증 등 dirty 변경은 덮지 않았습니다. 최신 Git이나 배포 묶음을 복사하지 않았습니다.

## TDD·실행 증거

[증거 폴더](../evidence/2026-10-24_monitoring-writing-child/)에 RED01~10, GREEN 초기 회차, 최종 log/XML, runner와 비교 시험을 보관합니다. RED는 신규 adapter 부재 → pending 연결 부재 → watch 결과/안내 부재 → 재작성 중첩 → batch 안내 부재 → 나머지 pending 연결 부재 → 기존 승인 덮임 → 혼합 batch 성공 오표현 → 적용 대상 누락을 확인한 순서입니다. 뒤의 성공 로그로 실패 로그를 덮지 않았습니다.

- [최종73 실행 로그](../evidence/2026-10-24_monitoring-writing-child/monitoring-final.log), [JUnit](../evidence/2026-10-24_monitoring-writing-child/monitoring-final.xml)
- [수정 전 원값7 비교](../evidence/2026-10-24_monitoring-writing-child/monitoring-compat.log)
- [격리 runner](../evidence/2026-10-24_monitoring-writing-child/monitoring-unit-run.py): socket connect/connect_ex/create_connection와 psycopg.connect 차단. stdlib Windows socketpair의 정확한 code object 호출만 예외 허용하며 loopback 앱 연결 차단·socketpair 생성을 먼저 확인합니다.

실행 형식: 현재 프로필 scratch의 `travel-writing-s1-venv/Scripts/python.exe monitoring-unit-run.py <고유로그> <시험경로들> --junitxml=<고유xml>`. Python3.12.15/pytest8.4.2 기존 격리 환경을 재사용했으며 새 패키지 설치나 프로젝트 requirements 수정은 없었습니다. 정확한 argv는 최종 로그 첫 줄에 있습니다.

초기 확대 시험에서 root conftest 제외에 따른 composition_unbound 15건이 발생했습니다. 현재 tests/conftest.py·service_bindings를 읽고 scratch plugin에서 기존 wire_domain_teams/standalone_services를 명시했습니다. 그 뒤 조립 시험의 이동 엔진 상태가 남아 로컬 라우터 조회를 시도한 1건은 네트워크 가드가 차단했습니다. 동일한 기존 엔진 초기화 fixture를 시험 전후 재현한 뒤 최종73 전부 통과했습니다. 제품 코드를 격리 환경에 맞춰 우회 수정하지 않았습니다. 앱/서비스를 시작하지 않았습니다. `git diff --check`도 관련 기존 파일에서 통과했습니다.

## 남은 검증·경계

실제 DB append/commit/rollback과 outbox 배달, 실모델 품질, 실제 고객 채널, 알림 후 권한/TTL/순서 역전·장기 후속 기억, Core 성공 변경 outbox 메타데이터 연결은 검증하지 않았습니다. 일반 안내의 임의 문장 claim 검수기나 전체 agent를 새로 구현한 것도 아닙니다. 앱/서비스/외부 DB·모델 호출, 배포, 커밋·푸시를 하지 않았습니다. 추가 제품 결정 요청은 없으며 부모의 소비자 검토가 남습니다.
