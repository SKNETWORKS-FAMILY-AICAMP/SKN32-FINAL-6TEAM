# 2026-10-23 고객 웹 상태·비동기·오류 처리 리뷰

확인 시각: 2026-10-23 01:25 KST. `role-eval-ui` 기준 격리 사본 `D:\FinalProject\Dev\fe-audit-20261023`, 검토 브랜치 `review/frontend-audit-20261023`의 현재 소스를 읽었습니다. 소스 코드 변경·서버 실행·운영 API 호출은 하지 않았습니다. 이 문서와 독립 재현 자료만 추가했습니다.

| 확인 범위 | 결과 |
|---|---|
| 접수·계획 확인·등록·등록 여행·채팅·항로 지킴이·실시간 연결·지도 경로의 주요 호출 흐름 | 8/8 = 100% 검토 축 확인. 전체 파일 또는 분기 커버리지 비율은 아닙니다 |
| 아래 결함 후보를 검증하는 격리 Node probe | 5/5 = 100% 실행. 그중 4개는 잘못된 결과/중복을 직접 확인했고, 여행 SSE는 대기 상태와 타임아웃 부재를 함께 확인했습니다 |
| 이 하위 리뷰에서 기존 Vitest·브라우저·실서버 시험 | 0회. 상위 리뷰의 검사 결과와 별도로 기록합니다 |

실행: `node final_project_cs/wiki/records/evidence/2026-10-23_frontend-audit/web-state/web-state-probe.cjs`. [재현 코드](../evidence/2026-10-23_frontend-audit/web-state/web-state-probe.cjs), [실행 결과](../evidence/2026-10-23_frontend-audit/web-state/web-state-probe-result.json). `[2026-10-23 02:27 KST 위치 이동 — Claude]` 기록 폴더로 옮기고 경로만 고쳤으며, 이동 뒤 재실행 결과는 시각 외 동일([재실행 결과](../evidence/2026-10-23_frontend-audit/web-state/web-state-probe-result-after-move.json)).

재현 코드는 현재 소스 파일을 읽어 Node `stripTypeScriptTypes`로 타입만 제거하고 실행합니다. Guardian은 실제 훅의 JSX 반환 직전까지와 실제 mutation callback을 가져왔고, React 저장소·네트워크·query cache는 작은 테스트 대역을 썼습니다. 브라우저 종단 재현 결과는 아닙니다. TypeScript stripping의 ExperimentalWarning은 있었고 probe는 정상 종료했습니다.

## 확인된 문제

### W1 · P2 · 항로 지킴이 변경 실패가 최신 여행 전체를 과거 판으로 되돌립니다

근거: `frontend/apps/web/src/features/guardian/trip-guardian.tsx:50-66`, 특히 **66행** `queryClient.setQueryData<Trip>(key, context.before)`.

1. version 1 여행에서 항로 지킴이를 끄면 `onMutate`가 여행 객체 전체를 `before`에 보관합니다.
2. 그 요청을 기다리는 동안 SSE/채팅/다른 기기의 변경으로 version 2가 query cache에 들어옵니다.
3. 지킴이 요청이 실패하면 query 객체의 동일성만 확인한 후 version 1 전체를 다시 씁니다. query 객체는 같은 채로 data만 바뀌므로 동일성 검사는 이 경합을 막지 못합니다.

probe에서 실제 callback을 실행해 **version 2 → version 1**, 일정 이름도 `changed by SSE` → `before`로 되돌아가는 것을 확인했습니다. 일반 네트워크 오류 갈래는 다시 조회하지 않으므로 다음 변화 신호가 올 때까지 오래된 일정·대화·안전 상태가 남을 수 있습니다. 서버 기록을 되돌리는 문제는 아닙니다.

권장: 실패 시 현재 여행 객체의 guardian 필드만 조건부로 되돌리고 최신 일정은 보존합니다. 요청 세대 또는 mutation 순서를 확인하고 처리 종료 후 authoritative GET으로 지킴이 상태를 맞춥니다. 토글 자체도 pending 중 직렬화해야 응답 역전이 별도로 발생하지 않습니다.

빠진 시험: 토글 시작 → SSE 최신 여행 반영 → 토글 실패, 토글 응답 역전, 토글 도중 로그아웃 및 새 session cache 생성. 현재 `lib/live/guardian.test.ts`의 API 변환 확인과 다른 종류의 훅 경합 시험입니다.

### W2 · P2 · SSE의 CRLF가 청크 사이에서 나뉘면 완료 payload를 잃습니다

근거: `frontend/apps/web/src/lib/live/events.ts:45-63`, 특히 **50행** `buffer.split(/\r\n|\r|\n/)`. 같은 parser가 `stream.ts`의 채팅/계획 생성/후보 스트림과 여행 변경 신호에서 쓰입니다.

정상 SSE `event: result\r\ndata: {"status":"adjusted","version":4}\r\n\r\n`를 `event: result\r`와 나머지로 나눠 전달하면, 첫 청크의 `\r`를 이미 개행으로 소비한 후 둘째 청크의 `\n`를 빈 줄로 다시 처리합니다.

실제 출력은 `result` + 빈 data, `message` + 실제 JSON의 **두 이벤트**였습니다. `stream.ts:110-127`는 빈 result를 `{}`로 파싱해 성공 응답으로 받아들이므로 완료 응답의 trip/version/answer 등을 잃습니다. 여행 변경 이벤트도 본문 없이 먼저 전달되고 정상 본문은 일반 message로 무시될 수 있습니다. 현재 모든 운영 응답이 CRLF라는 주장은 하지 않습니다. parser가 지원하는 CRLF 입력에서 청크 분할만으로 깨지는 결함입니다.

권장: 청크 끝 `\r`를 보류하거나 CRLF의 다음 LF를 건너뛰는 상태를 유지합니다. 완성된 빈 행에서만 이벤트를 dispatch합니다.

빠진 시험: 모든 문자 경계로 나눈 동일 SSE가 동일 이벤트를 내는 테스트. 현재 `events.test.ts:16-23`는 JSON 중간 분할과 한 청크 안 CRLF만 검사해서 이 경계를 놓칩니다.

### W3 · P2 · 등록 여행 SSE가 조용히 멈추면 갱신을 복구하지 못합니다

근거: `frontend/apps/web/src/lib/live/events.ts:70-98`, 특히 **91행**의 무기한 `reader.read()`; `features/trip/use-trip-events.ts:90-93`; `features/trip/use-trip-extras.ts:36,42`.

`ready` 뒤 네트워크가 반쯤 끊겨 fetch reader가 close/error를 전달하지 않는 경우, 헤더 제한과 heartbeat 제한이 모두 없어 `watchTrip`이 반환하지 않습니다. 따라서 재접속 loop가 움직이지 않고 mode는 `bell`에 남으며 알림·제안의 주기 조회도 꺼져 있습니다. 사용자가 같은 탭에 계속 머물면 서버의 변경/안전 알림을 갱신하지 못할 수 있습니다. 명시적 오류가 반복되는 경우에도 polling 전환은 404/405와 429만 처리합니다.

probe에서는 실제 함수에 `ready` 후 열린 채 침묵하는 stream을 주어 caller abort 전까지 대기하는 상태를 확인했습니다. 35ms probe 자체를 장시간 장애 실측으로 제시하지 않습니다. 무기한 대기의 근거는 함수에 시간 제한이 전혀 없다는 코드입니다.

권장: 서버 heartbeat 간격을 기준으로 transport liveness 제한을 두고 모든 byte/comment ping을 생존 신호로 셉니다. 제한 초과 시 reader를 닫고 재접속하며, 연결 복구까지 필요한 조회를 제한된 polling으로 전환합니다. 첫 연결 헤더 제한과 cleanup도 공통화합니다.

빠진 시험: `ready` 뒤 heartbeat 단절, 헤더 무응답, 반복 503 후 복구, 화면 숨김/복귀, unmount 후 재접속 중단.

### W4 · P2 · 접수 SSE는 응답 헤더를 못 받으면 polling으로 넘어가지 못합니다

근거: `frontend/apps/web/src/lib/live/stream.ts:210-238`, 특히 **218-220행** fetch 대기와 **238행** 최초 `arm()`; `features/intake-review/use-intake-events.ts:30-47`; `features/intake-review/intake-review.tsx:79-80,107-110`.

접수 GET은 `reading`이라고 답하지만 events 요청의 헤더가 오지 않는 경우입니다. watchIntake watchdog은 fetch가 끝나고 reader를 만든 다음에만 시작합니다. `follow`는 초기값 live, polling은 false라서 서버가 이미 읽기를 마쳐도 다음 GET이 시작되지 않습니다. 느림 문구만으로 완료 여부를 회복할 수 없습니다.

실제 함수에 `watchdogMs: 5`를 주고 헤더 fetch를 미완료로 두자 35ms 뒤에도 미완료였으며 caller abort를 줘야 끝났습니다. 같은 파일의 변경 요청 `attempt()`에는 헤더 제한이 이미 있지만 watchIntake에는 없습니다.

권장: fetch 이전에 헤더 타이머를 걸고 초과를 lost로 처리해서 재접속과 접수 polling을 켭니다. 이미 abort된 signal도 입구에서 확인하고 헤더 대기 타이머를 finally에서 해제합니다.

빠진 시험: 헤더 도착 전 watchdog 만료 → lost → GET polling으로 완료 확인. 현재의 body heartbeat 단절 시험과 구분합니다.

### W5 · P2 · 대안 사진을 한 번 열 때 두 번씩 요청해 장소 검색 한도를 낭비합니다

근거: `frontend/apps/web/src/features/plan-check/use-server-review.ts:292-310`, 특히 **296행**과 **309-310행**. 캐시 재열기에서도 **143행**이 onFirst를 다시 호출합니다. API 근거: `app/domains/travel_ops/entry/trip_api.py:1727-1737`에서 사진 요청마다 `_count("place_search", …)`를 호출합니다.

후보 첫 목록 onFirst에서 3개 사진을 요청하고, stream 최종 목록을 받은 뒤 같은 세 곳을 다시 요청합니다. 이후 같은 후보 promise를 재사용해도 onFirst 재생과 최종 처리에서 반복합니다. 실제 hook probe 결과 후보 stream은 **1회**인데 사진 HTTP 함수는 첫 열기 **6회**, 두 번 열기 누적 **12회**였습니다. 현재 일정 자체의 사진 요청은 이 숫자에서 제외했습니다.

사진 endpoint는 장소 검색과 같은 고객별 횟수 제한을 소비하므로 반복 열기·여러 일정의 미리 받기가 실제 검색 429에 기여합니다. 서버 계약의 어댑터 메모리 cache가 관광공사 중복 호출을 줄이므로, 이 측정으로 외부 관광공사 호출도 12회라고 주장하지 않습니다.

권장: 현재 화면 수명 동안 ref/language별 in-flight Promise를 공유하고 첫 결과에 붙인 사진을 최종 카드에서도 재사용합니다. 사진 파일의 지속 저장은 하지 않으며 현재 계약의 저장 제한을 유지합니다.

빠진 시험: 첫·최종 후보가 같은 ref일 때 요청 수, 재열기, 동시 구독자, 사진 실패 뒤 재시도, 사진 읽기가 장소 검색 budget을 소모하는 흐름.

## 구조·테스트 개선 제안

- `plan-check.tsx` **2,108행**에 확인 애니메이션, 질문 흐름, 편집 mutation 직렬화, 검색, 목록/지도/시간 조작, 자동 등록, focus 관리가 모여 있습니다. 화면 상태 reducer와 편집 명령 coordinator, 대안 검색 hook, 표시 전용 패널로 나누고 `PlanCheck`는 조립을 담당하게 하는 편이 좋습니다. 단순 파일 쪼개기보다 소유 상태와 이벤트의 경계를 먼저 정의합니다.
- `use-server-review.ts` **527행**은 revision 관리, undo, 후보 promise/stream fan-out, 사진, 장소 검색, 이동 방식, 저장, 재검증을 함께 소유합니다. 후보 조회·사진 생명주기와 intake mutation/undo를 분리하면 W5 같은 중복 요청과 오래된 응답이 섞이는 경합을 각 단위에서 검증할 수 있습니다.
- `trip-screen.tsx` **871행**, 등록 화면 **527행** 역시 화면 제스처와 도메인 mutation을 나눌 대상입니다. `useTripChat`의 최신 version 비교 및 계정 cache 동일성 방어는 좋은 기존 패턴이지만 모든 mutation rollback/응답 반영에 동일한 원칙을 적용해야 합니다.
- SSE parser·transport·재접속 정책이 `events.ts`/`stream.ts`와 두 follow hook에 갈라져 있고 타임아웃·종료 처리 수준도 다릅니다. parser와 전송 생명주기는 공통으로 만들되 읽기 SSE와 멱등 mutation 재전송 정책은 명시적으로 나눕니다.
- 일부 훅 시험은 React API를 직접 흉내 낸 슬롯 harness를 씁니다. 순수 변환 시험을 유지하면서 실제 React/QueryClient를 쓰는 최소 통합 시험을 추가해야 effect cleanup·StrictMode·query observer·비동기 응답 역전을 확인할 수 있습니다. 이번 probe도 이런 통합 시험을 대체하지 않습니다.
- 하드코딩은 정책값·제품 범위·UI 시간값을 구분해야 합니다. `PLAN_DAYS` 1~7/`PLAN_PARTY` 1~4는 현 계약 범위이며 서울 고정도 현재 제품 범위여서 일괄 결함으로 잡지 않았습니다. 재접속/대기/애니메이션 값은 목적별 상수로 모으고 서버 정책값과 혼동하지 않게 해야 합니다.
- 다음 회귀 묶음은 성공 응답만 더하기보다 경합을 우선합니다: 오래된 GET이 mutation보다 늦게 도착, 언어 전환 중 stream 도착, 화면 이탈 중 대안/사진 도착, 재접수/재검증 중 이전 후보 도착, 결과를 저장했지만 응답만 유실되는 경우, 로컬 storage 읽기/쓰기 실패.

## 확인 범위와 남은 한계

상위·프로젝트 작업 규칙, 현재 웹 REST 계약의 입구와 접수/여행 관련 절, 실제 front/back 호출부를 대조했습니다. 과거 인계에 적힌 성공 건수는 이번 실행 결과로 사용하지 않았습니다. 개인 전역 `C:/Users/u/.codex/AGENTS.md`와 `C:/Users/u/.claude/CLAUDE.md`는 이 환경에서 없었습니다.

이 보고는 고객 웹의 상태·비동기·오류 처리 축입니다. 관리자 앱, 의존성 취약점, 전체 접근성 및 실사용 화면 품질은 상위 리뷰의 다른 검토와 합쳐야 합니다. 오래된 GET이 최신 mutation을 덮는 일반 경합은 추가 통합 시험 대상으로 남겼고 이번 확정 5건에 포함하지 않았습니다. 수정은 하지 않았으므로 발견 항목을 해결됨으로 표시하지 않습니다.
