# 계획 확인 화면 — 화면 인계

| 항목 | 내용 |
|---|---|
| 작성·갱신 | 2026-10-03 · Claude(최상욱 작업) |
| 기준 | `role-manager` `1c48943` 위 `feat/web-manager-integration` |
| 상태 | **목업 시나리오 1~7의 화면·동작을 프론트에 모두 구현.** 미리보기는 예시 데이터로 전부 동작하고, 실제 경로는 지금 서버로 되는 것을 연결했다. 서버가 아직 없는 것은 화면에 그대로 있고 「준비 중」이라고 말한다(§4 연결 자리) |
| 미리보기 | `npm run dev` 뒤 `http://127.0.0.1:3100/preview/plan-check` — 「결과 바로 보기」로 시나리오 2~7 |

- 기준 목업: [계획 확인 시나리오](mockups/tripilot-plan-check-streaming.html)(개인 저장소 `2026-10-02_계획확인_스트리밍_대표목업.html`과 같은 파일, 머리말 한 줄만 다름) · [목업 안내](mockups/README.md#계획-확인-시나리오-목업)
- **분담**(2026-10-03 사용자 결정, 최종)
  - 「목업에 있는 화면들은 프론트에서 다 구현해 놓고, 서버에 연결할 API는 백엔드에서 작업해서 우리 화면에 연결한다.」
  - 프론트는 화면·동작과 데이터 계약(`model.ts`의 `PlanCheckView`, `plan-check.tsx`의 `PlanCheckActions`)을 둔다.
  - 지금 서버로 되는 것은 프론트가 연결했다. 나머지는 백엔드가 같은 자리(§4)에 연결한다.
  - ☆같은 날 앞선 판에서는 서버에 없는 기능을 화면에서 빼거나 꺼 두었고, 이 문서는 「시나리오 1~7 구현」이라고 실제보다 크게 적었다. 이번 판에서 바로잡았다.

계획 등록(`/trips/new`)에서 「계획 확인하기」를 누른 뒤의 흐름이 이 화면이다(실제 경로 `/intakes/[intakeId]`).
- **기존 접수 확인 화면**(`features/intake-review/`)이 남은 곳은 두 군데뿐이다.
  - 읽은 일정이 없어 「일정 짜 줘」가 필요한 접수
  - 결과 맨 아래의 「이전 확인 화면 열기」(원문 전체 보기 등 예비 경로)

## 1. 시나리오별 상태

| 시나리오(목업) | 화면 | 미리보기 | 실제 경로(지금 서버) |
|---|---|---|---|
| 1 계획 확인 진행 — 받았어요 → 원문 읽기 → 장소·운영시간 확인 → 정리 완료 | 구현 | 전부 | 읽기는 실서버 연결(SSE로 따라 읽음). 서버에 확인 단계가 없어 읽은 뒤 바로 결과 |
| 2 결과 보기 — 카드·이동 줄·핀·일차·시트 높이 | 구현 | 전부 | 카드·핀·일차·시트 연결. 이동 줄은 서버 응답에 없어 안 보임 |
| 3 자동 추천 — 카드의 「자동 추천」으로 1순위 후보로 바꿈 | 구현 | 전부 | **연결 자리** `autoRecommend` · `suggestion` — 지금은 「준비 중」 |
| 4 수정 화면 — 검색 위 막대 · 지금 일정/후보 A·B·C 카드 넘기기 · 지도 핀 · 사진 · 검색 결과 · 「이 장소로 바꾸기」 | 구현 | 전부 | 장소를 이름으로 바꾸기(`/edits` `place {name}`)·후보 이름(`chosen_from`)·「직접 고치기」 연결. **연결 자리** 후보의 거리·검사·사진(`candidates`), 장소 검색(`search`) |
| 5 잠금 — 고정하면 수정·자동 추천·삭제 막힘, 확인 필요 일정은 고정 불가 | 구현 | 전부 | **연결 자리** `lock` · `locked` — 지금은 「준비 중」 |
| 6 삭제 — 확인창 → 삭제 → 「되돌리기」 | 구현 | 전부 | 삭제 연결(`removed: true`). **연결 자리** `undo` — 지금은 확인창이 「되돌릴 수 없어요」라고 말함 |
| 7 전체 자동 추천 → 재검증 → 여행 등록 → 등록 완료 | 구현 | 전부 | 여행 등록 연결(`/confirm`). **연결 자리** `autoRecommendAll` · `recheck` · `dirty`. 서버가 저장마다 다시 확인하므로 지금은 확인 필요가 없으면 바로 「여행 등록」 |
| 배치 — 지도가 화면을 채우고 떠 있는 위 막대, 지도 위로 올리는 시트(반·전체·접힘) | 구현 | 전부 | 같음 |

## 2. 화면이 하는 일

**받은 순서대로, 화면 속도로 그린다**
- 화면은 `PlanCheckView` 스냅숏만 받는다.
- 앞 스냅숏과의 차이를 한 번에 하나씩(0.28초) 그린다. 순서: 읽기 시작 → 줄 → 날짜 → 확인 시작 → 하루 순서대로 장소·이동(나타남 → 검사 한 줄씩 → 판정) → 정리 완료 → 제목.
- 서버가 한꺼번에 보내도 나눠 보내도 같은 순서로 보인다(단위 시험). 「움직임 줄이기」 설정이면 바로 그린다.
- 바꾼 일정을 다시 확인할 때도 같다: 그 일정과 앞뒤 이동이 「확인 중」이 되고 검사 줄이 다시 채워진다.

**결과 화면(시나리오 2)**
- 카드 머리(제목 버튼)를 누르면 펼쳐진다. 한 번에 하나, 이동 줄도 같다.
- 카드를 고르면 지도에 그 날과 핀이 선택되고, 핀을 누르면 그 카드가 펼쳐진다.
- 일차 머리를 누르면 그 날 지도로 바뀐다. 손잡이는 시트를 중간 → 높게 → 낮게 돌린다.
- 시트 머리: 「장소 N곳 · 이동 M구간 확인 필요」 / 「고친 곳이 있어요 · 재검증해 주세요」 / 「고칠 곳이 없어요」 / 「재검증 중 · 2/4」 / 「등록 완료」.

**카드 도구(시나리오 3·5·6)**
- 카드 머리: 잠금 · 이름 · 판정(유지·조정·확인 필요, 다시 확인 중이면 「확인 중」·「재검증」) · 수정 · 삭제.
- 펼친 카드: 검사 줄, 「자동 추천」·「수정」, 그 아래 한 줄(「자동 추천은 1순위 ○○로 바로 바꿔요」 또는 잠금·준비 중 이유).
- **쓸 수 없는 단추도 남는다.** 누르면 이유를 알림으로 말한다(목업 개정 5). 예:
  - 「확인이 필요한 일정은 먼저 고쳐야 고정할 수 있어요」
  - 「고정한 일정이라 바꿀 수 없어요 · 잠금을 풀면 수정할 수 있어요」
  - 「바뀐 일정을 다시 확인하는 중이에요」, 「이미 등록한 여행이에요」
  - 연결 자리가 비어 있으면 「…은 준비 중이에요」
- 바꾸기·자동 추천·삭제·전체 자동 추천 뒤에는 시트 위에 알림이 뜨고, `undo`가 있으면 「되돌리기」가 붙는다.

**수정 화면(시나리오 4)** — 지도와 시트는 그대로, 내용만 바뀐다
- 위 막대가 「○○ 대신 찾을 장소」 검색창이 된다(뒤로 = 바꾸기 그만두기, Esc는 검색어 지우기 → 한 번 더 누르면 나가기).
- 시트: 「○○ 바꾸기」와 위치(「대체 후보 A · 2/4」), 옆으로 넘기는 카드(지금 일정 → 후보 A·B·C → 검색으로 고른 곳), 점, 「시트를 위로 올리면 ○○ 사진 6장 ↑」, 등록된 사진.
- 지도: 그날 다른 일정은 회색(누를 수 없음), 바꾸는 일정은 진하게, 후보는 A·B·C. 핀을 누르면 그 카드로, 카드를 넘기면 그 핀이 선택된다.
- 검색창에 쓰면 시트가 검색 결과(가까운 순)로 바뀐다. 고른 곳은 카드로 들어가 「이 장소로 바꾸기」를 누를 수 있다.
- 검색이 없는 서버에서는 「장소 검색은 준비 중이에요」와 「「○○」로 바꾸기」(서버가 그 이름으로 찾음)를 보인다.
- 맨 아래 「직접 고치기 · 이름·날짜·시각·장소 없음」(접어 둠): 이름·날짜·시각·「장소 없음」 수정. 화면이 먼저 막는 것은 이름 없음·끝이 시작보다 빠름·장소 이름 없음, 나머지는 서버 판단(거절이면 서버 문장, 입력 유지).

**삭제(시나리오 6)** — 휴대폰 화면 가운데 확인창
- 「○○ 일정을 삭제하시겠습니까?」, 일차·시각, 되돌릴 수 있는지.
- 처음 초점은 취소. Tab은 두 단추 안에서만 돌고, Esc·바깥 누름은 닫기만 한다.
- 삭제하면 앞뒤 일정 사이 이동을 다시 계산한다(미리보기). 실제 경로는 서버가 준 판으로 다시 그린다.

**하단 버튼(시나리오 7)**
- 왼쪽 「전체 자동 추천」에 확인할 수(장소+이동)를 붙인다. 고칠 것이 없으면 「고칠 곳이 없어요」.
- 오른쪽: 확인할 것이 남으면 「재검증」(꺼짐 — 「확인이 필요한 항목 N건이 남아 있어요 …」) → 고쳤으면(`dirty`) 「재검증」(켜짐, 누르면 「재검증 중…」) → 고칠 것이 없으면 「여행 등록」 → 등록하면 「✓ 등록 완료」(여행 보기 링크). 등록한 뒤에는 화면 조작이 닫힌다.
- 등록 거절은 서버 문장과 문제 목록을 보인다.

**공통**
- 처음 방문해 키가 막 발급됐으면 「내 여행 열쇠를 따로 보관해 주세요」를 맨 위에 보인다.
- 시작 화면과 같은 휴대폰 틀(`DeviceFrame`). 진행 막대는 `progressbar`, 상태·알림은 `status`, 삭제 확인창은 `alertdialog`, 쓸 수 없는 단추는 `aria-disabled`.
- 문구는 한/영. 색은 역할 변수만 써서 그린·화이트 테마를 따른다.

## 3. 파일

| 파일 | 내용 |
|---|---|
| `src/features/plan-check/model.ts` | 데이터 계약 — `PlanCheckView`(`dirty` · `rechecking` 포함) · `PlanItem`(`locked` · `info` · `suggestion` 포함) · `PlanCandidate` · `PlaceInfo` · `PlacePhoto`, 순서 규칙(`nextStep`), 진행률·개수·`needs` |
| `src/features/plan-check/plan-check.tsx` | 화면과 **연결 자리** `PlanCheckActions`(§4). 지도 위 막대·시트·카드 도구·알림 |
| `src/features/plan-check/place-change.tsx` | 수정 화면(카드 넘기기·사진·검색 결과) |
| `src/features/plan-check/result-parts.tsx` | 「직접 고치기」(`StopEditor`), 삭제 확인창, 여행 전체 문제, 하단 버튼(`ResultFooter`) |
| `src/features/plan-check/parts.tsx` | 검사 줄·판정 표시·「이유를 말하는 단추」(`Act`) |
| `src/features/plan-check/from-intake.ts` | 서버 접수 → 화면: `readingOf` · `resultOf` · `tripIssuesOf` · `candidatesOf`(`chosen_from`) |
| `src/features/plan-check/use-reveal.ts` | 스냅숏을 한 단계씩 그리는 훅 |
| `src/features/plan-check/fixtures.ts` · `preview-engine.ts` · `preview.tsx` · `src/app/preview/plan-check/page.tsx` | **미리보기 전용.** 목업의 예시 장소 18곳·사진 이름과 목업 스크립트의 규칙(후보 3곳·거리·운영시간·휴무·이동·전체 자동 추천·재검증)을 옮긴 예시 계산. 실제 경로는 쓰지 않는다. live 빌드에서 미리보기는 404 |
| `src/features/intake-review/intake-review.tsx` | 실제 경로. 새 화면에 서버 호출을 잇는다(§4) |
| `src/features/map/*` | 지도: `variant="fill"`(칸을 채움·안내줄 없음), 핀 글자·모양(`looks` — 회색·바꾸는 일정·후보 A·B·C). 세 제공자와 개념도가 같은 `pin.ts`를 쓴다 |

## 4. 연결 자리 — 백엔드가 잇는 곳

화면은 `PlanCheckActions`의 함수와 `PlanCheckView`의 칸만 본다. 함수가 없으면 단추는 남고 「준비 중」이라고 말하며, 칸이 비면 그 부분이 비어 보인다(지어내지 않음). 실제 경로의 연결은 `intake-review.tsx`의 `actions={…}`와 `from-intake.ts`다.

| 연결 자리 | 화면이 기대하는 것 | 지금 서버 | 상태 |
|---|---|---|---|
| 읽기 진행 | `readingOf` ← 접수 `stage` · `sources[].lines[]` · `items[].line`, 진행 SSE `GET …/events` | 있음 | **연결함** |
| 결과 항목·판정 | `resultOf` ← `items` · `fields.place.value` · `check.problems` · `needs_review` · `check.filled` · `check.title` | 있음 | **연결함** |
| 확인 단계(장소·운영시간) | `stage: "checking"` 동안 항목이 하나씩 채워짐 | 없음(`review`로 바로 감) | 협의 필요 |
| 운영시간·휴무일 검사 | `PlanItem.checks`에 `hours` · `closed` 줄 | 응답에 없음 | 협의 필요 |
| 이동 | `PlanCheckView.moves`(`PlanMove`: 출발·수단·요약·검사·판정) | 응답에 없음 | 협의 필요 |
| 장소 바꾸기 | `replace(id, {candidate} | {name})` | `/edits` `items[n].place {name}` — 서버가 이름으로 다시 찾음 | **연결함** |
| 대체 후보 | `candidates(id)` → `PlanCandidate[]`(이름·순위·거리·좌표·분류·주소·사진·이 장소의 검사) | 모호한 이름일 때 `evidence.chosen_from`(이름만) | **이름만 연결함** — 거리·검사·사진은 협의 필요 |
| 1순위 후보 이름 | `PlanItem.suggestion` | 없음 | 협의 필요 |
| 장소 검색 | `search(id, 검색어)` → `PlanCandidate[]` | 없음 | 협의 필요(지금은 「이름으로 바꾸기」로 대신함) |
| 장소 정보·사진 | `PlanItem.info` · `PlanCandidate.info`(`category` · `address` · `photos[{caption, url}]`) | 없음 | 협의 필요 |
| 자동 추천(한 곳) | `autoRecommend(id)` | 없음 | 협의 필요 |
| 전체 자동 추천 | `autoRecommendAll()` → `{changes: string[], kept: number}` | 없음(적용은 `/edits`로 가능) | 협의 필요 |
| 잠금 | `lock(id, locked)`, `PlanItem.locked` | 수정 칸에 없음 | 협의 필요 |
| 되돌리기 | `undo()` | `removed: false` 안 받음 · 판 되돌리기 없음 | 협의 필요 |
| 재검증 | `recheck()`, `PlanCheckView.dirty` · `rechecking` | 없음 — 저장마다 서버가 다시 확인(`dirty` 늘 거짓) | 필요한지 협의 |
| 삭제 | `remove(id)` | `/edits` `items[n].removed: true` | **연결함** |
| 직접 고치기(이름·날짜·시각·장소 없음) | `edit(id, draft)` | `/edits` `title` · `date` · `starts_at` · `ends_at` · `place {none:true}` | **연결함** |
| 여행 첫날·인원 | `editTrip(field, value)` | `/edits` `trip.first_day` · `trip.party_size` | **연결함** |
| 여행 등록 | `registration` | `/confirm`, `check.ready` | **연결함** |

목업의 「백엔드에 필요한 것」 표와 「서버로 보낼 값」 예시가 협의 필요 칸의 제안이다. 연결 순서는 백엔드가 정한다. 화면 쪽은 함수를 넘기고 칸을 채우면 바로 보인다.

## 5. CSS

- 클래스는 `plan-check.module.css` 한 파일, 색은 역할 변수만 쓴다(`tokens.test.ts`가 검사).
- 배치: `.checking[data-sheet][data-changing]` › `.map`(위 막대 아래부터 시트 뒤까지) · `.unlocated` · `.bar`(떠 있음) · `.sheet`(`--sheet-h`: 반 `min(440px, 60%)` · 접힘 150px · 전체 `100% - 64px`) · `.toast`(시트 위)
- 결과: `.sheetHead` · `.sheetBody` › `.timeline` › `.entry[data-type][data-verdict][data-selected]` › `.card[data-locked]` › `.cardTop` · `.checks` · `.cardActions` · `.cardNote`, 하단 `.footer` › `.footButton[data-primary|data-done]`
- 수정 화면: `.searchField` · `.change` › `.changeHead` · `.carousel` › `.changeCard[data-current|data-active]` · `.dots` · `.hint` · `.photos` › `.photoGrid` › `.photo[data-example]` · `.results` · `.details` › `.editor`

| 속성 | 값 |
|---|---|
| `data-stage` | received · reading · checking · done |
| `data-sheet` | half · full · peek |
| `data-verdict` | keep · adjusted · review · checking |
| `data-result` | ok · filled · warn · bad · unknown · pending |

**남은 마감**
- 지도 위 경로 선: 지도 어댑터에 선 그리기가 없다(핀 글자·모양은 이번에 더함).
- 지도는 위 막대 아래(60px)부터 그린다. 목업은 막대 뒤까지 지도가 보인다. 핀이 막대에 가려 누를 수 없어서 이렇게 했다.
- 사진 자리의 예시 그림은 단색 무늬다(목업은 장소 종류별 그림).

## 6. 시험

| 시험 | 내용 |
|---|---|
| 단위 `model.test.ts` · `from-intake.test.ts` · `preview-engine.test.ts` | 그리는 순서·진행률·개수, 읽기·결과·후보 이름 변환, 예시 계산(후보 3곳·검색·바꾸기·휴무·전체 자동 추천·삭제·다시 확인) |
| demo 브라우저 `tests/e2e/plan-check.spec.ts`(15개) | 시나리오 1~7을 차례로: 진행·움직임 줄이기·결과 바로 보기·뒤로·화면 폭(바꾸기 화면 포함), 카드·핀·일차·시트·이동 줄, 자동 추천 → 되돌리기, 수정 화면(후보 넘기기·핀·사진·검색 → 바꾸기), 직접 고치기, 잠금 이유, 삭제 확인창 → 되돌리기, 꺼진 재검증 이유 → 전체 자동 추천 → 재검증 → 등록 완료 |
| live 빌드 `tests/live/`(테스트용 모방 서버) | 실제 경로의 읽기·결과·수정·삭제·등록·SSE·웹훅 |
| 실서버(로컬) | 작업 리포트 |

실행 결과와 수치는 작업 리포트에 있다: [1단계](../../../wiki/records/reports/2026-10-03_0140_계획확인화면_1단계_진행화면.md) · [읽기 연결](../../../wiki/records/reports/2026-10-03_0200_계획확인화면_읽기_실서버연결.md) · [2단계](../../../wiki/records/reports/2026-10-03_0229_계획확인화면_2단계_결과보기.md) · [3~5단계](../../../wiki/records/reports/2026-10-03_0249_계획확인화면_3to5단계_수정삭제등록.md) · [목업 전체 구현](../../../wiki/records/reports/2026-10-03_0501_계획확인화면_목업전체구현.md).
