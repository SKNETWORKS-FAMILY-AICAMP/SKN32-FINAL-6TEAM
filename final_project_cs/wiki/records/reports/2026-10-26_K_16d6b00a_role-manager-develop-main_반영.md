# 묶음 K — L 커밋 16d6b00a 를 role-manager → develop → main 반영 (2026-10-26 12:23~13:00 KST)

## 결론
- 팀 저장소(SKN32-FINAL-6TEAM): role-manager · develop · main **세 단계 모두 반영 · CI 녹색**. force push 0회.
- 개인 저장소(roroblack/A-COP): role-manager · develop 반영. **main 은 미반영** — 개인 main `b0485d05` 은 2026-08-18 단독 커밋(공통 조상 없음, 옛 루트 `app/` 구조 237파일)이라 fast-forward 도 일반 병합도 정상 결과가 안 나온다(force 금지). 결정 필요(아래 남은 일).
- develop · main 은 **16d6b00a 로 고정**했다. 호텔 패치(role-manager `e43e9968`)는 develop · main 에 들어가지 않았다.

## push 전후 SHA
| 저장소 | 브랜치 | 전 | 후 | 방식 |
|---|---|---|---|---|
| 팀 | role-manager | e9953838e5f7 | **16d6b00ab240** | fast-forward (12:23:49) |
| 개인 | role-manager | e9953838e5f7 | **16d6b00ab240** | fast-forward |
| 팀 | develop | 30e9f0a08fdb | **16d6b00ab240** | fast-forward (12:33:53) |
| 개인 | develop | f7c91b319b62 | **ce6a817181cc** | fast-forward (병합 커밋 M = 16d6b00a + 개인 develop) |
| 팀 | main | 156fcc6741e5 | **a50165d110ed** | PR #103 merge 커밋(부모 156fcc67 · 16d6b00a). main 보호 규칙(PR 필수 · 필수 검사 3) 그대로 통과, 우회 없음 |
| 개인 | main | b0485d05fe18 | b0485d05fe18 (변경 없음) | 공통 조상 없음 → 보류 |

- 그 뒤 호텔 세션이 role-manager 를 `e43e9968` 로 올렸다(16d6b00a 위). develop · main 과 무관.

## CI 결과 (전부 실측 로그)
| 대상 | run | 결과 | 시험 수 |
|---|---|---|---|
| role-manager 16d6b00a CI (main) | [40263903737](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40263903737) | 성공 | 전체 12713 passed · 0 failed · 466 skipped → 12713/12713 = **100%**, 아키텍처 169/169 |
| role-manager 16d6b00a CI (develop) · (admin) | 40263911727 · 40263909062 | 성공 · 성공 | – |
| role-manager 16d6b00a CI (web) | 40263906467 | 취소(호텔 세션 dispatch 와 동시성) — 같은 SHA 의 develop push CI (web) 40264698392 성공 | – |
| develop push CI (develop) | [40264698483](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40264698483) | 성공 | 10221 passed · 0 failed · 133 skipped = **100%** |
| PR #103 CI (main) | [40264721967](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40264721967) | 성공 | 12738 passed · 0 failed = **100%** |
| main push CI (main) a50165d1 | [40265761183](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40265761183) | 성공 | 12738 passed · 0 failed · 466 skipped = **100%**, 아키텍처 169/169, ruff · Docker 성공 |
| main CD (AWS) a50165d1 | 40266644824 | 13:00 진행 중(main CI 성공 뒤 자동 시작) | – |

- 알려진 격리 DB 실패 `tests/e2e/test_chat_edit_web.py::test_a_range_shift_that_runs_into_a_kept_stop_is_refused_as_a_whole` 는 CI 에서 실패 목록에 없다(0 failed) → CI 깨끗한 DB 에서는 통과. 로컬 격리 DB 실패는 환경 원인으로 남는다.
- 개인 저장소 워크플로는 꺼져 있다(앞 묶음 기록). 개인 develop M 은 app · tests 가 16d6b00a 와 바이트 동일이라 팀 CI 결과가 그대로 적용된다.

## 개인 develop 병합 (계획 `S/integ-L-20261026/develop-plan/PLAN_KO.md` 대로)
- worktree `cache/scratch/integ-K-20261026/pdev`, `merge --no-ff personal/develop` (16d6b00a 기준). 충돌 16파일.
- 코드 · 시험 9파일과 wiki 색인 2 · `trip-chat-context.md` 는 role-manager 판(개인 쪽 충돌 조각은 비었거나 같은 보고서를 가리키는 옛 요약 줄). 같은 이름 기록 · handoff 4파일은 role-manager 본문 뒤에 「개인 develop(f7c91b31) 판 — 병합 보존」 절로 개인 본문 보존.
- 확인: `git diff 16d6b00a M -- final_project_cs/app final_project_cs/tests` = 빈 diff, 충돌 표시 0, `def admission_dates` 1개. M 의 16d6b00a 대비 차이는 wiki 4파일 +107줄뿐.

## x600 배포 확인
- 16d6b00a push 가 자동 배포를 일으켰다: 공지판 `deploy:16d6b00ab2-1792985273` 12:27 시작 → 12:29 `done`. 이어서 호텔 `deploy:e43e996817` 12:41 → 12:44 `done`. `/health` 200 `{"status":"ok"}`(12:33 · 12:59), 웹 `/` 200.
- ★컨테이너 상태 · api 최근 ERROR 수는 **확인하지 못했다**: 이 PC 의 `~/.ssh/id_ed25519_x600`(주석 `hermes-guguroute-x600-readonly`)으로 `root@` · `eon@192.168.0.8` 모두 publickey 거부. 앞 L 세션이 쓴 접속 경로를 찾지 못했다. 공개 health · 배포 공지만으로 판단.

## 다른 세션 관련 관측
- 호텔 패치 role-manager `e43e9968` CI (main) [40265004266](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40265004266): **12722 passed · 5 failed** — `test_intake_stay_lines.py` ×2 · `test_intake_candidate_kinds.py` · `test_intake_lodging_recommendation.py` · `test_intake_lodging_retry.py`(모두 호텔 줄 채우기). 16d6b00a 는 0 failed 이므로 호텔 패치에서 새로 생긴 실패이고 x600 에 이미 배포됐다. K 는 고치지 않았다(호텔 세션 몫) — `_coord/K-push-NOTICE.md` 에 알림.

## 남은 일
1. 개인 main 처리 결정: (a) `--allow-unrelated-histories` 일반 병합(옛 8월 루트 파일 237개가 main 에 함께 남음), (b) 사용자 명시 허가 하의 main 교체(force — 지금은 금지), (c) 그대로 둠.
2. CD (AWS) 40266644824 결과 확인.
3. 호텔 e43e9968 CI 5건 실패 — 호텔 세션이 원인 확인 · 수정(x600 반영 상태).
4. x600 읽기 전용 접속 경로 정리(키가 서버 authorized_keys 에 없음).
