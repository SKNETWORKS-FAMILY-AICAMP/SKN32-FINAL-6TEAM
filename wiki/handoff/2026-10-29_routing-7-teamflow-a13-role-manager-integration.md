# 라우팅 7건 · TeamFlow 574/714 · A13 role-manager 통합 · x600 배포 확인 인계 (2026-10-29 00:40 KST, S2)

## 결론
- 팀 · 개인 `role-manager` `c52fb5c69` → **`c714eecdb`**(빨리 감기, ls-remote readback 일치). 기능 브랜치 `fix/routing-open-audit-20261028` 도 같은 tip. develop `3463b30c6` · main `20c296e77` 은 손대지 않음.
- x600 배포 **확인 완료**: board `deploy:c714eecdbc-1793201416` phase done(00:31) · deploy.log 「반영 완료 c714eecdbc (이전 c52fb5c691)」 · api `ACOP_DEPLOYMENT_VERSION=c714eecdbc` · api/web/admin/worker healthy · `tripilot.devroro.click/health` 200. (23:1x 에는 SSH 시간 초과 · 523 이었고 00:3x 에 돌아옴.)
- 이로써 전수검사 7건(E-D3 · A17 · A15 · C18 · C20 · C21 · C22) + **A13(이번 수정)** 「고침」 확정(배포 기준, 고객 화면 실측은 안 함). 미결 29 → **28**.

## 들어간 커밋 (c52fb5c69 위)
| 커밋 | 내용 |
|---|---|
| `7fb47617a` · `87081891e` | 전수검사 미결 7건 + 보고서(앞 S 작업자). 이번에 diff 독립 재검토 — blocker 0 |
| `d6c3a67c7` | TeamFlow 후보 `010f9deeb` cherry-pick — ST4F-574 장소 갱신이 공통 공공데이터 키 · ST4F-714 project.yaml 팀 블록 중복 칸. 충돌 0 |
| `5d7054edb` | 574 후속: `getattr(…"public_data_key", None)` 숨은 대체 제거(시험 대역 때문이었음) |
| `cb284d301` | A13: 모델이 고른 해가 날짜 인용에 그대로 적혀 있지 않으면 값은 두고 확인 표시 + 안내. Codex read-only 검토 blocker(`\d{4}` 오탐: 「1230 출발」 · 예약번호 · 「1027년」) 반영 |
| `c714eecdb` | 보고서 `final_project_cs/wiki/records/reports/2026-10-29_라우팅7건_TeamFlow_A13_role-manager_통합.md` |
- ST4F-710 `e6e754f27` 는 이미 `e6e02f4c7` 로 role-manager 에 있었음 — 따로 넣지 않음. TeamFlow 이슈 상태는 바꾸지 않았다(574 · 714 를 「완료」로 옮기는 일은 TeamFlow 담당 몫).

## 검증
- 빠른 관문(격리 5 shard, `cb284d301`): 10,766 통과 · 실패 2(`test_human_review_adapters`, sparse 로 뺀 program/ — 기준과 같음).
- 격리 PG 55573: 59파일 555/555(1회) · 554/555(실패 1 = 실행이 자정을 넘은 날짜 기대값) — `5d7054edb`. A13 뒤 접수 DB 8파일 110/110.
- 새 시험: A13 9/9(RED 1 확인), 574 · 714 · 7건 대상 53/53. ruff · diff --check 통과.

## 주의 (다른 작업자)
- **terminal 셸 환경 변수가 작업자 사이에 섞인다**: `TMPDIR` 가 다른 작업자 scratch(`eks-verify-20261028/tmp`)로, DB 스크립트의 `ACOP_*` · `TEST_DATABASE_URL` 이 남아 있었다 → tiktoken 캐시 못 찾음 6건 · CORS 1건 거짓 실패. 관문 전 `TIKTOKEN_CACHE_DIR=C:/Users/kcxsz/AppData/Local/Temp/data-gym-cache`, `ACOP_*` 해제를 직접 할 것.
- 긴 DB 묶음(45분+)은 foreground 로 돌리지 말 것 — 시간 초과 뒤에도 프로세스가 살아 같은 DB 에 두 벌이 겹쳐 돌았다(둘 다 통과했지만 증거가 섞임).

## 정리
- 격리 PG 55573 정지(`pg_ctl stop`). scratch `routing-open-20261028/rb` worktree 제거(0 dirty, HEAD 원격). `repo` · `ev` · `out` · `pgdata` · 스크립트는 보존. C: 여유 363.47GB.
- role-manager push 소유 해제 — V 의 CD 진단 후보 `72ba5ff48` 등 다음 push 가능(`_coord/S-routing-open-NOTICE.md`).

## 남은 일
1. 재현 시험으로 닫을 것: A09(뒤 묶음 정정이 앞 묶음 항목을 못 지움 — 1,800자 넘는 글) · B10 · B11.
2. 결정 대기: A05 시한 · A06 화면 · C15 고착 회수 · C14 응답 계약 · 웹 5 늦춤 · C17 fail-open(사용자) · E-D6 DB 쓰기(사용자 승인).
3. 선택: E-D3 서울 밖 안내 · A13 확인 표시를 x600 고객 화면에서 실측(고객 쓰기 수반 — 시험 계정으로).
