# 라우팅 전수검사 미결 재집계 · 7건 수정 인계 (2026-10-28 22:45 KST, S 작업자)

## 결론
- 10-27 전수검사 A~E 결함표 원문 재계수: **70건 · 고침 28 · 미결 42 — 기존 보고 수치와 일치.**
- 지금(이 작업 끝): 고침 38(28 + 다른 커밋으로 이미 고침 3 + 이번 7) = 54.3% · 보고서 결론으로 종결 3 · **미결 29 = 41.4%**.
  - 이미 고침(role-manager 확인): C12 `5c4750c0f`·`80863b6f3`, C13 `b6587cd48`·`9068c95f8`, 웹 #8(`error-text.ts` save_failed 영어 문장).
  - 종결(보고서 안의 결론): 웹 #9 환경, A04 · A12 의도된 설계(Codex 동의).
  - **이번 7건은 아직 role-manager 미반영(후보)** — 아래 「통합」.
- 이번 수정: E-D3(P1, 계획 읽기 · 채팅 서울 밖 장소 안내) · A17(P2, 확인 화면 전환 0행이면 후속 계산 중단) · A15(P2, 실패 확정 시 모든 판 값 삭제) · C18 · C20 · C21 · C22(P3).

## 위치
- 팀 기능 브랜치 `fix/routing-open-audit-20261028` = `87081891e`(role-manager `c52fb5c69` 위: `7fb47617a` 코드·시험, `87081891e` 보고서). CI · 배포 트리거 없음, ls-remote readback 확인.
- 보고서(그 브랜치): `final_project_cs/wiki/records/reports/2026-10-28_라우팅전수검사_미결재집계_7건수정.md` — 남은 29건 표 · 막힌 이유 포함.
- scratch: `cache/scratch/routing-open-20261028/`(repo · rb 작업 트리, ev · out 증거, 격리 PG `pgdata`). `_coord/S-routing-open-NOTICE.md`.

## 실검증
- 빠른 관문(격리, 5 shard): 기준 efc6fca47 10,723 통과 · 실패 2 → 후보 10,752 / 0d2fd47a6 위 10,755 통과 · 실패 2. 실패 2 는 모두 `test_human_review_adapters`(sparse 로 뺀 program/ HTML — 환경, 기준과 같음).
- 새 시험 RED → GREEN: C 묶음 9 RED → 14/14, E-D3 8 RED → 10/10, A17 2 RED → 3/3, A15 단위 2 RED → 2/2 · DB e2e 1 RED(2판 모델 값 11행) → GREEN.
- 격리 PG(127.0.0.1:55573, 시험 전용 복사본): 접수 e2e 38파일 등 553/554(실패 1 = 날짜 박힌 시험, f24b71080 포함 트리에서 통과) · 0d2fd47a6 위 DB 4/4.
- Codex read-only 검토(diff · 시험만 전송): blocker 0, nit 3 반영.

## 통합 — 보류 이유와 다음 순서
- R(EKS 릴리스)이 21:42 · 22:10 role-manager · develop 에 push 하고 PR #107 CI 를 돌리는 중이라 role-manager 를 움직이지 않았다(릴리스 범위 · x600 자동 배포 겹침 방지).
1. PR #107 끝난 뒤 `git ls-remote` 로 role-manager 가 `c52fb5c69` 그대로면 기능 브랜치를 role-manager 에 ff push(팀 · 개인). 움직였으면 그 위로 cherry-pick · 관문 다시.
2. x600 배포 읽기 전용 확인(board `deploy:<sha>` phase done · deploy.log 「반영 완료」 · /health). 그 뒤에야 7건을 「고침」 확정.
3. 결정 대기: A05 시한 · A06 화면 · C15 고착 회수 · C14 응답 계약 · 웹 5 늦춤 · C17 fail-open(사용자) · E-D6 DB 쓰기(사용자 승인).
4. 재현 시험으로 닫을 수 있는 것: A09 · A13 · B10 · B11.
- 남은 일: 격리 PG(postgres PID — scratch pgdata, 55573) 는 이 작업 끝에 정지한다.
