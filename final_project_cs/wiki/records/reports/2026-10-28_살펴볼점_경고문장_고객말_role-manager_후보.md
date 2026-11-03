# 2026-10-28 여행 「살펴볼 점」 경고 · 일정 짜기 remedy · 식당 영업 이유를 고객 말로 — role-manager 커밋 후보

## 결론
- 후보 커밋 `efc6fca47c76ba12cbf6557358b458c025c630b4`. 기준은 role-manager `bdb48ffc9035e175098592c2a64c9cc642e8732b`(팀 저장소 ls-remote로 확인). **push하지 않았다.**
- worktree: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/fix-warning-wording-20261028-0843/rm`
- patch: `.../fix-warning-wording-20261028-0843/out/fix-warning-wording.patch`, sha256 `dc7255c2be2c25e11ec49738b4aa29d35358b7f601d27223cac081ebaf01ba31`
- 빠른 관문(5 shard, `-m 'not live and not db and not slow'`, 커밋 뒤 안정된 트리, 실행 전후 트리 해시 같음):
  - `RELDATE_SHIFT_DAYS=37`: 10725/10898 통과(실패 0, 오류 0, skip 173)
  - 실제 오늘: 10725/10898 통과(실패 0, 오류 0, skip 173). 37일 실행과 nodeid 집합이 같다. 이 숫자는 다음 두 실행을 합친 것이다.
    - `real3`의 shard 00 · 01 · 02 · 04
    - shard 03 단독 재실행(`out/real3_s03`, 2530/2530 통과)
    - `real2` · `real3`의 5 shard 동시 실행에서는 `test_intake_watch_slot_lifetime.py::…[content-2.0]` 하나가 시간 판정으로 실패했다(0.39 s · 0.30 s > 0.25 s). 이 파일은 바꾸지 않았다.
    - 실패 원인: 새 시험 파일이 늘어 shard 경계가 밀렸고, 이 파일이 shard 03의 첫 파일이 됐다. 그래서 다섯 프로세스가 동시에 시작하는 부하 속에서 돌았다.
    - 이 파일만 따로 두 번 돌렸을 때(11/11 ×2)와 shard 03만 단독으로 돌렸을 때 모두 통과했다.
- DB 시험(비교 DB `gugu_replay_improved_20261025`, `db/db.sh`): `tests/scenario/test_confirmed_scenario.py` 9/9 통과. 이 시험은 바뀐 문구의 일부인 「주문 가능한 시간이 촉박」을 단언한다. 시험 전후 preflight가 완전히 같았다.
- 웹 코드는 바꾸지 않았으므로 vitest는 해당 없다.
- 상태: 원격 반영 안 됨, x600 배포 안 됨, 로컬 서빙 반영 안 됨.

## 범위(웹이 실제로 그리는 필드)
- `trip.warnings[].reason` · `remedy`: `trip-attention.tsx:412-413`, `gateway.ts:195`. 밀도 경고(`density.py`)와 품질 경고(`itinerary_quality.py`)가 여기로 들어간다(`trip_api.py:687`).
- `last_order_tight` 이유: `replan._break_last_order` · `_closing_last_order`.
- 식당 영업 판정 이유 `replan.dining_fits`:
  - 대체 후보를 못 찾았을 때 안내 「살펴본 곳: X — 이유」에 들어간다(`itinerary_changes.py:1645`).
  - 확인 필요 안내의 `warnings`에도 들어간다(`itinerary_changes.py:900`).
- `planner.PlanRefused` `remedy`: 422 응답의 detail 필드다. 웹은 이 필드를 그리지 않지만 과제 지시에 따라 바꿨다.
- 판정 로직, 공개 필드(`code` · `date` · `items` · `policy_basis` …)는 그대로다. 문장 값만 바꿨다. 받침 조사는 `itinerary_checks.particle()`을 재사용했다.

## 바뀐 문장 전/후
| 어디 | 전 | 후 |
|---|---|---|
| same_place_twice reason | 남산 와 남산 다시 은(는) 같은 곳이다 — 그날 두 번 들어 있다 | 남산과 남산 다시는 같은 곳이에요. 그날 일정에 두 번 들어 있어요 |
| same_place_twice remedy | 한 번으로 줄이거나 … 바꾼다(일부러 다시 가는 것이면 그대로 둔다) | 한 번으로 줄이거나 둘 중 하나를 다른 곳으로 바꿔 주세요. 일부러 다시 가는 거라면 그대로 두셔도 돼요 |
| meal_missing reason | 점심 시간대(11:30~14:00)에 식사 일정이 없고 식사할 틈도 30분뿐이다 — 다른 일정이 그 시간을 채운다 | 점심 시간대(11:30~14:00)에 식사 일정이 없어요. 다른 일정이 그 시간을 채워 식사할 틈도 30분뿐이에요 |
| meal_missing remedy | 그 시간대에 식사 항목을 넣거나 … 틈을 둔다(…그대로 둔다) | 그 시간대에 식사 일정을 넣거나 일정 사이에 식사할 틈을 두세요. 일부러 거르는 거라면 그대로 두셔도 돼요 |
| route_zigzag reason | 그날 활동 4곳을 도는 길이가 약 13.3km 인데, 순서를 바꾸면 약 6.7km 로 돌 수 있다 | 그날 활동 4곳을 지금 순서로 돌면 약 13.3km인데, 순서를 바꾸면 약 6.7km로 돌 수 있어요 |
| route_zigzag remedy | 시간이 정해진 예약이 아니면 가까운 곳끼리 묶어 순서를 바꾼다 | 시간이 정해진 예약이 아니라면 가까운 곳끼리 묶어 순서를 바꿔 보세요 |
| past_day_end reason | 야경 투어 — 23:00에 끝나 하루 마감(22:00)을 넘는다 | 야경 투어: 23:00에 끝나서 하루 마감(22:00)을 넘겨요 |
| past_day_end remedy | 마감 안에 끝나게 앞당기거나 줄인다(…그대로 둔다) | 마감 전에 끝나도록 앞당기거나 줄여 주세요. 일부러 늦게까지 있는 일정이라면 그대로 두셔도 돼요 |
| last_order_tight reason(종료 앞) | 한식당: 라스트오더(21:00)까지 10분 — 주문 여유 20분이 안 된다 | 한식당: 라스트오더(21:00)까지 10분뿐이라 주문 여유 20분이 안 돼요 |
| last_order_tight reason(브레이크 앞) | …: 15:00 브레이크타임 전 라스트오더(14:30)까지 10분 — 주문 가능한 시간이 촉박하다 | …: 15:00 브레이크타임 전 라스트오더(14:30)까지 10분뿐이라 주문 가능한 시간이 촉박해요 |
| last_order_tight remedy | 더 일찍 도착하게 앞당기거나 마지막 주문 시각을 미리 확인한다 | 더 일찍 도착하도록 앞당기거나 마지막 주문 시각을 미리 확인해 주세요 |
| last_order_unknown remedy | 방문 전에 마지막 주문 시각을 확인한다 | 방문 전에 마지막 주문 시각을 확인해 주세요 |
| density_exceeded reason(프리셋) | 하루 일정이 연구 보정 프리셋의 목표를 초과합니다 | 하루 일정이 고르신 여유 정도보다 빡빡해요 |
| density_exceeded reason(직접 값) | 하루 일정이 사용자가 지정한 목표를 초과합니다 | 하루 일정이 정하신 여유 목표보다 빡빡해요 |
| density_exceeded reason(estimated) | 하루 일정이 추정 프리셋의 목표를 초과합니다 | 하루 일정이 기본 여유 기준보다 빡빡해요 |
| density_exceeded remedy | 고정 예약·식사·이동·완충시간을 유지하며 선택 활동 축소를 검토하세요 | 예약 · 식사 · 이동 시간과 여유 시간은 그대로 두고, 꼭 가지 않아도 되는 일정을 줄여 보세요 |
| density_unmeasurable remedy | 누락되거나 잘못된 시간·이동 정보를 보완하세요 | 빠지거나 잘못된 시간 · 이동 정보를 채워 주세요 |
| 밀도 이유 | 항목 1: 시작 시간대 누락 | 궁: 시작 시각에 시간대 정보가 없어요 |
| 밀도 이유 | 항목 1: 가용시간 창 없음 또는 창 밖 시작 | 궁: 정해 둔 활동 시간 밖에서 시작해요 |
| 밀도 이유 | 항목 1: 종료 누락·시간 순서 오류·가용시간 초과 | 박물관: 끝나는 시각을 알 수 없거나, 시작 시각보다 늦지 않거나, 정해 둔 활동 시간을 넘어요 |
| 밀도 이유 | 항목 1: 대기 주석은 비이동 항목 소요 안의 유효한 시간이어야 합니다 | 박물관: 적힌 대기 시간이 맞지 않아요. 대기 시간은 방문 일정에만, 머무는 시간 안으로 적을 수 있어요 |
| 밀도 이유 | 항목 1: 경로 소요 누락 또는 이동시간 부족 | 지하철: 이동 소요 시간을 모르거나 잡아 둔 이동 시간이 모자라요 |
| 밀도 이유 | 항목 1/2: 시간 겹침 | 궁과 시장의 시간이 겹쳐요 |
| 밀도 이유 | 항목 1/2: 이동시간 누락 또는 간격 부족 | 궁에서 시장으로 가는 이동 시간을 모르거나 사이 간격이 모자라요(ㄹ 받침: 명동길로) |
| 밀도 입력 오류 | 밀도 입력 형식이 잘못되었습니다 / 가용시간 시작 날짜 또는 길이가 잘못되었습니다 / 하루 가용시간 창이 서로 겹칩니다 | 하루 여유 설정 값을 읽지 못했어요 / 하루 활동 시간의 날짜나 길이가 맞지 않아요 / 날짜별로 정한 활동 시간이 서로 겹쳐요 |
| dining_fits | 라스트오더까지 주문 여유 20분이 안 된다(요식 원장) | 라스트오더까지 주문 여유 20분이 안 돼요 |
| dining_fits | 원장에서 방문 시간대의 영업을 확인할 수 없다 / 원장 기준 그 시각 영업하지 않는다 | 방문 시간대에 영업하는지 확인하지 못했어요 / 그 시각에는 영업하지 않아요 |
| dining_fits | 영업시간을 확인할 수 없다 / 그 시각 영업하지 않는다 / 15:00 브레이크타임에 걸린다 | 영업시간을 확인하지 못했어요 / 그 시각에는 영업하지 않아요 / 15:00 브레이크타임에 걸려요 |
| planner remedy(not_enough_candidates) | 장소 카탈로그를 더 받거나(TourAPI 동기화) 선호 조건을 줄인다 | 선호 조건을 줄여서 다시 짜 보세요 |
| planner remedy(plan_short) | 후보를 더 받거나 선호 조건을 줄인다 | 선호 조건을 줄여서 다시 짜 보세요 |
| planner remedy(plan_infeasible 1) | 완화 조건을 하나 풀거나(예산·결제 조건) 후보를 더 받는다 | 예산이나 결제 조건 중 하나를 풀고 다시 짜 보세요 |
| planner remedy(plan_infeasible 2) | 하루 항목을 줄이거나 가까운 장소로 바꾼다 | 하루 일정 수를 줄이거나 서로 가까운 장소로 바꿔 보세요 |
| planner remedy(day_overflow) | 하루 항목을 줄이거나 시작 시각을 앞당길 수 있는 장소로 바꾼다 | 하루 일정 수를 줄이거나 더 일찍 시작할 수 있는 장소로 바꿔 보세요 |

- 영문으로 끝나는 이름은 읽는 소리를 모르므로 겸용 조사로 둔다. 예: 「Starfield과(와) COEX은(는) 같은 곳이에요」. `particle` 약속을 따른 것이다.
- 영문 고객 문장: 이 경로에서 서버가 만드는 영문 문장은 없다. 웹 영문 화면도 `warnings` 문장을 서버가 쓴 한국어 그대로 보인다(웹 쪽 과제).

## 시험
- RED: 새 시험 `tests/unit/travel/test_warning_customer_wording.py`가 수정 전 트리에서 24건 모두 실패했다(`out/red.log`, rc=1). 실패 원인은 전부 문장 단언이었다.
- GREEN:
  - `out/green.log`: 24/24 통과
  - Codex 반영 뒤 `out/green2.log`: 93/93 통과(새 시험 26건, density · quality 묶음 포함)
  - 관련 파일 묶음 `out/related.log`: 896건 통과, 실패 2건. 실패 2건은 아래 단언 갱신 전의 결과다.
- 새 시험은 모든 품질 경고, 밀도 경고 · 이유 · 입력 오류, planner remedy(AST에서 상수 전부 추출), dining_fits 8개 분기에 다음 규칙을 건다.
  - 해요체로 끝난다.
  - 반말 평서형이 없다.
  - 숫자 · 단위 뒤 조사를 띄어 쓰지 않는다.
  - 한글 이름 뒤에 겸용 조사 · 띄어 쓴 조사를 쓰지 않는다.
  - 내부 이름(원장 · 프리셋 · 카탈로그 · TourAPI · 완충 · 주석 · 가용시간 · 이동 계산기)과 「항목 N」 순번이 없다.
- 옛 문구를 단언하던 시험 2곳은 `contract_correction` 주석을 달고 기대 문구만 바꿨다.
  - `test_density.py::test_presets_and_direct_preferences_have_different_warning_basis`: 「연구」 · 「사용자」 대신 「고르신 여유 정도」 · 「정하신 여유 목표」를 단언한다. 두 문장이 서로 다르다는 단언을 더했다.
  - `test_fresh_alternate.py::test_saying_no_names_the_time_the_distance_and_the_main_reason`: 「그 시각에는 영업하지 않아요」를 단언한다.
- 첫 관문 실행(`out/real_interim`, `out/p37_interim`)은 Codex 반영으로 소스가 바뀌어 도중에 멈췄다. 중간 관측으로만 보관한다.

## Codex 검토(`codex/`, gpt-6.1-sol, 본문만 보는 검토, session `01a17fd0-…`, tokens 14,229)
판정은 approve_with_changes였고, 지적은 다음처럼 처리했다.
- 끝 시각 · 대기 시간 이유가 실제 조건과 맞지 않는다 → 「시작 시각보다 늦지 않거나」 「방문 일정에만, 머무는 시간 안으로」로 바꿨다.
- 「하루 시간」이 모호하다 → 「활동 시간」으로 바꿨다.
- ㄹ 받침 「(으)로」, 영문 끝 겸용 조사 시험이 없다 → 「명동길로」 「서울숲으로」 「Starfield과(와) COEX은(는)」 시험을 더했다. 영문 끝 겸용 조사는 시험에서 허용하도록 정규식을 고쳤다.
- 시간 창 겹침 사례가 날짜 오류로 먼저 빠진다 → 날짜 · 길이는 맞고 서로 겹치는 창으로 바꿨다. 「겹쳐요」도 단언한다.
- 「주문 여유 20분이 안 돼요」보다 「주문할 시간이 …분도 남지 않았어요」가 낫다는 제안 → 받아들이지 않았다. 기존 시험 2곳(`test_dining_replan_rules` · `test_confirmed_scenario`)이 「주문 여유」 · 「주문 가능한 시간이 촉박」을 단언하므로 그 말을 지켰다.
- 시험 단언 2곳 변경은 검증 약화가 아니라고 판정했다.
- `PlanRefused.message`는 이번에 바꾸지 않고 목록으로 보고하는 것이 맞다고 판정했다. 이유는 아래 「남은 것」 첫 항목과 같다.

## 남은 것(이번 범위 밖 — 목록만)
고객에게 보일 수 있는데 이번에 고치지 않은 문장:
- `planner.PlanRefused.message`(「초안을 짰지만 판정을 통과시키지 못했다: …」 「…곳뿐이다」 「…만 짜였다」)
  - 반말이라 웹 `error-text.ts`가 버리고 「요청을 처리하지 못했어요 … (plan_infeasible)」를 보인다. 이 일반 문구에는 내부 코드가 노출된다.
  - message를 해요체로 바꾸면 서버 상세가 웹에 보이게 된다. 문체만 고치는 일이 아니라서 별도 후보가 필요하다. 고객 문장과 진단 문장을 나눠야 한다.
- 대체 후보 탈락 이유(`replan.py`의 `rejected.append`)는 「살펴본 곳」으로 보이는데 반말이고 내부 말이 있다.
  - 대상 위치는 414 · 420 · 487 · 491 · 559 · 584 · 654-703 · 771번 줄이다.
  - 예: 「그 시각 영업하지 않는다」(활동), 「다음 일정에 N분 늦는다(대중교통 N분 — 이동 계산기)」, 「재검증 불통과: …」.
  - 활동 쪽은 `tests/integration/travel/test_activity_catalog_pool.py:141`이 옛 문구를 단언한다.
- `itinerary_changes.NoChange("no_meal", message="늦어지는 시각 뒤에 식사 일정이 없다")` 등 NoChange message 중 반말인 것. 채팅 답으로 보이는지 확인이 필요하다.
- `ports/data_sources/google_places.py:316`: 「{start}~{end} 에 영업하지 않는다」(띄어쓰기 · 반말)
- `instances/mobility/engine/adapter.py:146`: 「이동 판정을 낼 수 없다: {code}」(내부 코드)
- `trip_api.py:1014-1017` 전부-과거 문장의 「확인해주세요」 띄어쓰기. 웹 `ALL_PAST_TEXT`와 같은 문장이고 날짜 가드 소유라 손대지 않았다.

내부 로그 · 관리자 전용(범위 밖):
- `itinerary_quality` `log.warning`
- `mobility/devtools/judgment_log.py`
- `density.DensityInput`/`DayWindow` 검증 메시지(ValidationError는 고정 문장으로 바뀌어 화면에 나가지 않는다)
- `instances/dining/agent_tools.py:261`(에이전트 도구 결과)

## 관문 기록
- `out/real2`·`out/p37b`(동시 실행), `out/real3`(실제 오늘 재실행), `out/real3_s03`(shard 03 단독), 트리 해시 `out/tree-start.txt` 실행 전후 같음.
- 시간 판정 실패는 이 후보와 무관한 부하 민감 시험이다. 부모가 push 전 관문을 돌릴 때는 shard 경계가 바뀐 것을 감안해야 한다.
