# 전체 과거 날짜 — normal confirm HTTP 증명

## role-manager 독립 이식 (이 브랜치의 현재 결과)

- 기준은 양쪽 원격 role-manager `6410f754b3fe1ff29b0916bab43b130b82a595a8`입니다. develop 또는 다른 브랜치를 merge하지 않고 검증된 hotfix 11경로 patch만 `git apply --3way`로 적용했습니다.
- review 충돌은 이 브랜치의 기존 store·risk·dining 경로를 보존하고 날짜 가드 hunk만 반영했습니다. wiki 충돌도 원래 내용을 유지하고 hotfix 링크만 추가했습니다.
- 이 기준에는 develop의 `dining_review` 모듈과 `test_intake_registration_gate.py`가 없습니다. 제품에 develop 기능을 들여오지 않았고 두 신규 시험의 존재하지 않는 dining mock만 제거했습니다. HTTP 8개 및 모든 날짜 assertion은 유지했습니다.
- 원래 35개 명령은 누락 파일로 exit 4(0 collected), 이후 미이식 dining import는 collection error/1 failure였습니다. 원본 로그를 보존했고 제품 실패나 성공으로 바꾸지 않았습니다.
- 이 브랜치에 실제 있는 네 시험 파일의 최종 실행은 **21/21 = 100%**, 실패·오류·skip 0입니다. `role-confirm-green.xml`/`.log`, 실행기 `run_isolated.py`, 환경 `ALLPAST_SOURCE_ROOT=.../role-delivery/final_project_cs`입니다. 원래 35/35 develop 결과와 합산하지 않습니다.
- 선택 파일: `test_all_past_confirm_api.py`, `test_all_past_dates.py`, `test_intake_deferred_check.py`, `test_social_dining_constraints.py`. 실행 옵션 `-q --tb=short --junitxml=.../role-confirm-green.xml`.
- 전체 architecture/contract/unit/security 선택 관문을 `-p pytest_asyncio.plugin -m "not live and not db and not slow" -q --tb=short`로 실행하여 exit 0을 확인했습니다. JUnit은 **9417건 = 9244통과 + 173 skipped**, 실패/오류 0; 별도 677 deselected, 268.42초입니다 (`role-full-final.xml`/`.log`). full-layer marker로 기본 제외되는 시험까지 전부 실행했다는 뜻은 아닙니다. 로컬 결과를 원격 CI 성공으로 부르지 않습니다.
- 최초 전체 실행은 asyncio plugin 미등록을 targeted 재현으로 확인해 중단했고 로그 `role-full.log`/`role-harness-check.log`를 보존했습니다. 새 전체 실행에서 plugin을 명시했으며 제품 fallback이나 시험 assertion을 완화하지 않았습니다.
- 추적 경로 18,965개 모두 접근 가능(누락/읽기불가 0), 제품 3개+시험 2개의 SHA256는 고정 checkpoint와 최종 실행 뒤 동일합니다 (`role-tracked-access-audit.json`, `role-frozen-source.json`). Ruff 5파일과 staged diff whitespace 검사도 exit 0입니다.
- 양쪽 원격은 같은 기준·후보를 사용합니다. 실제 commit/push와 `git ls-remote`+GitHub commit API readback 증거는 profile scratch `ROLE_DELIVERY_RESULT.json`에 별도로 남깁니다. 이 문서의 선행 develop 기록은 현재 role-manager 결과로 재사용하지 않습니다.
- 인증 계정은 GitHub API `roroblack`/`58134693`로 확인했습니다. 작성자 noreply는 commit 한정으로 지정합니다. 운영 설정 변경·수동 배포·실고객 DB·LLM/provider 호출은 하지 않았습니다.

## 아래는 이식 원본의 develop 증명 이력

## 결론

추가 제품 수정 0개입니다. `registration.require_review`는 cached review를 load만 하지만 정상 confirm은 결국 실제 `_create_trip`의 신규 등록 날짜 가드를 거칩니다. stale `ready: true`가 이 가드를 우회하지 못했습니다.

- base: `beb726b9918904dce068a1f5b16c2cbcc053e677`.
- 기존 후보 8파일 SHA256는 독립 snapshot에서 모두 일치함을 확인한 뒤 문서 링크만 보완했습니다. 제품 3파일과 기존 feature 시험은 변경하지 않았습니다.
- 실제 FastAPI TestClient POST `/v1/web/trip-intakes/{intake_id}/confirm`, 실제 draft → SQL owner 확인 → assemble → registration.require_review → `_create_trip`를 실행했습니다. DB는 SQL을 기록하고 모든 영속 쓰기를 거절하는 메모리 UOW입니다. 외부 DB 검증이라고 주장하지 않습니다.
- RED: snapshot의 최종 날짜 가드만 일시 비활성화하면 동일 POST가 다음 경계 418에 도달하여 `418 != 422`로 1/1 실패했습니다. 가드를 원상복구한 뒤 GREEN입니다. 새 제품 결함이 발견됐다는 뜻이 아니라 시험의 감지력 확인입니다.
- GREEN: 새 HTTP 8개 + 기존 날짜/미룬검사/등록게이트/식사조건 회귀 합계 **35/35 = 100%**, 실패·오류·skip 0. 이후 최종 import 정리 후 재실행 결과는 scratch `confirm-final.xml`을 따릅니다.
- 전부 과거: typed 422 `itinerary_infeasible`, violation `all_dates_in_past`, 날짜 확인 안내, 신규 등록 경계 0회, 영속 변경 0, cached payload 불변.
- 어제+오늘/어제+내일/오늘/미래: 각각 다음 정책 경계까지 진행합니다. 시험은 쓰기 전 418 sentinel로 멈추며 전체 등록 성공을 주장하지 않습니다.
- 이미 confirmed는 200 `created:false`; 다른 소유자는 실제 draft의 첫 SQL 뒤 404, review 접근 0; 무인증은 실제 auth 401, draft 접근 0.
- 정상 성공 경로의 인증은 명시적인 FastAPI dependency override입니다. 쿠키·현재 사용자·CSRF 값을 위조하지 않았습니다. 쿠키 세션/CSRF 전체 및 비교 DB 두 개는 이 controlled 증명의 범위가 아닙니다. 기존 confirmed/reopen/frozen 정책 제품 코드 변경은 없습니다.
- review 공개 안내와 confirmed/reopened 예외는 기존 `test_all_past_dates.py` 회귀로 함께 확인했습니다. 실제 GET 전체 DB lifecycle 증명과 구분합니다.

## 전체 관문과 전달

부모의 `latest-complete-gate.xml`을 직접 파싱했습니다: 수집 9545, skipped 173, 실행 **9372/9372 = 100%**, failures/errors 0. 이는 같은 제품 소스의 architecture/contract/unit/security 전체 관문이며 추가 HTTP 파일은 별도 35개 회귀에서 검증했습니다. 첫 old-base 보안87개와 섞지 않습니다.

전체 실행 로그·JUnit·source pre/post·patch·정확 cwd/명령/nodeid는 profile scratch `allpast-hotfix-20261025-2005/confirm-proof-unique/{CONFIRM_PROOF.json,PUSH_READY_CANDIDATE.json,PRE_POST_SHA256.json,complete-candidate.patch}`에 있습니다. parent가 원래 latest tree를 검사하는 동안 해당 tree를 편집하지 않았습니다.

외부 DB·모델 metadata·알림 dispatch·고객 shared DB·서비스 호출은 0입니다. 인증·작성자 검증 및 네 remote의 단일 owner push는 부모 담당이며 이 작업에서는 commit/push 하지 않았습니다. 원격 반영 0/4 = 0%입니다.
