# 2026-10-22 빠른 시험 단계(CI develop)를 DB 없이 · 느린 시험 제외로 바꿈

결론: develop 빠른 단계의 시험 작업이 DB 대기와 느린 파일 때문에 길었다. DB 가 필요한 12개 파일과 파일당 몇 초씩 걸리는 6개 파일에 표시(`db` · `slow`)를 달아 빠른 단계에서 건너뛰게 했고, PostgreSQL 기동 · 스키마 · 프롬프트 단계를 뺐다. 건너뛴 시험은 main 전체 관문이 계속 돈다.

## 한 일 (커밋 `800f676b`, role-manager 팀 SKN · 개인 A-COP 양쪽)
- `.github/workflows/ci-develop.yml` : test 작업에서 Postgres 서비스 · DB 시간대 확인 · 스키마 · 프롬프트 등록 단계 제거, 시험 한 줄 `-m "not live and not db and not slow"`, timeout 20 → 10분.
- `final_project_cs/pytest.ini` : `db` · `slow` 표시 등록.
- `final_project_cs/tests/conftest.py` : `DB_TEST_FILES`(12개) · `SLOW_TEST_FILES`(6개)와 표시를 붙이는 훅.
- `final_project_cs/tests/architecture/test_db_marked_files_exist.py` : 목록에 없어진 파일이 남지 않게 하는 시험.
- 측정 · 패치는 세션 작업 폴더에서 격리 사본으로 했다(원본 작업 폴더 미수정).

## 근거 (확인 구분)
- **격리 사본(HEAD 추출, DB 없음, 데이터 파일 없음)**: 처음 전체 실행 72분 — 원인은 DB 필요 시험 29개 항목이 연결 대기 130초씩. DB 시험 제외 후 188초, 느린 6개 파일 제외 후 112초(한 프로세스). 병렬 `-n 4` 는 115초로 이득 없어 뺐다. 항목 6,146 → 5,847.
- **이 PC(commit 세션, CI 와 같은 조건)**: 새 시험 1/1 통과, 빠른 단계 9,084 통과 · 139 건너뜀 · 677 제외, 실패 9건은 로컬 추출본 환경 탓(변경 전에도 같음). `-m "db or slow"` 건너뛰는 항목 210개.
- **GitHub CI(develop) 손으로 돌림(role-manager, 실행 39739261105)**: 성공. test 작업 2분 25초, 실행 전체 2분 30초. 직전 develop 실행들은 test 3분 0초 ~ 3분 43초(시험 수가 날마다 조금 다르고 한 번 측정이라 「대략」).
- 내 사본의 「새 실패 0」은 DB 없는 사본에서 보안 시험 2개(`test_pii_redaction_runtime.py` · `test_query_scope.py`)가 분할 전에도 오류라 기존 실패로 세어 놓친 것이었다 — commit 세션이 이 2개를 `db` 목록에 더했다(10 → 12).

## 알아 둘 것
- role-manager 는 CI 가 자동으로 돌지 않는다. 이 변경이 실제 효과를 내는 곳은 develop(develop 에 있는 워크플로 파일을 쓴다)이며, **develop 에는 2026-10-22 17:26 KST 에 반영했다(`5d52dfbf`, 팀 SKN · 개인 A-COP 양쪽).**
- develop 푸시는 사용자가 commit 세션에서 직접 「푸시해」라고 확인해 진행했다(2026-10-22). 순서: develop 최신의 GitHub 검사 확인(팀 develop `ca99669c` 의 CI(develop) 성공) → 그 위에 얹은 판의 빠른 단계를 CI 와 같은 조건으로 로컬 시험(9,124 통과 · 139 건너뜀 · 677 제외, 실패 9건은 로컬 추출본 환경 탓으로 role-manager 시험과 같은 목록) → 푸시 직전 재 fetch(develop 그대로) → 팀 develop 에 푸시, 개인 develop 은 `ae6f4236` 에서 빨리 감기(강제 푸시 없음).
- 별개: 이 변경과 무관한 `disaster_impact.py` 의 ports import 규칙 위반은 사본(HEAD 추출)에서만 실패했고 실제 CI 에서는 통과했다 — 원인 미확인.
- 처음 보신 「9,296」의 출처는 확인하지 못했다(commit 세션 로컬 집계 9,084 통과 + 139 + 677 와 가까움, 확정 아님).

## develop 반영 결과 (2026-10-22 17:26 KST)
- **커밋** `5d52dfbf` (팀 develop 부모 `ca99669c`, 4파일 +70/−31 — role-manager 의 `800f676b` 와 같은 줄 수). 팀 SKN · 개인 A-COP 양쪽 develop 이 같은 해시.
- **develop 푸시로 돈 CI(develop)**: 실행 #39747767025, 성공. ruff 26초(08:26:41→08:27:07 UTC) · test 작업 3분 0초(08:26:41→08:29:41 UTC) · 실행 전체 3분 3초. 이 푸시로는 CI(develop) 실행 하나만 확인했다(web · admin 검사는 이 푸시 해시로는 못 봤다).
- **비교**: 직전 develop 실행의 test 작업은 3분 0초 ~ 3분 43초였다. 이번 3분 0초는 그 범위의 아래쪽 끝이라 **이 한 번으로는 단축 폭이 뚜렷하지 않다**(role-manager 수동 실행은 2분 25초). 러너 속도 흔들림이 있어 더 쌓인 실행으로 봐야 하며, 확정하지 않는다.

## 남은 일
- develop CI 시간은 더 쌓인 실행에서 다시 비교한다(이번 한 번의 3분 0초는 흔들림 범위 안일 수 있다).
- 이 기록 파일은 commit 세션이 role-manager 양쪽에 커밋했다(2026-10-22). 기록의 해시 · 시간은 commit 세션이 원격 · CI 기록과 대조했다.
