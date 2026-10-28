# ST4F-711 백엔드 관문 복구·검증·양쪽 반영 — 2026-10-29

검증한 웹 수정 3파일을 팀·개인 `role-manager`에 fast-forward로 반영했습니다. 소스 커밋은 `217da9ad07d16374b2401924418b7115f81769ab`, 부모는 `c714eecdbcc6d6ec1865876321a90887a3e02dfd`입니다. 두 원격의 실제 조회 결과가 같은 소스 해시입니다(**2/2 = 100%**). develop/main 푸시·수동 배포·원본 코드 덮어쓰기·자료 삭제는 없습니다. 운영 반영 성공 및 LB-09 역사적 원인 확정은 별도 미확인입니다.

## 무엇을 고쳤는가

접수 경로 이동이 완료되지 않은 상태에서 전송이 실패하면, 등록 화면의 로컬 `sending` 상태가 남아 진행 화면에서 빠져나오지 못했습니다. `IntakeStarting`이 실패·뒤로 가기·시작 정보 없음에서 부모에게 복귀를 알리고 `RegistrationScreen`이 상태를 해제합니다. `useCallback`으로 참조를 유지합니다. 자동 재전송은 추가하지 않으며, 이미 접수된 성공 응답은 접수 화면으로 이동합니다. API·인증·DB·모델 계약 변경은 없습니다.

## 실제 검증 결과

| 검증 | 결과 | 근거 |
|---|---|---|
| 필수 백엔드 명령 | **3/3 = 100%**, 모두 exit 0 | `ready-gates.json` |
| DoD 항목 | **26/26 = 100%** | `dod-evidence/summary.json` |
| DoD 하위 실제 pytest | **216/216 = 100%**, 실패·오류·건너뜀 0 | `dod-evidence/pytest.xml` |
| 계약 pytest | **367/367 = 100%**, 실패·오류·건너뜀 0 | `contract-ready.xml` |
| 보안 pytest | **125/125 = 100%**, 실패·오류·건너뜀 0 | `security-ready.xml.gz` |
| 실제 PG 동시성·접수·멱등성 회귀 | **41/41 = 100%**, 실패·오류·건너뜀 0 | `concurrency-intake.xml` |
| 새 사본 Vitest | **1,224/1,224 = 100%**, 136파일 | `web-test.log` |
| 새 사본 ESLint / 타입 검사 | **2/2 = 100%**, lint 604파일·오류0·경고0 | `web-lint-summary.json`, `web-results.json` |
| 최신 tip에서 패치 정방향 검사·실제 적용·역방향 검사 | **3/3 = 100%** | `patch-*.log` |
| 이전 증거 크기·SHA256 재검사 | **61/61 = 100%** | `prior-evidence-audit.json` |
| 이번 웹 입력과 이전 실제 production 빌드 입력 | **1,378/1,378 = 100%**, 줄바꿈 정규화 비교 | `complete-web-build-correspondence.json` |

이전 production 빌드 exit0·Edge Playwright **10/10 = 100%**·추가 probe **4/4 = 100%**는 이번에 다시 실행했다고 세지 않습니다. 검증된 이전 증거의 무결성과 이번 후보 입력 전체의 일치를 새로 확인하여 적용 범위를 연결했습니다(`prior-verified/`). 브라우저 API는 모형이었고, 이번 백엔드는 실제 PostgreSQL·실제 API TestClient·제품 코드를 실행했으며 모델과 외부 공급자는 시험 대역입니다. 실제 유료 모델·운영 고객 요청 시험은 아닙니다.

실제 실행 명령은 `python -m scripts.verify_dod_v11 --evidence-dir ...`, `python -m pytest tests/contract -q`, `python -m pytest tests/security -q`입니다. 추가 회귀는 `tests/e2e/test_web_initial_concurrency.py`, `tests/e2e/test_intake_read_lock.py`, `tests/unit/travel/test_intake_read_lock.py`, `tests/e2e/test_trip_intake_api.py`, `tests/contract/test_consumer_idempotency_contract.py`, `tests/unit/core/test_idempotency_request_id.py`를 함께 실행했습니다. 동시 접수의 단일 Case·단일 적용·outbox 중복 방지, 읽기/쓰기 잠금, stale revision을 실제 DB에서 확인합니다. 전체 명령·실행 환경 구성은 첨부 스크립트에 있습니다.

## 환경 복구와 실패 보존

Python 3.14의 pytest 부재가 이전 필수 관문 0/3의 원인이었습니다. 기존 프로젝트의 Python **3.12.15 AMD64 / pytest 8.4.2** 환경을 읽어 사용했습니다. 직접 고정 의존성 중 없는 `ddgs==9.16.1`, `primp==2.0.1`만 새 scratch `deps/`에 `pip --target --no-deps --only-binary=:all:`로 설치했습니다. 기존 Python 환경에 설치·변경하지 않았습니다. Composer는 CI와 같이 이 격리 사본의 `final_project_sample` 패키지 경로만 연결했습니다(여행 시험 자료를 sample에서 가져오지 않았습니다).

전용 PostgreSQL **16.15**, `127.0.0.1:55491/st4f711`, `TimeZone=Asia/Seoul`입니다. 포트 선점 검사를 거쳐 새 `pgdata/`를 만들고 제품 마이그레이션·여행 seed·프롬프트 등록을 수행했습니다. 공유 DB·실DB·실모델은 건드리지 않았습니다. 첫 계약 수집 실패(Composer 경로 누락), 보안 124통과/1실패(PATH의 실행 불가 Git), DB identity 진단 스크립트의 따옴표 오류는 scratch 원본 로그에 보존했습니다. 경로·진단만 보완했고 제품 코드나 시험 기준을 약화하지 않았습니다. 최종 결과는 위 표입니다.

Git·Node는 이전 검증의 독립 MinGit과 지원 Node **v24.22.1 ARM64**를 사용했습니다. 실행이 차단된 WindowsApps `gh.exe`는 이 세션 scratch에 실행 파일만 복사해 기존 OS 키링 인증으로 사용했습니다. 토큰 출력·복사·저장이나 전역 Git 설정 변경은 없었습니다. 첫 커밋의 identity 미설정 실패도 보존하고, 인증 계정의 공개 GitHub noreply identity를 해당 프로세스에만 지정했습니다.

## 최신 원격·협업·반영

루트·cs AGENTS/CLAUDE/RULE, 양쪽 wiki 인덱스, 인계, 접수 계약, 실제 호출부를 읽었습니다. 원본의 오래된 제품명 문구와 최신 guguroute 지침의 차이를 인지하고 현재 사용자 지시·wiki 계약을 적용했습니다. T·S3·S·R·V의 `_coord` NOTICE를 읽어 해시·시각을 보존했고, 별도 ST4F711-backend NOTICE로 작업 경계와 통합 예정 시점을 게시했습니다. 다른 작업자 트리에 쓰지 않았으며, 타 작업자의 명시적 응답을 받았다고 주장하지 않습니다. 푸시 직전에 NOTICE 무변경과 양쪽 원격 부모 `c714eecdb...`를 다시 확인했습니다. dry-run 두 원격 모두 통과 뒤 강제 옵션 없이 푸시했습니다.

| 원격 | 실제 반영 소스 해시 |
|---|---|
| 팀 SKN role-manager | `217da9ad07d16374b2401924418b7115f81769ab` |
| 개인 A-COP role-manager | `217da9ad07d16374b2401924418b7115f81769ab` |

`role-manager`는 x600 자동 반영 대상이라는 후속 운영 기록을 확인했습니다. 검증을 마친 최소 소스만 푸시했으며, 서비스·타이머·배포 설정을 조작하지 않았습니다. 이후 문서 전용 커밋은 소스를 바꾸지 않습니다. 최종 문서 포함 tip은 세션 최종 보고·별도 원격 조회 결과로 확인합니다.

## 정확한 남은 항목과 보존

1. **운영 반영 확인 미완료:** 자동 배포의 실제 적용 SHA·고객 경로·복구 동작은 이번에 검증하지 않았습니다. 푸시 성공을 운영 성공으로 보고하지 않습니다. 운영 인수 전체 비율은 **분모 모름**입니다.
2. **LB-09 역사적 원인 미확정:** 당시 입력·URL·요청 원본을 확보하지 못했습니다. 재현·수정한 경로전환 실패 결함과 당시 사건이 같은 원인이라고 단정하거나 이슈를 완전 종결하지 않습니다.

이전 `w711` scratch의 `.next-resume711` 생성물 lint 346오류·9,316경고는 보존합니다. 이 낡은 scratch의 `npm run check` 통과를 선언하지 않으며, 이번 깨끗한 최신 사본의 lint 결과와 구분합니다. 그 생성물 문제는 이번 소스 반영의 실패가 아닙니다.

원본 소스·Git 색인·sparse/skip-worktree 설정·다른 세션의 자료를 변경하지 않았습니다. 새 clone·의존성·PG data·실패/성공 로그는 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/st4f711-backend-20261029-v1`에 보존합니다. 원본의 새 문서·링크만 추가하고, 기존 인덱스는 수정 직전 사본과 SHA를 보존한 뒤 덧붙입니다. 자료 삭제0이며 전용 시험 DB 프로세스는 증거 수집 후 종료하고 data는 남깁니다. 최종 종료·용량 실측은 후속 보존 기록에 남깁니다.

[이번 증거](../evidence/2026-10-29_st4f711-backend-gates/manifest.json) · [원격 반영 확인](../evidence/2026-10-29_st4f711-backend-gates/source-push-result.json)

## 최종 보존 실측

전용 PG를 정상 종료했고 55491 리스너 없음까지 확인했습니다. data와 모든 로그는 보존합니다. scratch 실측 21,191파일·2,310,984,468바이트(2.152GiB), C: 여유 314.393GiB입니다. 기존 의존성 junction은 합계에서 제외했습니다. 자료 삭제0, 다른 세션 프로세스 종료0입니다. [종료](../evidence/2026-10-29_st4f711-backend-gates/pg-stopped.json) · [용량·보존](../evidence/2026-10-29_st4f711-backend-gates/retention.json).

?? ??? ??? ??? build.log? ?? ? ? ??3????? ? ?? web-test.log? ??? ? ?? ?? ?? diff ??? ?????. ?? ??? ???? ?????. ?? ?? staged diff ??? exit0??, ?? ??2??? ??? ????? ??? ?? ?????. lint ignore? ?? ?? ?? ??? ????.

?? ?? ???? 1?? ???? ??? ?? ?? ??? JUnit ???? ??? ??? 1??/12??????. ?? XML? ?? ? ?? ??? ??? ??, ?? ???? ??? ? ?? gzip? Git? ?????(?? ?? SHA256 ??). ?? ????? ????? ??? ??? ???? ?? ??? ?? ?????.

최종 문서·증거 보안검사는 **12/12 = 100%** 통과했습니다. 원시 XML과 1차 실패는 scratch에 보존하며, 공유본에는 바이트 보존 gzip을 사용했습니다. [최종 문서 검사](../evidence/2026-10-29_st4f711-backend-gates/docs-security-summary.json).
