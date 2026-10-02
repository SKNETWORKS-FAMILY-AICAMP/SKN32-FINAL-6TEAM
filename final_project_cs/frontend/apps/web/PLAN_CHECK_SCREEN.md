# 계획 확인 화면 — 화면 인계

| 항목 | 내용 |
|---|---|
| 작성·갱신 | 2026-10-03 · Claude(최상욱 작업) |
| 기준 | `role-manager` `1c48943` 위 `feat/web-manager-integration` |
| 상태 | **목업 시나리오 1~7 화면 구현, 지금 서버로 되는 것은 실서버 연결** |
| 미연결 | 서버 API가 없는 기능(확인 단계, 운영시간·휴무일 검사, 이동, 자동 추천, 잠금, 후보·사진, 삭제 되돌리기)은 「준비 중」으로 꺼 두거나 예시 데이터 미리보기에서만 보인다 |
| 미리보기 | `npm run dev` 뒤 `http://127.0.0.1:3100/preview/plan-check` |

- 기준 목업: [계획 확인 시나리오](mockups/tripilot-plan-check-streaming.html) · [목업 안내](mockups/README.md#계획-확인-시나리오-목업)
- **분담**(2026-10-03 사용자 결정)
  - 화면 구조와 최소 배치 CSS, 지금 서버로 되는 부분의 연결은 Claude가 맡는다.
  - 서버에 없는 기능은 백엔드와 협의한다.
  - 테마·CSS 마감은 Codex가 맡는다. 다만 그린·화이트 테마와 메뉴 전환은 같은 날 사용자 지시로 Claude가 했다([개발 기준](DEVELOPMENT.md#2026-10-03--그린화이트-테마)).
  - 같은 날 「연결은 백엔드」에서 「연결할 수 있는 것은 지금 연결」로 바뀌었다.

계획 등록(`/trips/new`)에서 「계획 확인하기」를 누른 뒤의 흐름이 이 화면이다. 실제 경로 `/intakes/[intakeId]`는 다음과 같이 움직인다.
- **읽는 중:** 서버의 원문 줄을 차례로 그린다.
- **읽기가 끝나면:** 마지막 줄까지 그리고 잠깐 머문 뒤 결과 화면(지도 + 목록)으로 바뀐다.
- **결과 화면에서 하는 일:** 카드 수정·삭제, 여행 첫날·인원 입력, 여행 등록.
- **기존 접수 확인 화면**(`features/intake-review/`)이 남아 있는 곳은 두 군데다. 이 둘 외에는 쓰지 않는다.
  - 읽은 일정이 없어 「일정 짜 줘」가 필요한 접수
  - 결과 화면 맨 아래의 「이전 확인 화면 열기」 — 원문 전체 보기, 지도에서 장소 찾기 같은 기존 기능용 예비 경로

## 1. 단계별 범위

| 단계 | 목업 | 상태 |
|---|---|---|
| 1 진행 화면 | 시나리오 1 — 받았어요 → 원문 읽기 → 장소·운영시간·이동 확인 → 정리 완료 | 구현 · 실서버 연결(읽기). 확인 단계는 서버에 없어 미리보기만 |
| 2 결과 보기 | 시나리오 2 — 카드 펼침, 카드↔지도 핀, 일차 전환, 목록 높이, 이동 줄 | 구현 · 실서버 연결(이동은 미리보기만) |
| 3 카드 동작 | 시나리오 3·5·6 — 자동 추천, 잠금, 삭제 확인창 → 삭제 | 삭제 구현 · 실서버 연결. 자동 추천·잠금은 「준비 중」. 삭제 뒤 되돌리기는 서버가 지원하지 않아 넣지 않음(확인창에서 미리 알림) |
| 4 하단 버튼 줄 | 시나리오 7 — 전체 자동 추천 → 재검증 → 여행 등록 | 여행 등록 구현 · 실서버 연결. 서버가 저장마다 다시 확인하므로 별도 재검증 단계 없음. 전체 자동 추천은 「준비 중」 |
| 5 수정 화면 | 시나리오 4 — 장소 검색, 후보 카드, 사진 | 장소 이름(서버가 다시 찾음)·장소 없음·이름·날짜·시각 수정 구현 · 실서버 연결. 후보·사진은 「준비 중」 |

## 2. 화면이 하는 일

**받은 순서대로, 화면 속도로 그린다**
- 화면은 `PlanCheckView` 스냅숏만 받는다.
- 새 스냅숏이 오면 앞 스냅숏과의 차이를 한 번에 하나씩(0.28초 간격) 그린다. 순서는 이렇다: 읽기 시작 → 줄마다 읽음 → 날짜 → 확인 시작 → 하루 일정 순서대로 장소·이동(나타남 → 검사 한 줄씩 → 판정) → 완료 → 제목.
- 서버가 한꺼번에 보내도 나눠 보내도 같은 순서로 보인다(단위 시험).
- 처음 받은 스냅숏은 그대로 그린다(새로고침·늦게 연 경우). 「움직임 줄이기」 설정이면 바로 그린다.
- 장소가 빠지거나 앞 단계로 돌아가는 것처럼 차례로 그릴 수 없는 변화는 바로 바꾼다.

**읽기(`from-intake.ts`의 `readingOf`)**
- 서버 단계를 옮긴다: `received` → 받았어요, `transcribing`·`reading` → 일정 읽기.
- 소스를 이어 줄 번호를 매기고, 줄마다 읽었는지와 그 줄이 된 일정(제목·일차·시각)을 보인다. 서버가 정하지 않은 일차·시각은 비워 둔다.
- 화면 갱신은 1.5초 조회다.

**결과(`resultOf`) — 서버가 말한 것만 보인다**
- 기존 확인 화면의 `rows`·`placeOf`·`draftOf`·`statusOf`로 서버 데이터를 같은 기준으로 읽는다.
- 장소: 찾은 장소(✓), 못 찾은 이유(✕, `check.problems`), 확인 메모(!, `needs_review`)
- 시간: 서버가 채운 시각(✎, `check.filled`), 문제·확인 메모
- 판정: 문제나 확인 표시가 있으면 확인 필요. 서버가 시각을 채웠거나 고객이 고쳤으면 조정. 그 밖에는 유지.
- 서버가 해·날짜를 짐작만 한 것(`year_filled`·`day_offset`)은 확인 필요로 세지 않는다.
- 운영시간·휴무일·이동은 응답에 없어 보이지 않는다.
- 여행 전체 문제(`check.problems` 중 항목이 아닌 것)는 목록 맨 위 「여행 전체에서 확인할 것」에 보인다. 여행 첫날(`no_date`)과 인원(`party_size_out_of_range`)은 그 자리에서 답한다.

**결과 화면 조작**
- 카드는 머리(제목 안의 버튼, `aria-expanded`)를 누르면 펼쳐진다. 한 번에 하나만 펼쳐지고, 이동 줄도 같다.
- 카드를 고르면 지도에 그 날과 핀이 선택된다. 핀을 누르면 그 카드가 펼쳐지고 보이는 자리로 온다.
- 일차 머리를 누르면 그 날 지도로 바뀐다.
- 손잡이로 목록 높이를 중간 → 높게 → 낮게 순서로 바꾼다.
- 카드 머리에는 고정(「준비 중」으로 꺼짐)·수정·삭제가 있고, 펼친 카드에는 자동 추천(「준비 중」)·수정이 있다.

**수정 화면** — 목록 자리에 연다
- 입력: 장소 이름, 「장소 없음」, 일정 이름, 날짜, 시작, 끝
- 화면이 먼저 막는 것: 이름 없음, 끝이 시작보다 빠름, 장소 이름 없음(「장소 없음」이 아닐 때)
- 그 밖의 판단은 서버 몫이다. 거절(예: `place_not_found`)이면 서버 문장을 보이고 입력을 그대로 둔다.
- 저장하면 서버가 이름으로 장소를 다시 찾고 일정을 다시 확인한다. 그다음 「저장했어요」 알림이 뜬다.
- Esc·취소로 닫으면 그 카드의 수정 단추로 초점이 돌아온다.

**삭제** — 휴대폰 화면 가운데 확인창
- 「○○ 일정을 삭제하시겠습니까?」와 일차·시각, 「삭제한 일정은 되돌릴 수 없어요」를 보인다.
- 처음 초점은 취소에 있다. Tab은 두 단추 안에서만 돌고, Esc나 바깥 누름은 닫기만 한다.
- 삭제하면 `removed: true`를 보내고 알림이 뜬다. 그 장소에 이어진 이동도 함께 빠진다.

**하단 버튼 줄**
- 「전체 자동 추천」: 확인 필요 수를 보이며 「준비 중」으로 꺼져 있다.
- 「여행 등록」: 서버가 등록할 수 있다고 하면(`check.ready`) 켜진다. 아니면 「확인 필요한 것을 고치면 등록할 수 있어요. 고칠 때마다 서버가 다시 확인해요.」라고 보인다.
- 거절이면 서버 문장과 문제 목록을 보인다. 이미 등록한 접수는 「여행 보기」가 나온다.

**공통**
- 처음 방문해 키가 막 발급됐으면 「내 여행 열쇠를 따로 보관해 주세요」를 화면 맨 위에 보인다.
- 틀은 시작 화면과 같은 휴대폰 틀(`DeviceFrame`)이다.
- 진행 막대는 `progressbar`이고, 상태 문장과 알림은 `status`, 삭제 확인창은 `alertdialog`다.
- 문구는 한/영 두 가지로 쓴다. 목업의 「끝나면 알림으로 알려 드릴게요」는 실제 알림 기능이 없어서 쓰지 않았다.

## 3. 파일

| 파일 | 내용 |
|---|---|
| `src/features/plan-check/model.ts` | 데이터 계약(`PlanCheckView` · `PlanItem` · `ItemDraft` · `TripIssue`), 순서 규칙(`nextStep`), 진행률·개수, 수정 전 검사(`draftProblem`) |
| `src/features/plan-check/from-intake.ts` | 서버 접수 응답 → 화면 데이터: `readingOf` · `resultOf` · `tripIssuesOf` |
| `src/features/plan-check/use-reveal.ts` | 스냅숏을 한 단계씩 그리는 훅 |
| `src/features/plan-check/plan-check.tsx` | 화면 `<PlanCheck view onBack onCaughtUp? notice? actions? registration? tripIssues? onOpenPrevious? />`. `actions`에서 빠진 동작은 「준비 중」으로 보인다 |
| `src/features/plan-check/result-parts.tsx` | 수정 화면(`StopEditor`), 삭제 확인창(`DeleteDialog`), 여행 전체 문제(`TripIssues`), 하단 버튼 줄(`ResultFooter`) |
| `src/features/plan-check/plan-check.module.css` | 배치 CSS. 색은 공통 변수만 쓴다(직접 적은 색 0건) |
| `src/features/plan-check/fixtures.ts` · `preview.tsx` · `preview.module.css` · `src/app/preview/plan-check/page.tsx` | 미리보기 전용. 목업 예시 데이터를 쓰고, 수정·삭제·등록은 그 페이지 안에서만 바뀐다(장소는 찾지 않음). live 빌드에서는 404 |
| `src/features/intake-review/intake-review.tsx` · `src/app/intakes/[intakeId]/page.tsx` | 실제 경로. 새 화면에 서버 호출을 잇는다 — 수정 `editsFor` → `/edits`, 삭제 `removed: true`, 여행 첫날·인원 `trip.*`, 등록 `/confirm`. 「일정 짜 줘」·이전 화면은 기존 확인 화면 |
| `src/styles/tokens.css` | 색 역할 변수 — 그린(기본)·화이트 두 테마에 같은 이름. 이 화면이 더한 역할은 16개 |
| 시험 | `model.test.ts` · `from-intake.test.ts` · `tests/e2e/plan-check.spec.ts` · `tests/live/flow.spec.ts` · `tests/live/intake-review.spec.ts` · `tests/live/preview.spec.ts` · `tests/live/stub-server.mjs`(읽는 중 원문 줄, `intake: "blocked"`, `edits: "not_found"`) · `tests/live/helpers.ts`(`openEditor`) · `tests/real/real-server.spec.ts`(새 화면 흐름) |

## 4. 서버 연결 상태

| 화면 기능 | 서버 | 상태 |
|---|---|---|
| 읽기 진행(단계·줄·읽음·찾은 일정) | 접수 조회 `stage` · `sources[].lines[]` · `items[].line` | **연결함**(1.5초 조회) |
| 진행 알림(SSE) | `GET …/events`(`role-manager` `c361394`) | 미연결 — 조회로 충분해 이번에 붙이지 않음 |
| 확인 단계(장소·운영시간) | 서버에 없음(`review`로 바로 감) | **협의 필요** |
| 결과 — 항목·좌표·제목·장소/시간 문제·판정 | 접수 조회 `items` · `fields.place.value` · `check.problems` · `needs_review` · `check.filled` · `check.title` | **연결함** |
| 운영시간·휴무일 검사, 이동 | 응답에 없음 | **협의 필요** |
| 수정(장소 이름·장소 없음·이름·날짜·시각) | `POST …/edits` — `items[n].place` `{name}`/`{none:true}` · `title` · `date` · `starts_at` · `ends_at`. 못 찾으면 422 `place_not_found`, 낡은 판 409 `stale_revision`(화면이 다시 읽음) | **연결함** |
| 삭제 | `POST …/edits` `items[n].removed: true` | **연결함** |
| 삭제 되돌리기 | 서버가 `removed: false`를 받지 않음(「빼려면 true」) · 판 되돌리기 경로 없음 | **협의 필요** |
| 여행 첫날·인원 | `POST …/edits` `trip.first_day` · `trip.party_size`(1~4) | **연결함** |
| 여행 등록 | `POST …/confirm`(설문 포함), `check.ready` | **연결함** |
| 자동 추천(한 곳·전체), 후보 목록·사진 | 응답·경로 없음(서버는 이름이 모호하면 하나를 고르고 `chosen_from`에만 남김) | **협의 필요** |
| 잠금(반드시 포함) | 수정 칸에 없음(여행에는 `protected_reason: booked`가 있음) | **협의 필요** |
| 재검증(저장 없이 판정만) | 없음 — 지금은 저장할 때마다 서버가 다시 확인 | 필요한지 협의 |

목업의 「진행 이벤트 예시」와 「백엔드에 필요한 것」 표가 협의 필요 칸의 제안이다.

## 5. Codex CSS 인계

**클래스와 구조**
- 클래스는 `plan-check.module.css` 한 파일에 있다.
- 읽기: `.screen[data-stage]` › `.reading` › `.head` · `.doc` › `.line[data-state]`
- 확인·결과: `.checking[data-sheet]` › `.bar` · `.map` · `.sheet`
  - `.sheet` › `.handle` · `.sheetHead` · `.sheetBody` › `.tripIssues` · `.timeline` › `.entry[data-type][data-verdict][data-selected]` › `.card` › `.cardTop` · `.checks` · `.cardActions`
  - `.sheet` › `.footer`
- 수정 화면 `.editor`, 삭제 확인창 `.scrim` › `.dialog`, 알림 `.toast[data-shown]`

**상태 값(계약)**

| 속성 | 값 |
|---|---|
| `data-stage` | received · reading · checking · done |
| `data-sheet` | half · full · peek |
| `data-verdict` | keep · adjusted · review · checking |
| `data-result` | ok · filled · warn · bad · unknown · pending |

구조나 클래스를 바꿔야 하면 먼저 공유받는다.

**알려진 CSS 과제**
- 공통 지도의 최소 높이(휴대폰 390px)가 지도 칸보다 커서 지도 아래 안내줄이 잘린다. 화면은 「위치 미정」을 따로 보인다.
- 목업처럼 지도 위에 올리는 시트, 그림자, 떠 있는 위 막대, 핀 상태색·이동 경로 선은 넣지 않았다. 핀 색과 경로 선은 지도 어댑터에 없어 구조 변경이 필요하다.
- 320px에서는 하단 버튼 줄 때문에 목록이 짧아 스크롤이 필요하다.
- 미리보기 조작 막대의 모양. (뉴트럴(화이트) 테마 값과 메뉴 전환은 2026-10-03에 끝났다.)

## 6. 시험 (2026-10-03)

| 시험 | 내용 |
|---|---|
| 단위 `model.test.ts`·`from-intake.test.ts` | 그리는 순서·진행률·개수, 읽기·결과 변환(판정·서버 문장·짐작한 값·고객 값) |
| demo 브라우저 `tests/e2e/plan-check.spec.ts`(12개) | 미리보기 흐름, 움직임 줄이기, 결과 바로 보기, 뒤로, 화면 폭, 카드·핀, 일차·손잡이, 이동 줄, 수정 화면 검사·취소 초점, 「장소 없음」 저장, 삭제 확인창 Tab·바깥 누름·320px, 하단 「여행 등록」 |
| live 빌드 `tests/live/`(테스트용 모방 서버) | 읽는 중 → 결과, 결과 장소·판정, 막힌 등록, 수정 → `/edits`, 장소 못 찾음(422) 입력 유지, 삭제 확인창 → `removed`, 「준비 중」 단추, 여행 첫날 입력 → `trip.first_day`, 기존 화면 시험(「이전 확인 화면 열기」 경유), 미리보기 404 |
| 실서버(로컬) | 읽기 진행 → 결과(지도 핀·서버 문장). 「광장시장」 장소를 「창덕궁」으로 고치니 서버가 「창덕궁과 후원 [유네스코 세계유산]」으로 찾음. 「북촌한옥마을 산책」 삭제 확인창 → 삭제 → 카드 2개, 「여행 등록」 켜짐. `/edits` 200 ×2. 등록은 누르지 않음 |

실행 결과와 수치는 작업 리포트에 있다: [1단계](../../../wiki/records/reports/2026-10-03_0140_계획확인화면_1단계_진행화면.md) · [읽기 연결](../../../wiki/records/reports/2026-10-03_0200_계획확인화면_읽기_실서버연결.md) · [2단계](../../../wiki/records/reports/2026-10-03_0229_계획확인화면_2단계_결과보기.md) · [3~5단계](../../../wiki/records/reports/2026-10-03_0249_계획확인화면_3to5단계_수정삭제등록.md).
