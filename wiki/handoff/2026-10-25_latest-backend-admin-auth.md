# 2026-10-25 최신팀 backend/admin/auth 격리 병합 결과

## 결론
최신팀 `6c34589b4e34dede82e566d43b3757e127a5d5d9` 위 새 후보만 검증했습니다. **원본 backend/admin/auth 적용 HOLD·전체 GREEN 아님**입니다. 기준 fetch는 정식 safe_git/Python312/기존 MinGit로 성공했고, 기존 실행 서비스·DB·모델·외부 API는 시작/정지/접속하지 않았습니다. 설치·push·배포·원본 규칙 수정 없음입니다.

## 이번 결과 (과거 d0cc4f 후보와 분리)
- 후보: `C:\Users\kcxsz\AppData\Local\hermes\profiles\guguroute\cache\scratch\latest_backend_admin_auth\repo` (HEAD는 최신팀 pin, 검토 delta는 별도 index/tree와 정역 patch로 보존).
- 최종 backend/core/auth/정상 intake 진입 회귀 **1117/1121 = 99.6432%**, 실패4·error0·skip0·marker 제외29, exit1. 입력 1637개 전후 SHA 동일.
- 실패4는 이번 실제 traceback의 `service/socket bind denied`를 확인했고, 별도 **원문 최신팀 baseline**에서 동일 nodeid·동일 guard로 4/4 같은 차단을 재현했습니다. guard 해제/서비스 허용으로 통과시킨 것이 아닙니다.
- 수정 전 고객시간 RED 25개 exact identity 모두 최종 실행에서 **25/25 통과**입니다. `red25-final-exact-closure.json`에 원문 ID와 대조를 남겼습니다.
- 관리자 **41/41 시험 통과**, JSON·JUnit XML 각각41건. lint/typegen/tsc/unit/webpack 전체 build/후속 tsc 6개 exit0. 소스·설정·lock 54개 동결 SHA 전후 동일. 실제 관리자 로그인·설정 저장/예약 OFF readback 수락은 아닙니다.
- 이전 후보 시험 집합1004와 이번1121의 교집합 982개입니다. 이전 미선택 목록을 `prior-current-selection.json`에 남겼고 과거 외부probe 결과를 합산하지 않았습니다.

## 의미 병합
- `intake/pipeline.py`: 최신 `_kept_ends(source_rows,current_claims,rows)`를 보존한 뒤 해당 항목만 `_clear_hours_on_place_change`합니다. `keep_times`·`reflow`·공유 숙소·일자 경계 호출 계약을 유지합니다.
- `intake/review.py`: 최신 사전 진행 `done=i/current=항목`과 마지막 `current=None` 계약을 유지하고 실제 `facts_for`에 조건부 customer 인자만 더했습니다. 과거 사후 progress 이벤트를 중복 복구하지 않았습니다.
- cs wiki index: 최신 진행표시/택시구간 기록과 기존 후보의 날짜별 기록을 모두 보존했습니다. 원본 wiki를 덮지 않고 새 격리 기록을 최우선으로 연결했습니다.
- 날짜위험·고객시간·booking 전용 기본OFF·관리자 설정·auth는 이번 선택 시험 범위에서 재실행했습니다. Activity/Dining/Mobility 전역 active 기본값을 바꾸지 않았습니다.

## 원본 적용 차단과 정확 소유 인계
원본은 더 오래된 HEAD와 미커밋 라이팅/관리자 기능을 함께 갖고 있습니다. 깨끗한 팀 3way가 원본의 모든 변경을 보존한다는 뜻은 아닙니다. 다음 경로는 원본 수정 금지입니다.
1. `final_project_cs/app/infrastructure/llm_failover.py` — 원본 `reader_budget`, deadline, `reader_external`, API-only 정책과 후보 F3 `max_inflight`, hedge, `dispatch_claim`이 충돌합니다. **라이팅/공급자 소유자**에게 기존 local conflict7개·base/local/team/candidate blobs·정역 후보 patch를 인계합니다. 이 후보는 로컬 reader 안전 계약 통합 수락이 아니며 원본 위 적용하면 안 됩니다.
2. `final_project_cs/frontend/apps/admin/src/features/operations/connected.tsx` — 원본의 `DiagnosticsPanel`과 `source-policy.tsx`/`operationDiagnostics` 의존 경로는 최신팀+booking 후보에 자동 수용되지 않았습니다. **관리자 진단 소유자**가 해당 렌더/import hunk와 지원 API를 함께 보존해야 합니다. 원본은 변경하지 않았습니다.
3. intake/pipeline·review/assemble/hours 및 고객 웹 plan-check 관련 원본은 라이팅/고객시간 작업과 공유합니다. 최신 후보의 완성 delta는 검토용이고 원본에 통째로 역복사할 수 없습니다. 각 예전 충돌 범위·해시·분류는 `blocked-hunk-disposition.json`입니다.

원본 backend에서 안전한 독립 hunk의 **최신팀+로컬+의존 closure 보존**을 아직 입증하지 못했으므로 CAS 쓰기를 실행하지 않았습니다. 원본0경로 변경은 의도적인 HOLD이며 완료 적용으로 표현하지 않습니다. 양 원본 HEAD/index/refs/flags/sparse 설정과 선택 109경로 바이트는 시작/종료 동일입니다. 파이널스페이스 skip-worktree 16761개를 그대로 보존했습니다. 파일 부재는 원본 index/flags/sparse 조회와 구분 기록했고 임의 materialize하지 않았습니다.

## 산출물·재현
`candidate-forward.patch`, `candidate-reverse.patch`, `candidate-file-manifest.json`, `patch-roundtrip.json`, `semantic-resolutions.json`, `classification.json`, `blocked-hunk-disposition.json`, `source-final-preservation.json`, 개별 실행 log/XML/JSON이 이 기록의 scratch 산출물입니다. 정역 patch는 **최신팀 pin 전용**이며 원본용 적용 승인이 아닙니다. 새 독립 index에서 정방향 tree 일치 및 역방향 baseline tree 복구를 검증합니다.

## 공백·줄바꿈과 소유 범위 재검산
기본 `git diff --cached --check` exit2의 실제 stdout 779개를 전수 대조했습니다. 6경로 모두 과거 수락 후보 d0cc4f의 동일 CRLF 줄이며 실제 EOL 앞 space/tab은0·새 오류0입니다. 원본/시험 바이트를 바꾸지 않았고 기본 실패 로그를 그대로 보존했습니다. `cr-at-eol`만 명시한 표준 공백 검사 exit0도 별도 기록했습니다. `whitespace-classification.json`은779개 line/hash/상속 근거를 담고 있습니다. 최초 package는 `finalization-v1/`에 보존했습니다.

라이팅 공유 소유는 부모/사용자의 현재 담당 지시와 원본의 실제 reader_budget/deadline/reader_external/API-only 줄, 관리자 DiagnosticsPanel·operationDiagnostics 의존 경로, 옛 충돌의 정확7구간/2구간을 근거로 합니다. 이번 관측 중 원본 바이트 drift는 없었으므로 **현재 편집 중임을 직접 관측했다고 주장하지 않습니다**. 정확 line/hash와 artifact는 `shared-ownership-handoff.json`에 있습니다. 공유 원본에는 쓰지 않았습니다.

## 남은 수락
공유 라이팅 reader 정책·원본 관리자 진단 보존 결합, exact local 의존 closure, 허용되지 않은 HTTP4 bind시험, marker 제외29의 DB/live 범위, 실DB·실모델·실관리자 설정 저장·실화면·배포는 열려 있습니다. 기존 서비스는 그대로 유지했습니다.
