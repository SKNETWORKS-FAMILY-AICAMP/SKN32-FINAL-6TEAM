# 예약 전용 OFF 설정 8경로 원본 적용 · 최신 원본 실행 검증 — 2026-10-25

## 결론
- **원본 `C:/_proj/final_workspace`에 8경로를 적용했습니다(8/8 = 100%, postimage SHA256 전부 일치).** 적용 직전 현재 바이트가 preimage와 8/8 일치했고, 다른 세션이 해당 경로를 편집한 흔적(mtime·내용)은 없었습니다. 충돌 보류 경로 0.
- 적용 뒤 원본 기준 검증: booking 설정·reader 단위시험 6/6, action gate 탐침 18/18, 관련 회귀 합집합 374건 중 369 통과(실패 5건은 적용 전 사본과 **동일한 기존 실패**), 관리자 lint·typegen·tsc·vitest·build 전부 exit 0.
- 소유자 서버(3300 PID3888, 8070 PID6896)는 건드리지 않았습니다. 별도 loopback 포트(OS 배정)의 fresh serving copy에서 **설정 GET(직접, 범위 한정 키)·독립 읽기 전용 DB 대조는 OFF(false/override/revision 2/actor admin/감사 1건)로 일치**했습니다.
- **정식 로그인 + 프록시 GET은 미완료**입니다. 이 세션에 운영자 비밀번호가 전달되지 않았고 vault도 비어 있었습니다(위조·우회 없음). 서버 기동·정리는 끝났고, 비밀번호만 비공개 stdin으로 주면 한 번에 끝나는 명령을 아래에 적었습니다.
- 기능(`travel.booking.enabled`) 저장값은 OFF입니다. 이는 예약 기능의 값이며 관리자 앱·API·DB는 모두 정상 가동 중입니다.

## 1. drift·편집 중 여부 (적용 전)
| 확인 | 결과 |
|---|---|
| 8경로 현재 SHA256 = preimage | 8/8 = 100% (3회: 조사 시, 백업 직전, 적용 직전) |
| mtime = 패키지 manifest mtime | 8/8 (신규 3파일은 부재 유지) |
| 최근 3시간 내 `app/tests/admin src/wiki` 변경 | 제품 코드 0건, 다른 세션의 wiki 문서 14건만(I06 final-serving 등) — 8경로와 무관 |
| git | HEAD efeb873a8d065fbd28fe8e92dcc42e5cfb3de3e3, index.lock 없음, skip-worktree 등 비-H 플래그 0 |
| 보류 경로 | 없음 |

참고: 다른 세션의 I06 인계(`wiki/handoff/2026-10-25_final-serving-i06-8b1e6c3b.md`)가 말하는 `intake/pipeline.py` 한 hunk는 이번 8경로와 겹치지 않습니다.

## 2. 백업·적용
- 백업(적용 직전 21:19:40): `scratch/booking-apply-20261025/backup-full/` — 기존 5파일 바이트 + 신규 3파일 부재 장부 + `.git/index`(SHA256 bf7b92b1…, 적용 뒤에도 동일) + HEAD·config·packed-refs·loose refs 2개 + `ls-files -v` 17,190행(비-H 0)·`ls-files -s`·worktree 목록. 복원 매니페스트 `RESTORE_MANIFEST.json`. 쓰기 독점 잠금은 아니며 drift 검출용 CAS입니다(Windows 파일 잠금 미사용).
- 적용: MinGit 2.56.0 `git -c core.autocrlf=false apply`(patch SHA256 `5ba52b9a107db3b7bdbfd9b7300cde2215a402fddb85dd462987ab37a7a9bb57` 일치 확인) — exit 0. 추가 111행·삭제 1행(`connected.tsx` 렌더 1행 교체).
- postimage SHA256 8/8 일치(앞 16자리): booking_actions 87ec9d68… · settings_hook 5580b12b… · booking_handoff/__init__ 778c95f4… · web_guard f244580b… · booking-mode.test.tsx c2331970… · booking-mode.tsx 22cc349d… · connected.tsx ff6d4831… · test_booking_master_switch.py 0c7a23ad…
- 변경 파일 수: **수정 5 + 신규 3 = 8**. index·HEAD·ref 변경 0(적용 전후 동일), 스테이징·커밋·push 0.
- `git diff --check`: 저장소 설정(autocrlf=true) 기준 **exit 0·진단 0**. autocrlf=false 비교에서는 CRLF 파일(`web_guard.py`, `connected.tsx`)의 추가 행 끝 CR이 trailing whitespace로 잡히지만, 같은 파일의 기존 행이 모두 CRLF인 상속 줄끝이며 `core.whitespace=cr-at-eol`로는 신규 오류 0(exit 1 = 차이만). 신규 3파일·LF 3파일은 공백 오류 0. 줄끝을 정규화하지 않았습니다. 증거 `diff-check-report.txt`.

## 3. 적용 후 실행 검증 (원본 바이트 = 복사본, 원본 node_modules·.next 오염 0)
| 항목 | 결과 |
|---|---|
| booking 설정·reader (`test_booking_master_switch.py`) | 6/6 = 100% |
| action gate 탐침(scratch 전용, 저장소에 넣지 않음) — Cancel/Change/Revert × 미설정·false·1·"true"·reader 예외 → `booking_disabled` 거절 + 잠금 조회 0회, 명시 true에서만 통과 | 18/18 = 100% |
| 관련 회귀 합집합(booking switch·google switch·booking subject·plugin read 경계·evidence·계약 4파일·아키텍처 3파일, 12개 파일) | 374건 중 369 통과 = 98.7% (원본 직접 실행) |
| 같은 합집합 A/B(적용 전 사본 368건 ↔ 적용 후 사본 374건) | 상태 변화 0, 실패 5건 동일 → **기존 실패**: `test_team_tool_discipline[activity/disaster_impact.py]`, `test_api_key_file` 3건(git 서브프로세스 WinError5·`ACOP_SERPAPI_API_KEY` 템플릿 누락), `test_basement_is_domain_free`(a2a `order_id`). 8경로와 무관, 실패를 분모에서 빼지 않음 |
| 관리자 lint / typegen / tsc / build / tsc(빌드 후) | 모두 exit 0 (Node 24.22.1, 원본 lock으로 `npm ci` 격리 설치) |
| 관리자 vitest(프로젝트 기본 설정) | 22/22 (파일 1개) |
| 관리자 vitest(`.tsx` 포함 scratch 설정) | 24/24 (파일 2개, `booking-mode.test.tsx` 2/2) |

**발견·한계**: 프로젝트 `vitest.config.ts`가 `src/**/*.test.ts`만 포함해 신규 `booking-mode.test.tsx`는 기본 `npm test`에서 실행되지 않습니다. 제품 설정은 바꾸지 않았고 scratch 설정으로만 확인했습니다. 후속으로 include에 `.tsx`를 넣을지 소유자 결정이 필요합니다. 또한 booking_handoff Team의 OFF 응답과 DB 연결 apply 경로는 단위 대역으로만 확인했고 실DB·실모델 확인은 아닙니다.

## 4. fresh serving copy 읽기 전용 확인 (소유자 서버 미접촉)
- 사본: 원본 `app·config·tests·prompts·knowledge·scripts·admin·sample` 3,485파일 바이트 일치(불일치 0), 기동 직전 원본과 1,481파일 재대조 차이 0. 포트는 코드에 없고 `BOOKING_VERIFY_OPS_PORT`/`BOOKING_VERIFY_ADMIN_PORT`(OS 배정 loopback)로만 전달.
- 최종 실행(`servctl-final-nologin.json`): ops 56795 / admin 56796, 두 포트 ready, 인증 없는 프록시 GET `/admin/api/settings/limits` **401**(기대값), `/settings` 200, 직접 GET(설정된 `limits:read` 범위 키) 2회 동일: **`travel.booking.enabled` = false · source override · updated_by admin · revision 2**. 별도 읽기 전용 DB 연결: runtime_limits (false, admin), 상태 revision 2, 해당 키·값·행위자 감사 이벤트 1건(이벤트 revision 1 ≤ 상태 2; 다른 설정이 전역 revision을 올림). 직접 = DB 일치 true. 수락 전후 `runtime_limit*` 3개 표 지문(행 수·md5) 동일 = 설정 쓰기 0.
- **실패 보존**: 첫 시도는 모든 DB 세션을 `default_transaction_read_only=on`으로 강제했더니 `/admin/limits` GET이 **500**이었습니다(`serving-acceptance-RO-session-500-preserved.json`). 원인은 제품 `web_limits_api._revision()`이 GET마다 `INSERT INTO runtime_limit_state … ON CONFLICT DO NOTHING`을 실행하기 때문입니다(행이 이미 있어 데이터 변화는 없지만 읽기 전용 트랜잭션은 거부). 소스를 고치거나 GET을 건너뛰지 않고, 사본 launcher에 **SQL 허용 목록 가드**(그 정확한 문장만 허용, 그 외 INSERT/UPDATE/DELETE 등은 `PermissionError`)와 위 표 지문 검사를 두고 재실행했습니다. 허용된 문장 실행 기록 `serving-sql-guard*.jsonl`, 거부 0. 이 방식은 소유자 서버가 이미 하는 동작과 같은 범위이며, "DB 세션 전체가 read-only"라는 표현은 쓰지 않습니다.
- 정리: 기동한 ops·admin 프로세스(launcher + 실제 listener, 명령줄이 `booking-apply-20261025` 확인된 PID만)를 종료했고, 종료 후 두 포트 LISTEN 0. 소유자 listener 3300→PID3888, 8070→PID6896 변동 없음. handoff할 살아 있는 프로세스 없음.

## 5. 남은 조건
1. **정식 로그인 → 프록시 GET → OFF 일치** (비밀번호 필요). 부모가 비공개 stdin으로만 전달:
   `printf '{"operatorId":"admin","password":"<비공개>"}\n' | C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/date_risk_env_312/Scripts/python.exe C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/booking-apply-20261025/servctl.py final-login`
   결과는 `serving-acceptance-final-login.json`의 `stage=FORMAL_LOGIN_PROXY_DIRECT_DB_DONE`, `agreement_proxy_direct_db=true`. (PATCH·계정 변경 없음, 서버는 스스로 정리)
2. 소유자 서버(3300/8070)는 아직 옛 스냅샷입니다. 최신 원본 반영 교체는 소유 세션(admin-testmode-20261025)의 인계·승인이 있어야 하며 이번에 하지 않았습니다.
3. `vitest.config.ts` `.tsx` 포함 여부, 기존 실패 5건은 이번 범위 밖입니다.
4. 커밋·push·배포 0. 원본 변경은 워킹트리 8경로뿐입니다.

## 증거 경로
`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/booking-apply-20261025/` — `backup-full/`, `apply-verify.json`, `diff-check-report.txt`, `tests-run/`(JUnit·로그·vitest JSON·A/B 비교), `serving-copy-manifest.json`, `serving-copy-vs-original.json`, `servctl-final-nologin.json`, `serving-acceptance-*.json`, `serving-sql-guard*.jsonl`.
