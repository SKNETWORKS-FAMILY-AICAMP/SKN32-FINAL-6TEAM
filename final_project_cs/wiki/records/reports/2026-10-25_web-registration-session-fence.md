---
type: report
title: 늦은 등록 응답의 발신 세션 귀속 P2 최소 수정
status: draft
domain: travel
---

# 늦은 등록 응답 세션 귀속 — 2026-10-25

## 결론

독립 검토가 재현한 **P2 1/1 = 100%**를 로컬 프런트엔드 회귀에서 수정했습니다. A 발신 → 응답 보류 → B 교체 → A 응답 도착 시 B의 메모리 등록 응대가 되던 정확 반례를 confirm JSON·plan JSON/SSE에서 먼저 RED로 확인하고 GREEN으로 전환했습니다. 저장 차단뿐 아니라 성공 Promise 반환을 거부하여 그 결과에 의존하는 이동/상위 사용을 차단합니다. **통합·제품 전체 수락은 닫지 않습니다.**

담당: 세션 귀속 P2 구현 child. 계약·웹 호출 경계 검토: 본 child의 자체 검토이며, 부모 매니저의 독립 검토·루트 상태/인계 통합은 별도입니다. 앱·브라우저·실 HTTP API·DB·모델·배포·커밋/푸시는 실행하지 않았습니다.

## 코드 전 안전 계약·보존

- root/cs 규칙·wiki, 웹 응대 소비 계약, 지정 `response-readonly-review/{findings.md,probe.cjs}`, 기존 타입 수정 보고서와 검증 스크립트를 읽었습니다. 독립 반례의 두 입력 소스 SHA256이 이번 수정 전 백업과 일치합니다.
- 구현 전 [웹 소비 계약](../../external/web-response-status.md)에 실제 발신 시점의 세션/세대 귀속, 게스트 생성 이후 포착, 교체·로그아웃·A→B→A 거절, 저장과 성공 반환의 동시 차단, 재연결/재시도 경계, 비밀 로그 금지를 보완했습니다. API 요청/응답 필드·서버 소유권·버전은 변경하지 않았습니다.
- 수정할 기존 dirty/untracked 파일과 원본 tsconfig·next-env·trip-home·cs index를 프로필 scratch `session-fence-20261025/backup/`에 바이트 보존했습니다. reset/restore/stash/삭제로 기준선을 만들지 않았습니다.
- 최초 전체 root status는 도구 원본 출력 `cache/terminal-output/out-1792855736-11324-8d60.log`에 남았습니다. Python subprocess로 별도 Git status 저장을 시도한 부분만 WinError 5로 차단되어 terminal의 허용된 Git 읽기로 후속 status를 보관했습니다. 코드/시험 실행에는 차단이 없었습니다.

## 최소 수정과 원인

원인은 `intake.ts`의 confirm/plan await 뒤 `rememberRegistration`이 발신자 대신 도착 당시 `currentSession().csrf`를 읽던 것입니다. 같은 CSRF로 돌아오는 A→B→A는 값 비교만으로도 막을 수 없습니다.

- `src/lib/response-state.ts`: 실제 발신 세션을 `sessionSnapshot()` 객체 동일성(세대)에 묶는 작은 요청 fence를 추가했습니다. 결과 처리 전에 같은 세대인지 확인하며 실패하면 원문·토큰 없는 고정 `stale_registration_session`을 던집니다. 메모리 등록 응대 조회도 CSRF 문자열 대신 이 세대와 여행 ID를 확인합니다. 오래된 결과가 새 B 등록 응대를 지우지 않습니다.
- `src/lib/live/intake.ts`: confirm/plan 각각의 fence를 요청과 결과까지 유지합니다. stale 검사는 response 해석·메모리 저장·성공 반환보다 먼저 실행합니다. legacy에서 response가 없어도 stale trip 성공은 반환하지 않습니다.
- `src/lib/live/client.ts`, `src/lib/live/stream.ts`: 실제 dispatch를 잡기 위한 **선택 callback 전달만** 좁게 추가했습니다. API의 최초 게스트 생성/CSRF 재시도, stream의 sessionInit 이후 async 경계/재연결마다 fence가 실제 세션을 확인합니다. 사전 null 캡처나 api 호출 전 ensureSession만으로 실제 발신자를 추정하지 않습니다. callback 없는 기존 호출은 유지하며 wrapper 전체 재설계는 하지 않았습니다.
- 세대가 바뀌는 forced session refresh도 보수적으로 stale 거절합니다. 토큰 값이 같거나 이전 session 객체가 다시 사용돼도 새 snapshot이면 거절합니다. 이것은 서버 작업 취소·등록 롤백·다시 등록을 의미하지 않습니다. 이후 현재 여행을 확인하도록 하는 기존 오류 반환 경계입니다.
- 변경 제품 코드 4개·시험 2개입니다. trip-home/다른 UI/백엔드/설정/원본 generated 폴더는 수정하지 않았습니다.

## 정확 반례 RED → GREEN

명령의 Node는 모두 기존 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/cs-web-response-status/node.exe`이며 실측 **v24.10.0 x64**입니다. 패키지 설치·엔진 변경 없음.

1. 구현 전 `node node_modules/vitest/vitest.mjs run src/lib/live/response-consumption.test.ts`: **3 failed / 12, 기존 9 passed, exit 1**. confirm·plan JSON·plan SSE 모두 B에서 `registrationFor('trip-A')`가 A 응대 객체를 반환하여 `undefined` 기대와 충돌했습니다. `red-exact.log`.
2. 최소 구현 직후 동일 명령: **12/12 = 100%, exit 0**, `green-exact.log`. 정확 반례는 외부 HTTP 없이 실제 client/api/stream/intake/response-state를 거치고 fetch 경계만 보류하는 대역입니다. 성공 후 이동을 대신한 상위 `.then` callback이 호출되지 않는 것도 확인합니다. 실제 라우터/브라우저 이동을 실행한 증거는 아닙니다.
3. 이후 경계 시험 확장: 두 파일 **37/37 = 100%, exit 0**, `green-boundaries.log`. 경계 25개는 GREEN 뒤 추가한 회귀/부정 검증이며 별도의 test-first 사이클이었다고 주장하지 않습니다. 이번 신규 시험 합계는 정확 반례 3개 + 경계 25개 = **28개**입니다.

### 경계 시험 범위

- confirm JSON, plan JSON 및 SSE result 각각: 로그아웃, A→B→A(동일 A 객체 반환), 동일 CSRF의 새 세대, legacy stale 응답 거절, 현재 B 등록 응대 보존.
- 각 경로의 최초 게스트 세션 생성, 같은 세션 정상/동일 revision 재요청에서 이미 등록된 결과 응답, response 없는 legacy 유지, 다른 trip ID 조회 차단, URL/브라우저 저장소에 신규 문맥 쓰기 없음.
- 저장된 A 등록 응대도 A→B→A 뒤 무효화. CSRF 거절/세션 교체 뒤 두 번째 등록 POST 없음. SSE 중단/교체 뒤 다른 세대로 재연결 POST 없음. fetch headers 이후 JSON body 해석 중 세션 교체도 최종 결과 거절.
- 고정 오류에 CSRF·고객 응대 원문·detail 미노출. CSRF 값/세션 객체를 로그에 추가하지 않았습니다.
- confirm은 기존 JSON API, plan은 JSON fallback/SSE result 계약입니다. confirm에 신규 SSE 지원이나 plan용 별도 duplicate 이벤트를 발명하지 않았습니다. 중복은 기존의 동일 revision 재요청→동일 등록 결과 의미를 검증하며 서버의 멱등 DB 실행을 재검증한 것은 아닙니다.

## 전체 검증 — 단일 최종 소스 집합

증거 루트: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/cs-web-response-status/session-fence-20261025/`.
기존 `type-repair-run.py`와 로그를 읽고 새 `session-fence-run.py`/`session-fence-verify.py`로 고유 출력 폴더를 사용했습니다. 원본 로그/기존 clean-web은 덮지 않았습니다.

| 관문 | 실제 결과 | 근거 |
|---|---|---|
| 전체 `node node_modules/vitest/vitest.mjs run --reporter=default --reporter=json --outputFile.json=<새 증거 폴더>/all-vitest.json` | **798/798 = 100%, 92/92 파일, 실패/skip/todo 0, exit 0** | `all-vitest.log`, JSON의 정확 assertion 수를 코드 집계 |
| 원본 `node node_modules/typescript/bin/tsc --noEmit --incremental false` | **exit 2 유지**, 기존 `.next-live/types/validator.ts(5,56)` TS2306 1건만 | `original-tsc.log` |
| 수정 6파일 ESLint | exit 0 | `scoped-eslint.log` |
| 깨끗한 격리 `node node_modules/next/dist/bin/next typegen` | exit 0 | `clean-typegen.log` |
| 격리 동일 tsc, build 전 | exit 0 | `clean-tsc-before-build.log` |
| 격리 `node node_modules/next/dist/bin/next build --webpack` | **exit 0**, webpack 컴파일 → TS → page data → **static 11/11 = 100%** → optimization → traces → 전체 route 표 완료 | `clean-next-webpack-production-build.log` |
| 격리 동일 tsc, build 후 | exit 0 | `clean-tsc-after-build.log` |

격리 `clean-web`에는 원본 src/public(기존 검사 제외 보존물 `_backup` 제외), 동일 tsconfig·next-env·lock·Next/Vitest/ESLint 설정을 복사했습니다. private env/원본 generated 디렉터리는 복사하지 않았으며 기존 node_modules junction을 사용했습니다. `NEXT_DIST_DIR=.next-live-hours`, `NEXT_PUBLIC_DATA_MODE=live`, `NEXT_PUBLIC_MAP_PROVIDER=osm`, `NEXT_TELEMETRY_DISABLED=1`로 기존 검증 환경을 재사용했습니다.

빌드 후 **381/381 = 100%** 입력 파일의 원본/격리/사전 manifest SHA256이 일치합니다. 원본 tsconfig·next-env·trip-home은 시작 백업과 일치하며 검사 완화/타입 예외/설정 삭제는 없습니다. 원본 `.next-live/types/routes.d.ts`는 **0바이트 유지**, 깨끗한 생성본은 **1,965바이트**입니다. 격리 build ID: `rK1hjflG-Yj0CVaBDmd_8`. 원본 tsc 통과로 바꾸어 보고하지 않습니다.

## 소스 SHA256·변경 경계

아래는 Git HEAD 대비 전체 dirty diff가 아니라 **이번 시작 백업 → 이번 결과**입니다. 기존 dirty 응대 UI/타입 수정은 보존했습니다. 전체 시험/계약 hash와 입력 전수는 `verification-manifest.json`, `candidate-input-hashes.json`, `verified-inputs.json`, 본 작업 hunk는 `own.diff`를 확인합니다.

| 파일 (`src/lib/` 아래) | 수정 전 SHA256 | 수정 후 SHA256 |
|---|---|---|
| `live/intake.ts` | `5eb87163fa846ececda674be31657ffcb83ab48cde0ec0b2d3779eac8a5096a6` | `08f0fe62df37ca076c49502c934db8aa5525cd43ec42dfdbaf61f6258b29a705` |
| `response-state.ts` | `59fe6b933b0e3b6ede47448896f6620620171301026824ac5ceacfca619d1ffd` | `8bb25a36f5c556873f5180986f957e54c56fb3624b7dadd304a0bb4f05fc41aa` |
| `live/client.ts` | `be9d06ade40459dd3e8f06203cc3f054978cc5e0cffe96c819c952ee7ee5a994` | `432891605a75a80559a2e7ef68687d02f42272fdf84cdeb86baa07195a6ccad3` |
| `live/stream.ts` | `f5200674fc1349a2be8d48cae57634d30ad5840649106309bc8b6346b1ff3ccb` | `54b3cf97c655180cf33c08909024e2be50f08ae1341f6728f7b810c82ee69d82` |

제품 코드 외에 `live/response-consumption.test.ts`를 확장하고 `live/registration-session.test.ts`를 새로 만들었습니다. 문서는 `wiki/external/web-response-status.md`, 이 보고서, cs `wiki/index.md` 현재 상태 추기만 변경했습니다. 루트 wiki/색인/인계는 부모 매니저에게 전달합니다.

## 남은 범위·부모 인계

- 독립 P2의 로컬 메모리 귀속 반례는 회귀에서 해소했습니다. 서버 인증 우회·실화면 유출이 있었다는 의미로 확대하지 않습니다. 브라우저 조작, 실제 HTTP/DB 소유권, 서버 멱등 처리·이미 수행한 등록의 후속 처리, 외부 모델·운영 배포는 미검증입니다.
- 원본 tsc generated TS2306은 계속 열려 있습니다. 원본 `.next-live` 삭제/수정·tsconfig 완화는 하지 않았습니다.
- 앱/서비스 시작·브라우저·DB/모델 변경·배포·커밋/푸시 없음. 이번 로컬 수정에는 추가 사용자 결정이 필요하지 않습니다. 루트 현재 상태와 인계는 부모가 이 결과·한계를 통합합니다. **전체 완료/운영 수락을 닫지 않습니다.**
