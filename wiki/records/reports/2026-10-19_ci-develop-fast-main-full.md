# 2026-10-19 develop 은 빠른 검사만, 전체 검사는 main 만

사용자 지시(19:00 무렵): 「지금 develop 테스트 너무 많은 거 같아 불필요한 거 줄여. 풀 테스트는 main 만 진행하게 시켜」.

## 결론

GitHub 검사 설정 4개를 고친 새 판을 격리 폴더에 만들었다. **아직 커밋 · 푸시 전**이다(commit 세션으로 넘긴다). develop 에 들어가면 develop push 한 번에 도는 검사가 약 25분 · 러너 7~8대에서 약 3분 · 러너 2대(+웹 · 관리자가 바뀐 때 각 1대)로 준다.

## 바꾸기 전(team/develop `f10bd172` 기준, 19:00 확인)

| 검사 | develop push 때 | 걸린 시간(최근 실행) |
|---|---|---|
| CI (main) — ruff · 전체 pytest 5천여 개 · Docker 빌드 | 돈다 | 약 8분(실행 39230346442) |
| CI (web) — check + 브라우저 시험 4묶음 | 웹이 바뀐 때 | 약 15분, 러너 5대(실행 39215589722) |
| CI (admin) — check + 브라우저 시험 | 관리자가 바뀐 때 | 약 2분(실행 39060655379) |
| CI (develop) — ruff · architecture · contract · unit · security | **손으로만**(10-13 결정) | — |

## 바꾼 뒤

| 검사 | develop push · develop PR | main push · main PR · 손으로 돌림 |
|---|---|---|
| CI (develop) 빠른 검사 | **돈다**(맨 위 문서만 바뀐 push 는 건너뜀) | 손으로만 |
| CI (main) 전체 검사 | 안 돈다 | 돈다(필수 검사 이름 그대로) |
| CI (web) | `check` 만 | `check` + 브라우저 4묶음 |
| CI (admin) | `check` + 시연 HTML 대조 | + 브라우저 시험(e2e · unconfigured) |

- 웹 · 관리자의 「전체인가」 판정은 한 식(`main` 가지 · `main` 으로 오는 PR · 손으로 돌림)으로 둔다 — `FULL` 환경값.
- main 의 필수 검사(「ruff (F·E9)」「전체 시험 (live 제외)」「Docker 빌드」)는 `gh api …/branches/main/protection` 으로 확인했고 이름을 바꾸지 않았다. develop 은 보호 설정이 없다(404).
- 배포 스크립트(`final_project_cs/deploy/`)의 `.sh` · `.py` 에서 CI 결과를 읽는 곳을 찾았고 안 나왔다(검색어: check-runs · actions/runs · conclusion · workflow · ci-main). 놓칠 수 있는 것: x600 서버 쪽에만 있는 스크립트.
- 시험 코드가 워크플로 파일을 읽는 곳: 없음(develop 트리의 `.py` · `tests/` 에서 `ci-*.yml` · `.github/workflows` 검색 — 주석 2곳만).

## 확인

- 빠른 검사가 지금 develop 에서 통과하나: CI (develop) 를 develop `f10bd172` 에서 손으로 돌림(실행 39234803195, 19:04~19:07) — ruff 통과, 시험 8131 통과 · 133 건너뜀, 보안 101 통과. 약 3분.
- 새 판 4개 YAML 읽기 통과(PyYAML), 줄 끝 CRLF 한 번(원본과 같음).
- **안 한 것**: actionlint(이 PC 에 없음) · 새 판을 실제 GitHub 에서 돌려 보기(커밋 뒤 첫 develop push 에서 확인한다 — 웹 `live` 가 「건너뜀」, 묶음 결과 `web` 이 성공인지).

## 파일

- 격리 폴더: [`.tmp/ci-develop-slim-20261019/`](../../../.tmp/ci-develop-slim-20261019/) — `base/`(develop `f10bd172` 원본) · `new/`(새 판) · 만든 스크립트 `make_new.py` · `make_docs.py`.
- 새 판: `.github/workflows/ci-develop.yml` · `ci-main.yml` · `ci-web.yml` · `ci-admin.yml`, `final_project_cs/frontend/apps/web/README.md`(CI 절 한 줄) · `final_project_cs/frontend/apps/admin/DEVELOPMENT.md`(한 줄).
- 로컬 규칙: 루트 `CLAUDE.md` · `AGENTS.md` 「커밋·푸시 대상」에 같은 한 줄(백업 [`_backup/2026-10-19_1907_ci-develop-slim/`](../../../_backup/2026-10-19_1907_ci-develop-slim/)).

## 남은 일

1. commit 세션이 develop 최신 위에 얹어 커밋 · 푸시(role-manager 양쪽, develop 은 사용자가 요청할 때).
2. 푸시 뒤 첫 develop 실행에서 새 동작 확인.
3. 대가: develop 에서 통합 · e2e · 브라우저 시험 실패가 main 으로 갈 때까지 안 보인다. 큰 변경은 CI (main) 을 그 가지에서 손으로 돌린다.
