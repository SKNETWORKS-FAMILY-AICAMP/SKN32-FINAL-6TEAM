# 2026-10-28 원본 직접 통합 — 날짜 위험·고객 운영시간·최신팀 backend/admin/auth 후보 (A 단계)

## 결론
- **원본 `C:/_proj/final_workspace` 작업 트리에 47경로 적용**(후보 114경로 중 46 + 새 이식 시험 1). 커밋·push·배포·DB·서비스·설치 변경 0. HEAD/index 바이트 적용 전후 동일(`efeb873a…`).
- **고객 운영시간 P1 미반영 동작 4곳을 원본 구조로 이식** — RED 12/12 → GREEN 12/12(같은 시험 바이트, 원본에서 실행).
- **날짜 위험과 "최신팀 기준" 코드 동기화는 HOLD.** 원본 HEAD는 팀 develop보다 1,065커밋 뒤(app 322파일 +50k줄, app 133·web src 125·admin src 19파일 부재). 날짜 위험은 원본에 없는 최신팀 `intake/risks.py`·위험 패널 위에 만든 기능이라 이식하면 사실상 원본을 원격에 맞추는 일이 되고, 원본 규칙(AGENTS.md 1~10행: pull/checkout/덮어쓰기·역복사 금지)이 금지한다. Codex 자문(read-only)도 같은 결론.
- 백엔드 회귀(원본, non-live·non-DB 범위 511파일): **7,633 통과 / 7,672 (99.49%)**, 실패 24·오류 14·건너뜀 1 — **38건 모두 통합 전 바이트(4개 변경 모듈 PRE 오버레이)와 동일 nodeid·동일 상태**, 신규 회귀 0. DB 대기로 시간초과 32파일(시나리오 DB 등), DB 범위 미실행 e2e 81·integration 72파일, live 10파일 제외.
- 관리자(원본 폴더, 기존 lock 기반 npm ci 설치본 재사용, Node 24.22.1): lint·typegen·tsc·vitest·build·build 뒤 tsc **6/6 rc0**, vitest **24/24**(gateway 22 + booking-mode 2 — vitest include 확장으로 원본의 booking-mode.test.tsx가 처음 실행됨). lock/package/vitest 설정 해시 전후 비교 기록.

## 기준·입력
- 정식 safe_git(원본 `tools/safe_git.py`, Python 3.12 + 승인 MinGit x64 `0x8664`) `fetch team develop` rc0 → **최신 team/develop = `36ba4c2fc2938bca68b0c775c01a63809f7c8ed0`**(이전 6c34589b 아님). 원본 HEAD `efeb873a…`(role-manager, 10-13)는 6c34589b·36ba4c2f 모두의 조상.
- 후보 scratch 폴더는 10-27 정리 때 `_archive_20261027/latest_backend_admin_auth`로 축약 보관(dirty.patch + 미추적 53 + bundle). **6c34589b + dirty.patch + 미추적 53 + 시험 부산물 3건 원복 = tree `f7b680f7…` 정확 재구성**(소유 bare repo `recon.git`, 원본 objects는 alternates로 읽기만).

## 114경로 분류(3way: 원본 작업트리 / 기준 6c34589b / 후보)
| 분류 | 경로 | 처리 |
|---|---:|---|
| 적용 | 46 | 깨끗한 3way 7(관리자 vitest include·README 2, codex 호출 파일 충돌 정정 3 = codex_percall·codex_du_report·결과 md, 정정 보충 문단 2 = 10-07 조사 문서·보고서) · 고객시간 P1 원본구조 이식 4 · 정정 계약 문단 1 · 후보 새 파일 34(기록/인계 30, F3 경계 시험 3, codex 충돌 시험 1) |
| 이미 동일(보존) | 10 | launcher 2·test_local_launcher·local-app-bundle·booking_actions·booking_handoff·booking switch 시험·관리자 3300 보고 2·model.test(EOL) |
| 의미상 이미 반영(보존) | 22 | 고객시간(pipeline 장소변경 시 hours 삭제 inline, review hours_state, web 편집/표시), F3(settings·llm_failover), booking OFF 관리자, 원본 고유 시험판 |
| HOLD | 36 | 날짜 위험(risks·risk-panel·관련 웹/백엔드 시험), 최신팀 전용 모듈/시험(reopen·booking instance·features_api·e2e 스위치·후보 F3 test_llm_failover +210줄 등), 공유 소유 충돌(llm_failover 문서·connected.tsx Diagnostics·root README), 공유 index/log 5 |

경로별 해시·사유: `FINAL_MANIFEST.json`.

## 이식한 고객시간 P1 동작
1. `watch/dawn_check._closed_places` — 고객이 알려 준 시간(`source=customer_hours`)으로 낸 휴무는 tenant 공용 대체후보 제외집합에 넣지 않음(공식 휴무 공유는 유지).
2. `intake/hours._merge_state` — 요식 원장의 그 시각 판정이 있으면 시계 칸 없이도 `dining_ledger` 공식 출처.
3. `itinerary/itinerary_checks._place_violations` — 원장 판정이 있으면 고객 요일표로 휴무 위반을 만들지 않음.
4. `intake/stream.Feed` — 실시간·완료·재연결 item 이벤트에 `hours_state`·`customer_hours` 실음(검토 결과와 웹 디코더는 원본에 이미 있었음).
시험 `final_project_cs/tests/unit/travel/test_customer_hours_original_port.py`(후보 시험 본문 그대로, 최신팀 전용 `_fixed_neighbours` 대역만 raising=False). 후보 고객시간 시험 52건을 원본에 대면: 적용 전 28/52 → 적용 후 37/52, 남은 15는 모두 최신팀 전용 심볼/도우미(`reopen`·`_item_of`·`_kept_ends`·`test_web_taxi_pricing_v1` 등) 부재. 후보 RED25 원본 nodeid 목록 파일은 보관본에 없어 정확 25 identity는 재현 불가 — 위 52건 직접 측정으로 대체.

## 실행 증거(모두 이 폴더 `ev/`)
- 가드: `runner.py` = 기존 승인 `date_risk_pytest_runner.py` 방식(더미 설정·DB URL 127.0.0.1:1·xdist 일꾼 DB 복사 차단) + **이 시험 프로세스가 bind한 loopback 포트만 connect 허용**. 비교: `runner_baseline.py`(4 변경 모듈을 백업 PRE 바이트로 로드).
- `scope_post`(511파일 1차) → basetemp 상위 폴더 누락이라는 **하네스 결함으로 tmp_path 시험 244 오류** 확인, 보존 후 `drive.py` 수정·실패 66파일 `rerun_post`/`rerun_baseline` 동시 재실행(1032/19/2 동일). 1차 시간초과 7파일은 900초로 `slow_post`/`slow_baseline`(76/5/12 동일). 합산 `regression_combined.json`.
- 기존 실패 38의 내용: 원본 고유 미추적 파일 때문에 생기는 구조 시험(composer 사본·docs/·_backup 칸 규칙·retired assets 48), 템플릿 키 누락(SERPAPI), Windows git 실행 PermissionError(WinError5) 3, transformers 미설치 1, DB 연결 시간초과(시험 내부 실DB) 다수, mobility 골든 4, schedule_query 1, bus shared cache 1.
- 원본 부작용: 회귀 전후 `git status -uall` 차이 = 이 통합의 새 시험 3 + 다른 세션 보고서 1건뿐.
- codex 충돌 시험: 적용 후 4/4 OK, 적용 전 codex_percall로 2 실패(RED).
- 관리자: `ev/admin/{rc.txt,vitest.xml,*.log,lock-*.txt}`.

## 백업·복원
- CAS 장부: `backup_20261028T043337`(1차 43), `backup_20261028T045757`(2차 4), `backup_*`(3차 wiki 보고·index append). 각 장부 = 경로별 사전/사후 sha256·mtime·`ls-files -s/-v`·`.git/index` 바이트 사본·HEAD·status.
- 복원(역순, 먼저 dry-run): `python restore.py <backup_dir>` → 확인 후 `python restore.py <backup_dir> --do`. 지금 바이트가 우리 사후 해시와 같을 때만 되돌리며(다른 세션이 그 뒤 고친 파일은 SKIP), 새로 만든 파일은 그 조건에서만 지운다.

## 남은 조건
- 날짜 위험·최신팀 기능: 원본 HEAD를 팀 develop으로 올릴지(원본 규칙 개정 또는 사용자 명시 승인 필요) 결정 전에는 원본에 넣을 수 없음.
- 공유 소유: llm_failover 후보 7구간·문서, 관리자 connected.tsx Diagnostics, root README 충돌, wiki index/log 전체 병합.
- DB 범위 시험(e2e 81·integration 72·DB 시간초과 32파일), 실DB·실모델·실관리자 저장/readback, 실화면 수락은 이 단계 범위 밖.
