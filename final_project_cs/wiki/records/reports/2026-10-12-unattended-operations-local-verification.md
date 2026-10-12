---
type: report
title: 무인 운영·자료 조회 정책 로컬 구현 검증
date: 2026-10-12
status: waiting_dependency
---

# 무인 운영·자료 조회 정책 로컬 구현 검증

설정 저장·진단 복구·사후 분석 화면을 구현하고 관련 로컬 시험을 통과했습니다. 실제 자료 조회와 공통 오류 수집·주기 재전송의 접합이 남아 W05·W09 전체 완료로 판정하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 백엔드 시험 | 통과 | 51/51 = 100% |
| 운영 화면 확인 | 통과 | 9/9 = 100% |
| 고객 화면 mock 서버 시험 | 통과 | 3/3 = 100% |
| 핵심 실제 호출 접합 | 대기 | 0/3 = 0% |

위 분모는 실행한 시험 사례와 인계한 핵심 접합 세 곳의 수입니다. 제품 전체·W05·W09의 완료율이나 성능 측정치가 아닙니다. 기록 시각: **2026-10-12T04:44:38+09:00**. 독립 검토는 통합 담당 대기입니다.

## 문제와 바뀐 동작

기존 고객 문의는 운영자가 답변하거나 상태를 바꾸는 업무를 전제했습니다. 고객 접수는 이제 **문제 신고·건의 기록**이며 기록 성공을 여행 문제 해결로 안내하지 않습니다. 답변 대기를 약속하지 않고 여행 목록에서 직접 재시도·장소 입력으로 돌아가는 경로를 둡니다. 고객별 목록은 본인 범위를 먼저 검사하고 페이지 조회합니다. 같은 요청 UUID의 재전송은 같은 기록으로 돌아갑니다. 기존 과거 안내 기록은 보존합니다.

운영 앱은 **무료 자료 우선·유료 재조회 허용/상한·최소 간격**을 DB에 저장합니다. 로그인·권한·CSRF 검사, 판본 비교에 의한 동시 변경 거절, 변경 사유·감사가 같은 트랜잭션에 연결됩니다. 정책 서비스 실행 시험에서는 설정을 바꾼 뒤 실제 선택 결과가 바뀌었습니다. 실제 식당 조회 호출부는 아직 이 서비스를 부르지 않습니다.

사후 진단은 오류 코드·배포/정책 판본·재현 코드·발생/사건/요청 UUID·영향 고객을 저장합니다. 동일 발생 UUID는 한 번만 집계하고 동일 결함 묶음의 발생 수와 중복 없는 고객 수는 표본으로 줄이지 않습니다. 100명에게 100번 발생한 결함이 100건·100명으로 집계됐습니다. 고객 UUID와 발생 상세 조회는 추가 `case:read` 권한을 요구합니다. 운영 화면에서 발생·요청 번호를 조회하고 검증한 해결 판본을 감사와 함께 기록합니다. 고객 일정을 직접 수정하지 않습니다.

기존 229 서비스 개선은 동의 기반 합성 자료입니다. 기존 마스킹·감사·인증 체계를 재사용하되 고객 연결을 그 합성 자료에 덧붙이지 않았습니다. 별도 SQL 후보 902로 결함 연결을 분리했습니다. 보존 기간은 기본 30일이고 누적 건수·해결 판본은 유지합니다.

DB 저장 실패는 마스킹된 SQLite 영속 대기 파일로 보관합니다. 같은 발생 UUID로 재전송하고 DB 커밋 후 대기 행을 지워 커밋 직후 중단에도 중복 집계를 막습니다. 포화 시 기존 대기 기록을 덮지 않고 유실 카운터를 기록합니다. 디스크까지 실패하면 `collection_degraded`로 드러냅니다. 만료 기록이나 삭제된 고객의 대기 기록은 되살리지 않습니다. 파일·WAL의 물리 크기가 아니라 대기 payload의 UTF-8 합계와 건수를 제한합니다.

## 실행 증거와 재현 조건

### 백엔드

- [최종 JUnit XML](../../../../scratch/operations-20261012/backend-final-v5.xml): 성공 51, 실패 0, 오류 0, 건너뜀 0, 실행 91.681초. 시간은 이 한 실행의 벽시계이며 성능 비교용 반복 측정이 아닙니다.
- 업무 DB 대신 scratch에 설치한 PGlite 0.3.14의 메모리 PostgreSQL 실행을 사용했습니다. 기본 customers/trips 및 기존 226과 신규 902 SQL을 읽고 신규 SQL은 두 번 적용했습니다. [PGlite 공식 문서](https://pglite.dev/docs/)는 도구 참고 출처이며 제품 완료의 근거는 위 실행 결과입니다.
- Windows 샌드박스에서 TestClient의 소켓 초기화가 멈추는 범위를 확인해 시험을 샌드박스 밖에서 실행했습니다. 업무 DB로 폴백하지 않는 opt-in 시험입니다. 실제 PostgreSQL 다중 프로세스 잠금 경쟁을 검증한 것은 아닙니다.

작업 위치는 cs 프로젝트 폴더입니다. `OPS_PGLITE_MODULE`을 scratch의 설치 모듈로 지정한 뒤 다음 명령을 실행했습니다.

```powershell
$env:PYTHONUTF8='1'
$env:OPS_PGLITE_MODULE=(Resolve-Path ../scratch/operations-20261012/pglite/node_modules/@electric-sql/pglite/dist/index.js).Path
python -m pytest tests/unit/test_operations_diagnostics.py tests/security/test_unattended_operations.py tests/security/test_admin_json_gateway.py tests/integration/db/test_unattended_operations.py -q -p no:cacheprovider --basetemp=../scratch/operations-20261012/pytest-final-v5 --junitxml=../scratch/operations-20261012/backend-final-v5.xml
```

검증 항목: 설정 영속 저장·감사·판본 충돌, 로그인·권한·CSRF·행위자 위조 거절, 조회 실패 503, 무료 우선·유료 시간 창·예산 소진·실패 시 예산 소비·확인 간격, tenant/customer/trip 격리, 마스킹·허용 필드 제한, 100건 집계와 100명 연결, 재전송 멱등성·보존·삭제·디스크 포화, 본인 접수의 중복 방지·페이지 조회. 공급자 함수는 시험용 대역이며 유료 외부 호출은 하지 않았습니다.

### 화면

mock 서버 시험 12/12 = 100% (화면 반응): 운영 구성요소 9/9, 고객 앱 3/3.

실서버 확인 (서버 응답): **안 했음** — 실제 배포된 cs 프로젝트 서버·실제 외부 자료 제공처에 접속하지 않았습니다. 별도로 로컬 FastAPI 시험 클라이언트와 격리 PGlite를 연결해 전용 API 응답을 확인했습니다.

- 운영 화면은 실제 React 구성요소를 별도 검증 페이지에 번들링했습니다. 전체 운영 앱의 탐색·배포 환경을 검증한 것은 아닙니다. [화면 확인 결과 9건](../../../../scratch/operations-20261012/ui/result-v2.json), [1280px 화면](../../../../scratch/operations-20261012/ui/operations-1280.png), [375px 화면](../../../../scratch/operations-20261012/ui/operations-375.png). 입력·권한 오류·판본 충돌·해결 판 저장·저장 실패 후 초안 보존·가로 넘침·브라우저 오류를 확인했습니다.
- 운영 화면 재현: 워크스페이스 루트에서 `node scratch/operations-20261012/build-ui.mjs` 후 `node scratch/operations-20261012/ui-test.mjs`. 설치된 Chrome을 사용했고 원격 사이트를 열지 않았습니다. 초기 추가 시험은 목록 항목의 여러 줄을 정확히 찾지 못해 실패했고 선택자를 고친 뒤 9/9를 통과했습니다. 제품 코드의 실패를 통과로 바꾸어 기록하지 않았습니다.
- 고객 앱 재현: 고객 웹 폴더에서 `STUB_PORT=3370`, `LIVE_PORT=3371`, `LIVE_DIST_DIR=.next-operations-20261012`, `LIVE_SKIP_BUILD=1`, `PLAYWRIGHT_CHANNEL=chrome`을 설정한 후 `npx playwright test tests/live/support.spec.ts --config=playwright.live.config.ts --output=../../../../scratch/operations-20261012/support-playwright-v2`를 실행합니다. 처음 실행 때 새 빌드를 만들었고 최종 재실행은 그 빌드를 재사용했습니다. 3/3 통과, 42.7초. [마지막 실행 상태](../../../../scratch/operations-20261012/support-playwright-v2/.last-run.json). 최초 실행의 출력 상대경로가 작업 폴더 밖 scratch를 가리켜 최종 근거 사본을 위 워크스페이스 scratch에 복사했으며 원본은 삭제하지 않았습니다.
- 고객 support 단위 시험은 `npm test -- src/features/support/support.test.ts src/features/support/client.test.ts`로 6/6 통과했습니다. 두 웹앱의 `node node_modules/typescript/bin/tsc --noEmit`은 종료 코드 0입니다. 운영 앱의 표준 typecheck 앞단 Next typegen은 SWC 경로 접근 오류로 완료하지 못해 TypeScript 직접 검사를 별도 기록합니다. 이 오류를 표준 typecheck 통과로 쓰지 않습니다.

### 그림·변경 범위

[수집 한 회차의 흐름 그림](../../../../program/research/baseline_completion_2026-10-12/tasks/operations/diagnostic-flow.html)은 시작·분기 조건·세 종료 지점을 표시합니다. `diagram-design`의 flowchart 가이드와 acop 프로필을 적용했고 자체 검사 성공 및 Chrome 렌더링으로 겹침을 확인했습니다. 자동 재전송은 그림에서도 인계 대기로 표시합니다.

아래 23개는 이 담당이 변경하거나 새로 만든 소스·시험·전용 계약 파일입니다. 다른 담당의 변경을 포괄하는 목록이 아닙니다. [SHA-256 원본 목록](../../../../program/research/baseline_completion_2026-10-12/tasks/operations/source-manifest.json)은 이 파일들과 인계 문서·그림의 현재 바이트를 기록합니다. 통합 시 바이트가 달라지면 관련 시험을 다시 판단해야 합니다.

- [app/application/operations_policy.py](../../../app/application/operations_policy.py)
- [app/application/operations_diagnostics.py](../../../app/application/operations_diagnostics.py)
- [app/presentation/admin_operations_api.py](../../../app/presentation/admin_operations_api.py)
- [app/infrastructure/db/migrations/902_unattended_operations.sql](../../../app/infrastructure/db/migrations/902_unattended_operations.sql)
- [config/operations-policy.yaml](../../../config/operations-policy.yaml)
- [scripts/replay_operations_diagnostics.py](../../../scripts/replay_operations_diagnostics.py)
- [app/ops_entrypoint.py](../../../app/ops_entrypoint.py)
- [app/application/admin_service.py](../../../app/application/admin_service.py)
- [app/domains/travel_ops/modules/web_account/admin_customer_api.py](../../../app/domains/travel_ops/modules/web_account/admin_customer_api.py)
- [frontend/apps/admin/src/features/operations/source-policy.tsx](../../../frontend/apps/admin/src/features/operations/source-policy.tsx)
- [frontend/apps/admin/src/features/operations/connected.tsx](../../../frontend/apps/admin/src/features/operations/connected.tsx)
- [frontend/apps/admin/src/lib/gateway.ts](../../../frontend/apps/admin/src/lib/gateway.ts)
- [frontend/apps/admin/src/components/AdminApp.tsx](../../../frontend/apps/admin/src/components/AdminApp.tsx)
- [frontend/apps/web/src/features/support/support.tsx](../../../frontend/apps/web/src/features/support/support.tsx)
- [frontend/apps/web/src/features/support/client.ts](../../../frontend/apps/web/src/features/support/client.ts)
- [frontend/apps/web/src/features/support/support.test.ts](../../../frontend/apps/web/src/features/support/support.test.ts)
- [frontend/apps/web/tests/live/support.spec.ts](../../../frontend/apps/web/tests/live/support.spec.ts)
- [tests/unit/test_operations_diagnostics.py](../../../tests/unit/test_operations_diagnostics.py)
- [tests/security/test_unattended_operations.py](../../../tests/security/test_unattended_operations.py)
- [tests/security/test_admin_json_gateway.py](../../../tests/security/test_admin_json_gateway.py)
- [tests/integration/db/operations_pglite.mjs](../../../tests/integration/db/operations_pglite.mjs)
- [tests/integration/db/test_unattended_operations.py](../../../tests/integration/db/test_unattended_operations.py)
- [wiki/operations/unattended-operations.md](../../operations/unattended-operations.md)

## 남은 접합과 제한

[담당별 구체적 접합 계약](../../../../program/research/baseline_completion_2026-10-12/tasks/operations/handoff.md)에 호출부와 필수 시험을 정리했습니다.

1. Dining 새벽 조회에 정책 서비스 연결: 기존 공급자 예산의 첫 예약을 이중 차감하지 않는 어댑터가 필요합니다. 논리 재조회 상한과 HTTP 호출 예산의 단위를 구분합니다. 무료 표의 영업시간을 실제 개점 확인으로 추정하지 않습니다.
2. 공통 실행 오류 수집과 주기적 재전송·보존 정리: 이번에는 고객 건의와 정책 서비스 검증 불가만 수집에 연결했습니다. 배포 판본 주입·비공개 영속 볼륨·파일 접근권한·스케줄 연결과 저하 상태 노출은 통합 인수 항목입니다.
3. 인증 파일의 이용 제한 안내와 공통 탐색 메뉴의 답변 전제는 해당 소유 담당에게 문구 접합을 인계했습니다. 실제 자동 해제 기능이 없는데 해제를 약속하지 않습니다.
4. 실제 PostgreSQL의 다중 연결 동시 예약·전체 스키마·안전 SQL 실행기, 전체 contract/security 및 현재 DoD 관문·독립 검토는 통합·검증 담당 범위입니다. 이 보고서는 관련 전용 시험만의 결과입니다.

업무 DB 변경·원격 배포·재시작·고객 알림·유료 외부 호출·예산 확대·커밋·푸시는 하지 않았습니다. 현재 코드의 실제 운영 적용을 뜻하지 않습니다.

## 백업

기존 파일은 수정 전 복사했고 추가 수정 판본도 보존했습니다.

- [최초 원본 백업](../../../_backup/2026-10-12_035928_unattended_operations): 기존 API·화면·계약 원본. 백업했지만 이번에 수정하지 않은 파일도 포함합니다.
- [추가 원본·이전 판·검증 페이지 백업](../../../../scratch/operations-20261012/_backup): 고객 support·시험·운영 화면 추가 수정 전 판본.
- [상태 파일 이전 판](../../../../program/research/baseline_completion_2026-10-12/tasks/operations/_backup): 최종 상태 갱신 전 기록.
