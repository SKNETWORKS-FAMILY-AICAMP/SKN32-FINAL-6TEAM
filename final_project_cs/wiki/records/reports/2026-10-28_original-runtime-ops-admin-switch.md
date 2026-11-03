---
type: report
title: 원본에서 ops 8070·관리자 3300 직접 기동과 운영자 로그인·예약 OFF 읽기 확인
status: verified
domain: travel
---

# 원본에서 ops 8070·관리자 3300 직접 기동 — 2026-10-28

## 실행 상태(원본)
| 서비스 | URL | 리스너 PID(시작) | 루트 PID | cwd | 실행 파일 |
|---|---|---|---|---|---|
| ops | http://127.0.0.1:8070 | 26564 (06:03:25) | 15464(venv 리다이렉터) | `C:\_proj\final_workspace\final_project_cs\` | cpython 3.12.15 x64(api-runtime venv) `-m app.ops_entrypoint --host 127.0.0.1 --port 8070` |
| admin | http://127.0.0.1:3300 | 32620 (06:04:10) | 6576 | `...\final_project_cs\frontend\apps\admin\` | Node 24.22.1 arm64 `next dev`, `NEXT_DIST_DIR=.next-batch` |

cwd는 프로세스 PEB에서 직접 읽어 확인했습니다. 기동은 `original_runtime_prep/start_ops_admin.ps1 -Go`를 그대로 사용했고(소유 기록 `run/owned.json`), `ACOP_DATABASE_URL`은 비공개 파일에서 프로세스 환경에만 넣었습니다. 고객 API 8042(PID 23120)·웹 3100(26720/27028)·DB 5433(6536)은 손대지 않았고 전환 뒤에도 같은 PID입니다.

## 바꾼 것
- 이전 scratch 서버 3300(PID 3888, 부모 13632)·8070(PID 6896, 부모 26236)을 PID·시작시각·명령줄 재확인 후 그 PID 트리만 정지.
- 원본 `final_project_cs/.env`(Git 무시 파일): 바이트 백업 후 `admin` 운영자 비밀번호 PBKDF2 해시 교체, 범위 7개(기존 3개 포함), `ACOP_OPS_API_KEYS` 5개 범위(action:approve, delegation:read/write, limits:read/write) 추가. 다른 21개 항목 값 불변, CRLF 유지. 비밀번호 원문은 stdin으로만 사용.
- 키 값은 원본 소스 계약을 따랐습니다: `app/presentation/security.py`의 `authenticate`는 `HMAC(secret_key, scope)` 키만 받으므로 임의 난수 키는 401이 됩니다. 그래서 로컬에서 그 함수로 만든 값을 넣었습니다(출력 없음).

## 검증(실제 응답)
- 로그인 전: 관리자 프록시·ops `/admin/api/settings/limits` 둘 다 401, 키 없는 `/admin/limits` 401.
- `/health` 200 `{"status":"ok","app":"ops"}`, `3300/settings` 200.
- 운영자 `admin` 정식 로그인 200(세션 authenticated) → 프록시 GET 200 → limits:read 키 직접 GET 200: `travel.booking.enabled` = false, source override, updated_by admin, revision 2, 두 응답 동일.
- DB 읽기 전용 트랜잭션(`transaction_read_only=on`): 값 false·actor admin·state revision 2, 이 키의 최신 감사 이벤트 seq 658(revision 1 ≤ 2, actor admin, new false). PATCH·계정 변경 0.
- 화면 렌더: 헤드리스 Edge로 `/settings` 비로그인 화면이 「운영자 로그인」 폼으로 그려짐(비밀번호 입력 없음). 로그인 후 검증은 API 응답 기반으로 따로 기록.
- 외부 모델: ops 진입점은 시작 훅·모델 호출 import가 없는 관리 전용 경로만 등록. 실행 중 비루프백 연결 0.

## 역사 정정 대조
`historical_correction_v2` 4경로는 원본에 이미 다른 형태(추가 보충 절 + 사용하지 않는 import를 지운 generator)로 반영돼 있어 보존했습니다. 다만 원본의 `gpt-6-luna_rep2.json`은 정정 전 자료라 원본 입력으로는 보고서의 165·93.0%가 재생성되지 않습니다(164·92.4%). 자료 덮어쓰기 금지에 따라 [정정 보고](2026-10-25_remaining-historical-correction.md)에 사실만 추가했습니다.

## `next dev` 부수 효과
- `frontend/apps/admin/tsconfig.json`에 `.next-batch` 타입 경로 2줄과 끝 CRLF가 써졌습니다. 현재 바이트를 백업한 뒤 추적 원본 blob(`e8fd434e1`)과 같은 바이트로 되돌렸고 `diff`는 비었습니다. 다음 `next dev` 기동 때 다시 써질 수 있습니다.
- 같은 폴더에 `AGENTS.md`(678B)·`CLAUDE.md`(11B)가 새로 생겼습니다. Next 16의 `ensureAgentRulesForDev`가 상속된 에이전트 환경변수를 감지해 만든 파일입니다. 삭제 승인 규칙에 따라 지우지 않았으며, 지울지 여부는 사용자 결정입니다.

## 롤백
`scratch/original_switch_20261028/ROLLBACK.md`. 이전 ops 8070의 `launch.py`와 cwd는 전환 전에 이미 삭제돼 동일 재기동은 불가하고 근사 재기동만 가능합니다. 증거: `scratch/original_switch_20261028/`.
