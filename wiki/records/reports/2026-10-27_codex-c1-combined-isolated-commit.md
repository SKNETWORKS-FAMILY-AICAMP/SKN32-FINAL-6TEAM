---
type: report
title: codex_percall uuid + C1 v2 고객 알림 e2e — 양쪽 role-manager 93c7ba8e 위 격리 clone 누적 시험 · 커밋 2개(push 전)
status: draft
domain: travel
---

# codex_percall uuid + C1 v2 통합 커밋 준비 (2026-10-27)

[codex_percall uuid 격리 반영](2026-10-27_codex-percall-uuid-isolated-apply.md)과 [C1 고객 알림 e2e 격리 검증](2026-10-27_c1-customer-notice-e2e-isolated-validation.md)의 두 patch 를 최신 role-manager 위 깨끗한 격리 clone 에 합쳐 누적 시험 · 보안 검토 후 **실제 커밋 2개**를 만들었다. push 는 하지 않았다(부모 몫). 원본 작업트리 · 공유 DB(5433) · 서비스 · 원격 쓰기 0.

## 결론

| 항목 | 값 |
|---|---|
| 기준(parent) | `93c7ba8ecf053caedfe54ad7199dd0b9321e4f0b` — 팀 SKN role-manager 12:50 · 13:00(+GitHub API) 같음, 개인 A-COP role-manager 12:50 같음. 두 원본 보고서의 pin 과 같아 재분석 불필요 |
| 커밋 1 | `45318ab420a11330b6f7597e3811b0afdffc23a4` (parent `93c7ba8e`) — fix(eval_kit): codex_percall uuid, 2파일 +55 −1 |
| 커밋 2 · tip | `ffb5fb1b5059c960bd634eca56894b7aa0a4cbd5` (parent `45318ab4`) — test(e2e): C1 v2 시험 + `final_project_cs/wiki/external/customer-notice-controls.md`, 2파일 +41 |
| tip tree | `be917b80cbb8ac1a146ddd215eac65029b3806d5` = 두 patch 를 함께 stage 해 시험한 트리 |
| 결과 blob | `codex_percall.py` `1d3d53c6` · `test_codex_percall.py` `95620dc6` · `test_customer_notice_admin_switch.py` `f28a0854` — 원본 보고서 값과 같다 |
| 입력 patch | codex `4faa633e…070191`, C1 v2 `59b1c462…d38aa` — 두 보고서 sha256 과 같다. 둘이 겹치는 파일 0, `apply --check` 개별 · 동시 모두 exit 0 |

## 시험 (최종 트리, 같은 파일 해시)

| 실행 | 결과 |
|---|---|
| codex RED (pin 코드 + 새 시험) | 1 failed, exit 1 (의도한 실패) |
| codex GREEN × 5 | 5/5 exit 0 = 100% |
| eval_kit 회귀 | 15/15 = 100% |
| C1 (새 격리 PG 16.15 클러스터 `127.0.0.1:55472`, migrate → register_prompts → seed_travel) × 2 | 각 1/1 = 100%, `runtime_limit_events` 0 → 0(감사 줄 잔여 0) |
| C1 이웃 묶음(+ test_web_guard · google_price · guardian 스위치 · integration delivery switch) | 46/46 = 100% |
| CI develop 빠른 관문(`tests/architecture contract unit security`, `-m "not live and not db and not slow"`, `-n 8`) 1차 | 10,494 passed · 173 skipped · **3 failed** — 셋 다 Python subprocess 의 WindowsApps git `WinError 5`(환경, 제품 아님) |
| 같은 3건 파일, 검증된 scratch MinGit 2.56 를 PATH 앞에 | 84/84 = 100% |
| 빠른 관문 전체 재실행(MinGit PATH) | **10,497 passed · 173 skipped · 0 failed** (junit 10,670) exit 0 |
| ruff | 변경 py 3파일 통과 |
| `git diff --check 93c7ba8e HEAD` | exit 0 |

가드 plugin(`cmb_guard.py`)이 psycopg 는 55472 만, socket 은 loopback(5433 제외)만 허용 — 모든 실행 차단 시도 0. 실제 Codex CLI · 모델 · 네트워크 호출 0. 이 관문은 CI develop 기본 관문이며 전체 suite(db · slow · booking_full 등)·CI main 전체 시험은 돌리지 않았다.

## 보안 검토

- 변경 4파일에 비밀값 패턴(api key · secret · token · password · private key · `sk-` · `ghp_` · `AKIA`) 0건.
- codex: `uuid4` 는 OS 난수, 이름은 work 폴더 임시 파일에만 쓰임. 셸 호출 없음(목록 인자 `subprocess.run`, `-s read-only` 유지). 서명 · 반환 변화 없음.
- C1: 런타임 코드 변경 0. 시험이 권한 거절 403 · 형식 422 · 판 충돌 409 를 확인하고, 덧붙이기 전용 감사 줄은 `_audit_cleanup` 으로 정리한다(잔여 0 실측).
- 격리 DB 환경 값은 CI 와 같은 형태의 가짜 값이다. `.env` 미사용.
- 보안 관문 `tests/security` · 계약 `test_api_key_file` 포함 빠른 관문 통과(위 표).

## push 에 필요한 것 (부모)

- 저장소: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/combined-codex-c1-20261027/repo`, 브랜치 `integrate-codex-c1`(tip `ffb5fb1b`). `objects/info/alternates` 로 원본 `.git/objects` 를 읽기만 한다(원본에 쓰기 없음). remote `team`·`origin` 등록됨.
- 직전 확인: `git ls-remote team refs/heads/role-manager` · `git ls-remote origin refs/heads/role-manager` 가 둘 다 `93c7ba8e` 이면 fast-forward:
  `git push team ffb5fb1b5059c960bd634eca56894b7aa0a4cbd5:refs/heads/role-manager` · `git push origin ffb5fb1b5059c960bd634eca56894b7aa0a4cbd5:refs/heads/role-manager`. 끝이 움직였으면 새 끝에 두 커밋을 `cherry-pick -x` 하고 관문을 다시 돈다. 강제 push 금지.
- 13:00 에 개인 origin `ls-remote` 가 자격 도우미(WindowsApps `gh.exe` Permission denied)로 실패했다(12:50 은 성공). 부모 환경에서 다시 확인해야 한다. 전역 설정은 고치지 않았다.
- role-manager push 는 x600 자동 배포를 부른다. 이번 변경은 eval 도구 · 시험 · 문서뿐이라 런타임 영향은 없다.
- 예비: bundle `combined-codex-c1-20261027/codex-c1-integrate.bundle`(sha256 `a80995a4…a19bae`, prerequisite `93c7ba8e`, `git bundle verify` 통과), format-patch 2개는 아래 evidence 에도 복사.

## 원본 보존

원본 `C:/_proj/final_workspace` HEAD `efeb873a`(변화 없음). `codex_percall.py` sha256 `a71bf1ba…`·미추적 시험 `8ee738a1…` 전후 같다. `git status --porcelain` 줄 수 12:50 1,165 → 13:00 1,158 — 이 작업은 원본에 쓰지 않았으므로(이 보고서 · evidence · 인계 전) 다른 세션의 변경이다. fetch 는 scratch clone 에만 했다.

## 증거

[evidence 폴더](../evidence/2026-10-27_codex-c1-combined-isolated/) — format-patch 2개(`0001` sha256 `2383e37f…`, `0002` `56666662…`), 가드 · 실행 스크립트, 실행별 exit · 행 수 · 해시 · 요약(빠른 관문 junit 은 크기 때문에 scratch 에만), codex RED/GREEN/eval_kit 로그. scratch 원본 `combined-codex-c1-20261027/`(24시간 미사용 시 정리될 수 있음).

## 남은 일

1. 부모: 양쪽 role-manager push 후 각 해시 보고(개인 origin 자격 확인 포함).
2. CI main 전체 시험(DB · slow 포함)은 push 뒤 develop 단계에서 확인. 이번에는 돌리지 않았다.
3. C1 문서를 `final_project_cs/wiki/external/index.md` 에 연결할지는 앞 보고서대로 사용자 결정으로 남김.
