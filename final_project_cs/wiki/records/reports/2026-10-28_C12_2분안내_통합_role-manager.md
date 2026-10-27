# 2026-10-28 C12 제안 고르기 저장 실패 수정 + 계획 읽기·짜기 「2분」 안내 — role-manager 누적 통합 후보

- 작성: 2026-10-28 KST, Claude(하위 작업). 사용자 요청: 두 후보를 함께 반영하되 **push · 배포 안 함**.
- 기준 재확인(작업 시작 시): 팀 `role-manager` = 개인(origin) `role-manager` = `ffb5fb1b5059c960bd634eca56894b7aa0a4cbd5` (팀은 `tools/safe_git.py fetch team` · `ls-remote`, 개인은 git 자격 도우미 실행 거부로 `gh api repos/roroblack/A-COP/git/ref/heads/role-manager` 로 읽음). 두 후보 모두 이 커밋 바로 위라 fast-forward 후보다.
- 격리: worktree `cache/scratch/integ-c12-wait-20261028`(브랜치 `integ/c12-wait-20261028`, 원본 작업 폴더 · 다른 worktree · 공유 DB · x600 · 원격 쓰기 0). 실 DB 는 scratch 클러스터 사본 `127.0.0.1:55491/acop_p1iso`만(P1 가드 차단 0건). 모델 호출 0.

## 1. 쌓은 순서

| # | 원본 커밋 | 통합 커밋 | 내용 |
|---|---|---|---|
| 1 | `7f670774f` | `5c4750c0f` | 제안 고르기(`trip_api._choose`) 저장 실패(OperationalError)가 500 이던 것 → 제안 행을 새 연결로 다시 읽어 그대로일 때만 503 `save_failed` |
| 2 | `129741ec3` | `80863b6f3` | C12 리뷰 — 소유 확인 전 실패는 원래 예외(남의 여행에 503 내던 것), 잠그기 전 실패의 503 본문 `proposal_status: open` |
| 3 | `72c6a718f` | `02461e7a1` | 계획 읽기 · 계획 짜기 화면 예상 안내 「1분쯤 걸려요」 → 「2분쯤 걸릴 수 있어요」(한 · 영). 시간 제한 · 속도 불변 |

cherry-pick 3/3 자동 적용, 충돌 0. 두 후보가 함께 고친 파일은 `final_project_cs/wiki/external/rest-endpoints/web-intakes.md` 하나(다른 단락) — 양쪽 추가 줄이 모두 있음을 diff 로 확인했다. 나머지 파일은 각 원본 커밋의 blob 과 같다. 충돌 표시 줄 0.

## 2. 관문

| 검사 | 결과 |
|---|---|
| 빠른 관문(architecture · contract · unit · security · eval, `not live and not db and not slow`, 네트워크 · DB 차단 실행기) | 10,549 통과 · 0 실패 · 173 건너뜀 (C12 단독 후보와 같은 수) |
| 실 PostgreSQL 이웃(새 e2e 3 · 리뷰 탐침 8 · test_web_api · watch_failures · watch_relaxed · desk_gate · chat_lodging_web · web_auth_guest_transfer · 단위 choose 3파일) | 115/115 + `booking_full` 11/11 → 고유 122/122 = 100% (탐침은 후보 밖 파일이라 실행 뒤 지움) |
| 웹 vitest 전체 | 1,219/1,219 = 100% |
| 웹 tsc | 통과 |
| 브라우저(모방 서버, Chromium) — 2분 안내 시험 + 이웃(plan-check-screen · progress · reading-hold) | 41/41 = 100% |
| ruff(바뀐 .py) · `git diff --check` | 통과 |

화면 확인: 계획 읽기 「계획을 확인하고 있어요 — 사진 한 장은 2분쯤 걸릴 수 있어요」 · “A photo can take about two minutes”, 계획 짜기 「…2분쯤 걸릴 수 있어요」 · “It can take about two minutes”. 깨진 줄바꿈 · 겹침 없음. 캡처는 git 밖 `cache/scratch/integ-c12-wait-ev/screens/{reading,planning}-{ko,en}.png`. ★모방 서버 화면이다 — 실제 서버 시간을 잰 것이 아니다.

## 3. 남은 것

- push 안 함. push 할 때는 직전에 두 원격 `role-manager` 가 아직 `ffb5fb1b` 인지 다시 보고, 같으면 팀 · 개인 모두 fast-forward. 앞서 가 있으면 새 tip 위에 다시 쌓고 관문을 다시 돈다. role-manager push 는 x600 자동 배포를 부른다.
- develop · main 미변경. C12 리뷰 §4 의 P3 3건(`_stay_recheck` 500 등)은 그대로.
