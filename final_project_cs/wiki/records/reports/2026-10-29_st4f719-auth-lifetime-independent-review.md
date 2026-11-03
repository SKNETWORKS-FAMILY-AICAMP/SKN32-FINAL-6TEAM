---
type: report
title: ST4F-719 인증 수명 수정 독립 검토
status: draft
domain: travel
---

2026-10-29 독립 검토입니다. **수락 보류(HOLD)**입니다. 기존 미리보기 보호는 확인했지만, 모든 인증 경로의 401 처리와 같은 계정 재로그인 보호는 완성되지 않았습니다. 제품 코드는 수정하지 않았습니다.

## 재현한 결함

1. **P1 — 인증 스트림의 401이 인증 수명을 끝내지 않습니다.** `frontend/apps/web/src/lib/live/events.ts:73`, `intake-events.ts:237`, `stream.ts:238`의 watcher는 401을 `failed`/`unsupported`로만 반환합니다. `sessionChecked`를 호출하지 않아 `currentSession()`과 인증 수명이 남습니다. 따라서 이 경로에서만 만료를 관측하면 `queryOwner`가 이전 작업을 계속 현재 작업으로 판단할 수 있습니다. 세 watcher 각각의 401 재현 시험이 실패했습니다. 실제 고객 정보 유출을 재현한 것은 아닙니다.
2. **P1 — 늦은 401이 같은 계정의 새 로그인을 지웁니다.** `client.ts:421`의 `sessionChecked`는 요청 시작 때의 인증 수명 대신 `privacyScope` 동일성만 비교합니다. A 요청을 보류하고 A→B→A 또는 A 로그아웃→새 A 로그인 뒤 옛 401을 풀면 새 A가 null이 됩니다. `query-owner.ts`의 수명 검사는 이보다 앞선 세션 상태 변경을 막지 못합니다. 두 순서 모두 실행 재현했습니다.
3. **P1 — 늦은 로그아웃도 같은 계정의 새 로그인을 지웁니다.** `client.ts`의 `logout` 완료는 다른 계정만 보호합니다. A 로그아웃 응답을 보류하고 B→새 A 로그인 뒤 완료하면 새 A 인증이 null이 됩니다. 실행 재현했습니다. 서버 쿠키까지 지워졌다고 주장하지 않습니다.

추가 경계 두 가지도 실패했습니다. 쿠키를 동반하는 `openApi`는 `unauthenticated` 401을 받아도 세션을 무효화하지 않습니다. 공개 기능 조회에서 인증 종료를 요구할지는 계약 판단이 필요하지만, 모든 401에 적용된다는 주장은 성립하지 않습니다. 또 `api`는 본문 없는 HTTP 401을 `HTTP_401`로 해석해 세션을 유지합니다. 현재 서버의 정상 오류 계약은 `unauthenticated` envelope이므로 후자는 방어 범위의 한계로 분리합니다.

수정 방향은 요청 시작의 인증 세대를 401·로그아웃 완료까지 전달하고, 같은 세션 강제 확인은 유지하되 로그아웃/전환 이후의 새 로그인은 옛 완료로 변경하지 않는 것입니다. 모든 인증 fetch 경로를 함께 다뤄야 합니다. 이번 검토에서는 수정·계약 변경을 하지 않았습니다.

## 실행 근거

기존 격리 후보 `scratch/st4f719-blocker-independent-20261029/repo`를 재사용했습니다. 새 clone·운영 접속·사용자 데이터·push·배포·삭제·트래커 쓰기는 0건입니다. 담당은 이번 Codex 독립 검토 세션이며 기존 수정 담당과 별도 검토입니다. 루트/후보 AGENTS·RULE, wiki 허브·역할·웹 인증 계약을 먼저 읽었습니다. 현재 `wiki/coord`·`_coord`는 없고 전용 coord 도구도 없었습니다. 기존 `scratch/st4f719-review-20261029/coord-read.json`(62개 snapshot)을 읽었으나 최신 예약 상태를 보장하지 않습니다. 통합 예약은 하지 않았습니다.

시험·로그는 `scratch/st4f719-blocker-independent-20261029/auth-lifetime-independent/`와 같은 상위 폴더의 `browser-auth-lifetime-independent-*`, `browser-auth-lifetime-ui-independent-*`에 보존했습니다. 새 시험은 후보의 `src/lib/live/auth-lifetime-independent.test.ts`와 `tests/live/auth-lifetime-ui-independent.spec.ts`입니다.

| 검증 | 결과 |
|---|---|
| 집중 Vitest 최종 실행 | 32/40 = 80%, 실패 8, skip 0 |
| 그중 새 독립 경계 | 4/12 = 33.3%, 실패 8 |
| 그중 기존 수명·소유권·인증 시험 | 28/28 = 100% |
| 기존 미리보기 Edge 재실행 | 28/28 = 100%, skip/flaky 0 |
| 기존 실제 PG 인증·로그아웃 Edge | 10/10 = 100%, skip/flaky 0 |
| 여행 목록 401 오류 표시 Edge | 수정된 시험 1/1 = 100%, 최초 기대 문자열 손상 실패 1건 별도 보존 |
| 기존 제품 소스·보안 파일 보존 | 508/508 = 100% SHA256 일치 |
| 기존 scanner·보호 XML | 2/2 = 100% 기존 SHA256 일치 |

Vitest는 공식 설치된 Node로 `vitest.mjs run`에 위 새 시험과 `authorization-lifetime.test.ts`, `client-identity.test.ts`, `query-owner.test.ts`, `client-blocker-review.test.ts`를 주고 `--maxWorkers=1 --reporter=json`으로 실행했습니다. 첫 실행 31/38 이후 로그아웃/쓰기 재전송 시험 두 개를 추가해 최종 32/40이 됐습니다. 첫 실패도 보존했습니다. 통과 대조군은 일반 API의 정상 envelope 401, 동일 세션 refresh, 늦은 A 401 뒤 B 유지, 401 뒤 mutation 본문 재전송 0회입니다.

Edge는 기존 `run_late_gates.py browser-auth-lifetime-independent`와 `BROWSER_SPECS=independent-preview-verify`, `API_PROBES=0`, `INDEP_PROBES=0`으로 실행했습니다. 7경계(동일/다른 계정/전환 복귀/비인증/비인증 복귀/전환+unmount/unmount만)×4모드(성공/실패/retry/discard)입니다. 실제 로컬 PG 쿠키 인증 `/auth/me`와 실제 Next/React/Edge를 사용했고 업무 미리보기는 stub입니다. 이전 결과가 UI·미리보기 상태·query cache에 들어오지 않고 B 대조 데이터가 유지됨을 확인했습니다. 실제 PG 업무 쓰기 또는 전체 앱의 모든 계정 간 쓰기를 증명한 것은 아닙니다.

정적 전체 `src` fetch 검색에서는 공통 client, 세 watcher, 쓰기 stream attempt, 공개 공지 조회 두 곳을 확인했습니다. 공지는 `credentials: omit`입니다. `stream.attempt`는 `sessionChecked`를 쓰지만 위 같은 계정 경합을 공유합니다. 개별 HTTP endpoint 전수 시험의 분모는 모릅니다. 전 경로 401 완료로 보고하지 않습니다.

## 보존·남은 범위

기존 보안 실패 124/125 = 99.2%, 필수 관문 2/3 = 66.7% HOLD는 이전 실행 결과이며 이번 실행 수치가 아닙니다. 독립 검토에서 전체 관문을 재실행하지 않았습니다. scanner 예외·XML·보안 정책을 변경하지 않았고 HOLD를 해제하지 않습니다. 원 지정 인계·보고서에는 `?`로 손상된 문장이 있어 의미를 추측해 복원하지 않았습니다.

실행은 기존 로컬 PG data directory와 기존 Next 캐시를 재사용하고 worker 1로 제한했습니다. 새 DB 전체 사본이나 대형 산출물을 만들지 않았습니다. `disk_guard.py inventory`는 entries 0, free 182,619,779,072 bytes, min 32,212,254,720, target 400,000,000,000을 보고했습니다. 이 scratch의 ledger lease가 없어 타 소유권 등록/release는 하지 않았습니다. PG/Next 순증은 사전 크기 측정이 없어 분모 모름이며 총 산출물 크기와 종료 영수증은 후속 아래에 기록합니다.

한 일 목록: 규칙/wiki/coord 확인, 기존 후보 fetch 경로 감사, 독립 경합·401 시험 작성/실행, 실제 PG 인증 Edge 재검증, 화면 오류 검증, 해시 보존 확인, 별도 보고·인계 작성입니다. 실제 외부 OAuth 제공처 로그인, 운영 배포, 실제 고객 여행 쓰기는 검증하지 않았습니다.

종료 영수증: PG data directory 신원 확인과 종료 로그를 남겼고 app/stub/api/PG 네 포트 4/4 = 100% 연결 거부를 확인했습니다. 기존 소스·보안 508/508과 보호 scanner/XML 2/2를 종료 후에도 다시 해시 확인했습니다. `final.json`, `preservation.json`, `disk-inventory-final.json`을 보존했습니다. 이번 증거·새 시험·해당 browser 로그 40파일은 357,182 bytes입니다. 이 크기는 기존 PG/Next 캐시와 Playwright 출력 폴더를 제외한 명시 범위이며 전체 디스크 증가량은 아닙니다. 자료는 삭제하지 않았고 이 세션의 로컬 검증 사용을 종료했습니다.

화면 검증 보충: 실제 PG 인증 후 여행 목록 GET만 합성 401로 바꿨습니다. 실제 `/trips` DOM에서 만료 안내가 보이고 1초 뒤에도 유지되며 로그인·재조회 버튼이 남는지 확인했습니다. 스크린샷 `auth-lifetime-independent/visible-error.png`도 직접 열어 확인했습니다. 최초 새 시험은 PowerShell stdin의 한글 기대 문자열이 `?`가 되어 실패했습니다. 오류 DOM에는 정상 한국어 안내가 있었고, 기대 문자열만 Unicode escape로 고친 고유 이름 재실행이 1/1 통과했습니다. 최초 실패 로그·JSON·DOM 문맥은 보존했으며 제품 회귀 실패로 분류하지 않습니다. 기존 실제 PG 인증 10개는 별도 실행에서 모두 통과했습니다. 이 결과를 합쳐 모든 endpoint·화면 오류가 검증됐다고 일반화하지 않습니다.
