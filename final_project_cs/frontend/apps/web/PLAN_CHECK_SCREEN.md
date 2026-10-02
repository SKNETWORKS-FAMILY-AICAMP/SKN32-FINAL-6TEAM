# 계획 확인 화면 — 화면 인계

| 항목 | 내용 |
|---|---|
| 작성 | 2026-10-03 · Claude(최상욱 작업) |
| 기준 | `role-manager` `1c48943` 위 `feat/web-manager-integration` 로컬 변경 |
| 상태 | **1단계(진행 화면) 화면만 구현.** 서버에는 연결하지 않았다 |

**역할 분담** — 2026-10-03 사용자 결정

| 담당 | 맡는 일 |
|---|---|
| Claude | 화면 구조와 최소 배치 CSS를 만들어 넘긴다 |
| 백엔드 | 서버 연결 |
| Codex | 테마·CSS 마감 |

**참고**

| 항목 | 위치 |
|---|---|
| 기준 목업 | [계획 확인 시나리오](mockups/tripilot-plan-check-streaming.html) · [목업 안내](mockups/README.md#계획-확인-시나리오-목업) |
| 미리보기 | `npm run dev` 뒤 `http://127.0.0.1:3100/preview/plan-check` |

미리보기는 목업의 예시 데이터를 시간에 맞춰 흘려 보내는 페이지이며, **서버에 연결돼 있지 않다**. 개발 서버와 demo 빌드에서만 열리고, live 빌드에서는 404다.

계획 등록(`/trips/new`)에서 「계획 확인하기」를 누른 뒤의 흐름이 이 목업으로 바뀐다. 지금 연결돼 있는 `/intakes/[intakeId]`(`features/intake-review/`)는 **건드리지 않았다.** 이 화면은 백엔드가 그 자리에 연결할 때까지 미리보기에서만 보인다.

## 1. 단계별 범위

| 단계 | 목업 | 상태 |
|---|---|---|
| **1 진행 화면** | 시나리오 1 — ① 받았어요 → ② 원문을 한 줄씩 읽음 → ③ 지도 + 목록에서 장소·운영시간·이동 확인 → ④ 카드가 접히고 여행 제목 | **화면 구현 완료** |
| 2 결과 보기 | 시나리오 2 — 카드 펼침, 카드↔지도 핀 선택, 일차 전환, 목록 높이(손잡이) | 다음 |
| 3 카드 동작 | 시나리오 3·5·6 — 자동 추천, 잠금, 삭제 확인창·되돌리기 | 예정 |
| 4 하단 버튼 줄 | 시나리오 7 — 전체 자동 추천 → 재검증 → 여행 등록 | 예정 |
| 5 수정 화면 | 시나리오 4 — 장소 검색, 후보 카드, 사진 | 예정 |

## 2. 1단계 — 화면이 하는 일

- **받은 순서대로, 화면 속도로 그린다.**
  - 화면은 `PlanCheckView` 스냅숏만 받는다.
  - 새 스냅숏이 오면 앞 스냅숏과의 차이를 한 번에 하나씩(0.28초 간격) 그린다. 순서는 이렇다: 읽기 시작 → 줄마다 읽음 → 날짜 → 확인 시작 → 하루 일정 순서대로 장소·이동(나타남 → 검사 한 줄씩 → 판정) → 완료 → 제목.
  - 서버가 한꺼번에 보내도, 여러 번 나눠 보내도 같은 순서로 보인다. 이것은 단위 시험으로 확인했다.
- **처음 받은 스냅숏은 그대로 그린다.** 새로고침하거나 늦게 연 경우에는 지금 상태부터 보이고, 다시 재생하지 않는다.
- **「움직임 줄이기」 설정이면 차례로 그리지 않고 바로 그린다.**
- **그릴 수 없는 변화는 바로 바꾼다.** 장소가 빠졌거나 앞 단계로 돌아간 경우가 그렇다.
- **진행 막대와 숫자가 전체를 미리 안다.**
  - 장소 수는 읽은 줄에서 찾은 일정 수로 센다.
  - 이동 수는 하루 일정 수에서 1을 빼서 더한다.
  - 그래서 「장소 1/4 · 이동 0/2」처럼 보인다.
- **완료 뒤 표시**
  - 목록 머리에 확인할 것을 센다(「장소 1곳 · 이동 1구간 확인 필요」).
  - 카드마다 판정을 붙인다(유지 · 조정 · 확인 필요).
  - 좌표가 없는 장소는 지도 위에 「위치 미정 · ○○」으로 보인다.
- **지도는 기존 `TripMap`을 그대로 쓴다.** 제공자별 전환과 좌표 없는 일정 안내가 그 안에 있다.
  - 확인 중에는 확인하는 날의 지도를 보인다.
  - 끝나면 1일차로 돌아온다.
- **화면 낭독기**
  - 진행 막대는 `progressbar`이며 값과 단계 이름을 읽는다.
  - 단계가 바뀌면 상태 문장을 읽는다.
  - 검사 결과 기호(✓ ✎ ! ✕ –)에는 글자 설명을 붙였다.
- **문구는 한/영 두 가지로 쓴다.** 목업의 「끝나면 알림으로 알려 드릴게요」는 실제 알림 기능이 없어서 쓰지 않았다. 대신 기존 화면 문구 「이 화면을 열어 두면 끝나는 대로 보여 드려요」를 썼다.

## 3. 파일

| 파일 | 내용 |
|---|---|
| `src/features/plan-check/model.ts` | **데이터 계약**(`PlanCheckView` 등)과 순서 규칙(`nextStep`), 진행률·개수(`progress` · `expected` · `tally`) |
| `src/features/plan-check/use-reveal.ts` | 스냅숏을 한 단계씩 그리는 훅. 「움직임 줄이기」를 따른다 |
| `src/features/plan-check/plan-check.tsx` | 화면 `<PlanCheck view onBack />` |
| `src/features/plan-check/plan-check.module.css` | 배치 CSS. 색은 공통 변수만 쓴다 |
| `src/features/plan-check/fixtures.ts` · `preview.tsx` · `preview.module.css` | 미리보기 전용 — 목업 예시 데이터와 재생기 |
| `src/app/preview/plan-check/page.tsx` | 미리보기 주소. live 빌드에서는 404 |
| `src/styles/tokens.css` | 이 화면이 쓰는 색 역할 변수 16개 추가(그린 값만) |
| `src/features/plan-check/model.test.ts` · `tests/e2e/plan-check.spec.ts` · `tests/live/preview.spec.ts` | 시험 |

## 4. 백엔드 연결 안내

연결은 `/intakes/[intakeId]` 페이지에서 서버 응답을 `PlanCheckView`로 바꿔 `<PlanCheck view={…} onBack={…} />`에 넘기면 된다. 화면은 서버를 부르지 않는다. 화면 속도와 애니메이션은 화면이 맡으므로 백엔드는 **순서와 내용만** 맞추면 된다(목업 「애니메이션 재생 방식」과 같다).

- 처음 열 때: 접수 조회(`GET /v1/web/trip-intakes/{id}`) 결과로 한 번 그린다.
- 그 뒤: 진행 알림(`GET …/events`, `role-manager` `c361394`)이나 재조회 결과로 새 스냅숏을 넘긴다.

| 화면 칸 | 지금 서버에서 가져올 곳 | 상태 |
|---|---|---|
| `stage` received · reading | 접수 `stage` — `received` → received, `transcribing`·`reading` → reading | 지금 계약 |
| `stage` checking | 장소·운영시간 확인 단계가 서버에 없다(`review`로 바로 감) | **협의 필요** |
| `stage` done | `status: review`(읽기 끝) — checking 없이 바로 done으로 둘 수 있다 | 지금 계약 |
| `lines[]` | `sources[].lines[]`의 `no` · `text` · `read` | 지금 계약 |
| `lines[].found` | 줄 번호가 같은 `sources[].items[]`(`line`)의 일차·`starts_at`·`title`. 날짜 줄(`kind: date`)은 따로 주는 칸이 없다 | 일부 협의 |
| `items[]` id · day · startsAt · title | `sources[].items[]`의 `index`(id는 `source_id:index` 권장) · `day` · `fields.starts_at` · `fields.title` | 지금 계약 |
| `items[].coordinates` | `fields.place.value`의 `latitude` · `longitude`(찾은 장소만) | 지금 계약 |
| `items[].checks` (장소·시간·운영시간·휴무일 + 한 줄 문구) | 지금은 등록을 막는 문제(`check.problems`)와 `needs_review`만 있다 | **협의 필요** |
| `items[].verdict` | `needs_review`면 review, 서버가 채운 값(`check.filled`)이 있으면 adjusted, 아니면 keep으로 임시 대응 가능 | 협의 권장 |
| `moves[]` (수단 · 요약 · 출발 · 검사) | 응답에 없다 | **협의 필요** |
| `days[]` | 항목의 `date` / `trip.first_day` | 지금 계약 |
| `title` | `check.title` | 지금 계약 |

목업의 「진행 이벤트 예시」(`stage` · `line` · `item` · `check` · `move` · `done`)를 쓰면 위 칸이 그대로 채워진다. 이벤트 이름은 작성자 제안이다.

## 5. Codex CSS 인계

- **클래스:** `plan-check.module.css` 한 파일이다.
- **구조:** `.screen[data-stage]` 안에 두 갈래가 있다.
  - 읽기: `.reading` › `.head` · `.doc` › `.line[data-state]`
  - 확인·결과: `.checking` › `.bar` · `.map` · `.sheet` › `.timeline` › `.entry[data-type][data-verdict]` › `.card` · `.checks` › `.check[data-result]` / `.move`
- **진행 막대:** `.progress[data-size]` › `.steps li[data-state]`
- **상태 이름:** `data-*` 속성 값이 계약이다. 아래 값을 쓴다.

| 속성 | 값 |
|---|---|
| `data-stage` | received · reading · checking · done |
| `data-state` | read · current · waiting / done |
| `data-verdict` | keep · adjusted · review · checking |
| `data-result` | ok · filled · warn · bad · unknown · pending |

- **구조나 클래스를 바꿔야 하면 먼저 공유받는다.**
- **알려진 CSS 과제**
  - 공통 지도(`features/map/map.module.css`)의 최소 높이(휴대폰 390px)가 이 화면의 지도 칸보다 크다. 그래서 지도 아래 안내줄이 잘린다. 화면은 「위치 미정」을 따로 보여 정보는 빠지지 않는다. 지도 칸 크기 맞춤과 겹친 시트(목업처럼 지도 위에 올리는 방식)는 마감 몫이다.
  - 목업의 그림자·떠 있는 위 막대·핀 색(상태별)·이동 경로 선은 넣지 않았다. 핀 색과 경로 선은 지도 어댑터에 없는 기능이라 구조 변경이 필요하다.
  - 뉴트럴 테마 값과 메뉴 전환, 미리보기 조작 막대(`preview.module.css`)의 모양.

## 6. 시험 (2026-10-03)

| 시험 | 결과 |
|---|---|
| 단위(`model.test.ts`) | 6개 — 하루 순서, 받음→완료의 전체 순서·단계 수, 한꺼번에/나눠 받아도 같은 순서, 되돌림·삭제는 바로 바꿈, 진행률이 뒤로 가지 않음, 개수 |
| demo 브라우저(`tests/e2e/plan-check.spec.ts`) | 5개 — 전체 흐름, 움직임 줄이기, 결과 바로 보기·처음부터, 뒤로, PC·375·320px 가로 넘침 없음 |
| live 빌드(`tests/live/preview.spec.ts`) | 미리보기 주소 404 |

실행 결과와 수치는 [작업 리포트](../../../wiki/records/reports/2026-10-03_0140_계획확인화면_1단계_진행화면.md)에 있다. 실제 서버 연결 시험은 하지 않았다. 연결은 백엔드 몫이다.
