# 여행 취향 설문 · 백엔드 `constraints.survey` 대응

작성일: 2026-09-28 · 상태: 백엔드 설문 계약에 맞춤(TeamFlow `ST4F-156`). 같은 날 앞선 판(`ST4F-155`)의 프론트 자체 형식과 온보딩 끝 별도 전송은 없앴다.

**계약의 정본은 백엔드다.** `final_project_cs/app/modules/travel_ops/survey.py`의 `TripSurvey`(판 `2026-09-24.v1`), 결정 `wiki/decisions/D-020-trip-survey-and-ask-first.md`, 계약 문서 `final_project_cs/wiki/external/rest-endpoints.md` 「`constraints.survey`」. 이 문서는 웹 화면의 답이 그 칸으로 어떻게 가는지만 적는다. 프론트의 Zod 거울은 [`src/features/onboarding/payload.ts`](src/features/onboarding/payload.ts)의 `tripSurveySchema`이고, 데모가 서버처럼 거절하게 하려고 둔다. 백엔드가 바뀌면 이쪽을 따라 고친다.

## 1. 언제 보내나

설문만 받는 API는 없다. 백엔드는 설문을 **여행 등록 요청의 `constraints.survey`**로 받고, 모든 등록 경로가 한 함수(`_create_trip`)에서 설문을 검사한다. 웹은 온보딩 답을 페이지에 들고 있다가, 온보딩을 마친 경우에만 `TripGateway.createTrip({ source, scenario, survey })`에 실어 보낸다. 온보딩을 마치지 않았으면 설문 없이 등록한다(백엔드도 설문 없이 받는다).

| 데이터 모드 | 동작 |
|---|---|
| `demo` | `tripSurveySchema`로 검사하고, 틀리면 여행을 만들지 않고 `INVALID_INPUT`(서버의 `422 invalid_survey`에 해당). 설문은 저장하지 않는다 |
| 실제 연결 | 계획 글 접수 흐름(`/v1/web/trip-intakes`)의 확인(`/confirm`)·일정 짜기(`/plan`) 요청 몸통에 `survey`(선택)로 싣는다(`2026-09-28` cs 세션이 `IntakeConfirmIn`·`IntakePlanIn`에 칸을 더했다). 온보딩을 마치지 않았으면 칸을 아예 보내지 않는다. 틀린 설문은 서버가 422 `invalid_survey`로 거절한다 |

## 2. 질문과 칸

| # | 질문 | 화면 선택 | 백엔드 칸 | 보내는 값 |
|---|---|---|---|---|
| 1 | 여행 테마 | 하나 | `theme` | `food` `nature` `culture` `activity` `shopping` `local` |
| 2 | 여행자 구성 | 하나 | `party` | `alone` `partner` `friends` `family` `other` |
| 3 | 선호 이동수단 | 여러 개 | `preferred_mobility[]` | `public` `walk` `car` `taxi` |
| 4 | 가장 중요한 것 | 하나 | `priority[]` | `food` · `activity` · `mobility`(화면의 「이동」) 1개 |
| 5 | 세부 우선순위 | 영역마다 하나 | `priority_details{food, activity, mobility}` | 영역마다 값 1개짜리 목록 |
| 6 | 실내·실외 | 식당·액티비티 각 하나 | `indoor_outdoor{dining, activity}` | `indoor` `outdoor` `any` |
| 7 | 일정이 꼬이면(15번) | 하나 | `on_disruption` | `replace` · `ask_first` |
| 8 | 여유(16번) | 하나 | `pace` | `relaxed` · `moderate` · `packed` |

- ★`[2026-09-28 사용자 지시]` **내국인 여부(`domestic`)는 묻지 않는다.** 받아도 반영할 곳이 없어서 뺐다. 백엔드 칸(`TripSurvey.domestic`)은 선택 값이라 안 보내도 된다. 프론트 Zod 거울에는 백엔드와 같게 칸만 남겼고 보내지는 않는다.
- 백엔드가 **판정에 쓰는 것은 7·8번뿐**이다(위 표 번호는 내국인 문항을 뺀 뒤 기준). 나머지는 받아 두기만 한다(D-020: 「반영했다」고 말하지 않는다).
- 1·2·3·6번의 세부 값은 D-020이 「담당 팀이 정할 값」으로 두어 백엔드가 문자열로 받는다. 화면 값은 지금 예시다.
- 세부 테마(`theme_details[]`)는 선택지가 정해지지 않아 묻지 않고 보내지 않는다.
- 이전 화면의 기피 음식·예산·종교·인원 수는 백엔드 설문에 칸이 없어 뺐다(모르는 칸은 422로 거절). 예산(`constraints.budget_krw`)·인원(`party_size`)은 설문이 아닌 등록 요청의 다른 칸이다.

## 3. 건너뛴 질문

화면에는 `미선택`으로 보이고, 그 칸은 **보내지 않는다.** 백엔드가 자기 기본값을 쓴다 — `on_disruption`은 `replace`(최적안을 먼저 적용하고 알림), `pace`는 비움(밀도 목표 없음 → 생성기 하루 2곳), 나머지는 null·빈 목록. 모든 질문을 건너뛰면 `{ "version": "2026-09-24.v1" }`만 간다.

`"unselected"` 같은 표시값은 보내지 않는다 — 정해진 값만 받는 칸은 422로 거절되고, 자유 문자열 칸은 그 글자를 답으로 저장한다. 백엔드는 저장할 때 기본값을 채우므로 「건너뜀」과 「기본값을 고름」(예: 15번 `replace`)을 구분하지 않는다. 구분이 필요하면 백엔드 계약을 바꿔야 한다. 질문별 기본값을 정하는 것도 백엔드의 기본값을 정하는 일이다.

## 4. 남은 것

- ~~접수 흐름에 설문 칸 추가~~ — `2026-09-28` 서버가 `/confirm`·`/plan`에 `survey`를 받도록 고쳤고 화면이 보낸다. 남은 것은 아래 둘이다.
- 세부 테마 선택지, 세부 우선순위 값 — 담당 팀이 정한다.
- 약관(목업)은 온보딩 답을 「현재 페이지 상태로 유지」한다고 적고 있다. 등록 때 서버로 보내므로 수집 항목·목적·보관을 약관에 반영해야 한다.
