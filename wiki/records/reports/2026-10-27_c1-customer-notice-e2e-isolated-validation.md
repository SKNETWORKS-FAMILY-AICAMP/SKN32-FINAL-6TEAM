# 2026-10-27 bundle 후보 C1(고객 외부 알림 관리 콘솔 e2e 시험 · 문서) — 최신 role-manager 격리 DB 검증

사용자 지시(2026-10-27): [bundle 11 재분류](2026-10-27_finalspace-bundle-11-reclassification.md)의 C1 이 최신 role-manager 에서 유효하고 안전한지 격리 DB 로 검증하고, 적용할 수 있는 patch 를 돌려준다. 운영 DB 쓰기 · push 금지.

## 결론

- **C1 은 최신 role-manager 에서 유효하다.** 원 patch(`cand2`)를 그대로 적용한 시험이 격리 DB 에서 통과했다(1/1 = 100%).
- **안전 결함 1건을 찾아 고쳤다.** 원 시험은 덧붙이기 전용 감사 표 `runtime_limit_events` 에 시험 tenant 행 2개를 남긴다(tenant 행은 지워지지만 감사 줄은 트리거 때문에 남는다). 공유 DB 에서 돌리면 시험할 때마다 고아 감사 줄이 쌓인다. pin 의 `tests/e2e/test_web_guard.py` 에 이미 있는 `_audit_cleanup` 정리 fixture 를 그대로 쓰도록 고쳤다(단언 변경 0).
- **적용 patch: v2** — [c1_v2_tests_doc.patch](../evidence/2026-10-27_c1-customer-notice-e2e-isolated/c1_v2_tests_doc.patch), sha256 `59b1c462…d38aa`, 2파일 +41, 런타임 코드 변경 0. 문서 부분은 원 patch 와 바이트가 같다.
- 원본 작업 폴더 · 공유 DB(5433) · 원격: 쓰기 0. push 0.

## 기준

| 항목 | 값 |
|---|---|
| 팀 role-manager (SKN) | `93c7ba8ecf053caedfe54ad7199dd0b9321e4f0b` (2026-10-27 다시 fetch, exit 0) |
| 개인 role-manager (A-COP origin) | `93c7ba8e…` 같음. 앞 보고서 pin 대비 0/0 — 바뀜 없음 |
| 원 patch | `cand2_988a_tests_doc.patch` sha256 `ac7962f3…dfe36e` (앞 보고서 값과 같음) |
| 원본 작업 폴더 | HEAD `efeb873a`, 대상 두 경로 모두 없음(추적 · 미추적 · 충돌 없음). status 줄 수는 1,155(앞 보고서) → 1,160(지금) — 다른 세션의 변경이며 이번 작업은 원본에 이 보고서 · evidence 폴더 · 인계 한 줄만 더했다 |
| 격리 | Hermes scratch 의 bare 저장소(원본 objects 를 alternates 로 읽기만) + pin 고정 worktree(`core.autocrlf=false`). 원본 refs · index · 작업 폴더는 건드리지 않음 |
| 격리 DB | scratch 에 **새 PostgreSQL 16.15 클러스터**를 `initdb` 로 만들어 `127.0.0.1:55471` 에서만 띄움(공유 서버 5433 과 별도 프로세스 · 별도 data 폴더). CI 와 같은 순서로 `migrate` → `register_prompts` → `seed_travel`. 끝난 뒤 중지 |
| 실행 환경 | Python 3.12.15 scratch venv, CI 와 같은 형태의 가짜 설정(`ACOP_LLM_PROVIDER=mock` 등). `.env` 없음 |
| 가드 | pytest plugin `c1_guard.py`: psycopg 연결은 `127.0.0.1:55471` 만 허용, 5433 · 바깥 socket 차단. 세션 시작마다 자체 시험(5433 · 바깥 주소 차단, 55471 열림) 통과. 모든 실행에서 차단 시도 0 |

## 실행 결과

| 실행 | 대상 | 결과 | 감사 줄 잔여(이 시험 이름) |
|---|---|---|---|
| run1 | 원 patch 그대로 | 1/1 통과 = 100% (8.1초) | **2행 남음**(tenant `trip_api_85bdd…`) |
| v2_a · v2_b | v2 | 각 1/1 통과 = 100% (5.1초 · 5.0초) | 0 |
| mut_ignore_db | v2 + 제품 변이(`customer_notice_delivery.enabled` 가 DB 값을 무시) | **1 실패**(26행 `assert False is True`) — 시험이 실제 저장 반영을 잡는다. 변이는 실행 뒤 되돌림(`git diff` 0) | 0 |
| neighbors | v2 + `test_web_guard.py` · `test_google_price_admin_switch.py` · `test_guardian_admin_switch.py` · `tests/integration/test_customer_notice_delivery_switch.py` 한 세션 | 46/46 통과 = 100% (49.8초) — fixture 가져오기 · 순서 간섭 없음 | 0 |

- 실행 전후 시험 · 제품 파일 sha256 이 같았다(모든 실행 `hash_stable=yes`).
- neighbors 실행에서 `runtime_limit_events` 가 13행 늘었는데, C1 이 아니라 함께 돌린 **pin 의 기존 이웃 시험들**이 남긴 것이다(어느 파일이 몇 행인지는 나누어 세지 않았다). C1 이름의 감사 줄은 run1 의 2행뿐임을 tenant 별로 셌다. 기존 시험의 정리 누락은 이번 범위가 아니라 고치지 않았다(아래 남은 일).
- 정적 검사: `ruff check` 통과, `git diff --check <pin> <tree>` 통과, 새 index 로 pin 에 `apply --cached` 한 결과 트리 `1350f636…` 가 만든 트리와 같다.

## 문서(`wiki/external/customer-notice-controls.md`) 사실 대조

| 문서 내용 | pin 에서 확인 |
|---|---|
| 「운영 설정 · 보관 → 웹 이용 · 서비스 설정」 | 관리 앱 메뉴 `운영 설정 · 보관`(AdminApp.tsx) · 탭 `웹 이용 · 서비스 설정`(operations/connected.tsx) |
| `/admin/limits` · `/admin/api/settings/limits` · `limits:read/write` | 시험이 실제 HTTP 로 확인(403 · 422 · 409 · 200). 두 번째 경로는 `admin-screen-api.md` · `test_admin_json_gateway.py` 에 있음 |
| 기본 꺼짐 · JSON boolean | `config/guardrails.yaml` `notice_per_customer_enabled: false`, 문자열 `"true"` 는 422 |
| 재시작 없이 반영 | `scripts/run_outbox_worker.py` 가 발송 판정 때 `customer_notice_delivery.enabled(tenant)` 로 DB 를 읽음 · 시험이 저장 직후 판정 변화를 확인 |
| 감사 이력(운영자 · 사유 · 이전/새 값 · 판) | `runtime_limit_events` 열과 `/admin/limits/events` 응답으로 확인 |

문서는 wiki 어느 목차에도 링크되지 않은 쪽이다. 목차(`final_project_cs/wiki/external/index.md` 「관계」)에 연결할지는 앞 보고서처럼 사용자가 정할 일로 남겼고, patch 에 넣지 않았다.

## 적용 방법 (role-manager 통합 담당)

```
git -c core.autocrlf=false apply --check wiki/records/evidence/2026-10-27_c1-customer-notice-e2e-isolated/c1_v2_tests_doc.patch
git -c core.autocrlf=false apply        wiki/records/evidence/2026-10-27_c1-customer-notice-e2e-isolated/c1_v2_tests_doc.patch
```

pin `93c7ba8e` 기준이다. 원본 작업 폴더(HEAD `efeb873a`, pin 보다 1,062 뒤)에 바로 적용하는 것은 검증하지 않았다 — 통합 사본에서 적용한다. 원 patch(`cand2`)는 v2 로 대체하며 둘을 함께 적용하지 않는다.

## 한계 · 남은 일

- 검증 범위: 새 시험 1개 + 이웃 4파일(46건). 전체 suite · CI · 실서버 · 실제 디스코드/텔레그램 발송은 하지 않았다.
- 격리 DB 는 빈 클러스터에 마이그레이션 · 데모 시드만 넣은 것이다. 개발 DB(5433)의 실제 자료 상태에서의 결과는 아니다.
- pin 의 `tests/e2e` 에서 감사 줄 정리(`_audit_cleanup`)를 쓰는 곳은 `test_web_guard.py` 하나뿐이다. 이웃 시험들이 `runtime_limit_events` 에 감사 줄을 남긴 것은 별도 후보다(이번에는 고치지 않음, 파일별 수와 다른 스위치 시험은 세지 않았다).
- 커밋 · push: 0.

## 증거

[evidence 폴더](../evidence/2026-10-27_c1-customer-notice-e2e-isolated/) — v2 patch, 가드 plugin, 실행별 `out.txt` · `junit.xml`(run1 은 경로 오류로 junit 없음, out.txt 만) · 표 행 수 전후 · 종료 코드.
