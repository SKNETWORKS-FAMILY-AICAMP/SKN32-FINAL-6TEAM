# role-eval-ui → develop 통합 사전 검증

- 수행: Codex, 2026-10-01 (KST). 사용자 승인: 두 브랜치 병합·푸시, 로컬 `b2673e2` 포함, 백엔드 포트 `8042` 고정.
- 목표: 공유 이력을 보존해 사용자 웹 작업을 develop에 반영하고 두 브랜치를 같은 통합 커밋으로 동기화한다. main은 대상이 아니다.
- PR: [#29](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/pull/29). 최종 병합 SHA·원격 CI·전체 검증 결과는 PR 본문에서 확인한다.

## 통합 범위와 보존

| 구분 | 시작 SHA |
|---|---|
| 원격 role-eval-ui | `e58cefca42aee96cfb6e92988aabbf1b13613c24` |
| 사용자 승인 로컬 role-eval-ui | `b2673e2b9979add5be3be9e68800c8711c5a39f5` |
| 원격 develop | `233dc7f73530255b46d611d5050658a2d8f117f2` |
| 로컬 develop | `37a450e7588bd309e95e4d5ce4d7a7854e4e5271` |
| 변경하지 않는 main | `abde7c3eaad3b46ef3b0fd000e15be8f3d1aebf2` |

별도 worktree에서 merge commit `93bfb5429966ebcc46b865afcd9d24fca56778fc`를 만들고 role-eval-ui에 일반 푸시했다. 텍스트 충돌은 없었다. 자동 병합된 `.env.example`은 live 모드와 8041을 조합했으므로, 명시적인 팀 결정 및 README·클라이언트 기본값에 맞춰 `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8042`로 유지했다. 웹 리뷰 수정·1분 폴링·채팅 오류 안내와 일정 카드 HTML 목업을 포함한다.

원본 체크아웃의 미커밋 dev-console README와 `mockups/README.md`, `mockups/management-scenario.html`은 커밋하지 않는다. 기존 파일 SHA-256을 별도로 기록해 동기화 후 보존을 대조한다. 강제 푸시·공유 이력 재작성·main 변경은 수행하지 않는다.

## 완료한 검증

Python 3.12.10, Node.js 22.22.3. 실제 설정·외부 API 키 없이 mock LLM과 별도 PostgreSQL 16/pgvector 시험 DB를 사용한다. 브라우저 live 시험은 대역 서버를 대상으로 하며 실제 서비스 검증이 아니다.

| 검증 | 결과 |
|---|---|
| `git diff --check` (develop 대비 통합 변경) | 통과 |
| `python -m ruff check .` (0.16.8) | 통과 |
| 웹 `npm run check` | lint·typecheck·build 통과, Vitest 109/109 = 100% |
| 웹 `npm run test:e2e`, Chrome | 54/54 실행 통과 = 100%, 설정별 3건 제외 |
| 웹 `npm run test:live`, Chrome | 44/44 = 100% |
| PR #29 CI(develop) | 구조·계약·단위 1,785 통과, 73 skipped, 188 deselected; 보안 23/23 = 100% |
| PR #29 CI(web) | check·e2e·live 통과 |

근거: [CI(develop) 36798059503](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/36798059503), [CI(web) 36798059521](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/36798059521). 이 결과는 통합 코드 `93bfb54` 기준이다. 이 문서 추가 후 PR 관문과 최종 원격 HEAD를 다시 확인한다.

## 기존 문제와 환경 구분

- 기존 develop `233dc7f`의 [CI(main) 36791115562](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/36791115562)는 `tests/e2e/test_trip_intake_api.py::test_unread_lines_are_pointed_at_by_the_model_and_places_are_looked_up` 1건 실패다. 2,318 passed, 182 skipped, 195 deselected. 이번 통합은 백엔드 코드·테스트·스크립트를 develop에서 변경하지 않는다.
- 첫 로컬 브라우저 시도는 Playwright의 chromium-1243 실행 파일이 없어 시작 단계에서 실패했다. README에 명시된 설치 Chrome 채널로 실행해 위 54·44건을 확인했다.
- 로컬 전체 pytest는 시스템 `TMPDIR` 접근 권한으로 임시 폴더 fixture 오류가 발생했다. 미완료 실행을 중단하고 TEMP·TMP·TMPDIR를 작업용 폴더로 지정해 재검증한다. 최종 전체 결과는 PR 본문에 남기며 이 사전 기록에서 통과로 간주하지 않는다.
- `scripts.verify_dod`는 자체 설명대로 옛 v8 29항목 검사다. 현재 여행 v11 26항목과 혼합해 완료율을 계산하지 않는다.
- 서버의 dining `price_compare`는 기존 웹 모델·화면에서 표시하지 않는다. 제품 기능 추가로 범위를 넓히지 않는다. 외부 dining 데이터 적재·core DB 재구축·유료 API 호출·실서버 브라우저 시험은 이번 작업에서 실행하지 않는다.

## 재현

웹 앱에서 `npm ci`, demo 환경으로 `npm run check`, `PLAYWRIGHT_CHANNEL=chrome`으로 `npm run test:e2e`, `npm run test:live`를 실행한다. 백엔드는 CI(develop)의 가짜 설정값·mock LLM·별도 시험 DB·Asia/Seoul 세션 시간대를 적용하고 마이그레이션 및 `scripts.register_prompts` 뒤 검사한다. Windows에서는 TEMP·TMP·TMPDIR가 모두 쓰기 가능한 시험 경로인지 먼저 확인한다.

참조: 저장소 README, `final_project_cs/RULE.md`, 웹 README, `.github/workflows/ci-develop.yml`, `.github/workflows/ci-web.yml`.
