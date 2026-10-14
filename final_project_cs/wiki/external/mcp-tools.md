---
type: contract
title: 여행 MCP 도구
description: 사용자·에이전트 키와 개인 AI OAuth로 본인 여행만 다루며 쓰기 도구는 기본 비활성이다
status: draft
tags: [api, security, contract]
owners: [human:미배정]
domain: travel
---

# 여행 MCP 도구


`app/domains/travel_ops/modules/mcp/mcp_server.py` · 고객 API 앱에 `/mcp/` 로 붙는다(Streamable HTTP, 무상태). 현재 사용하는 여행 MCP 경로입니다.

**원칙.** ①**MCP 는 새 규칙을 만들지 않는다** — 모든 도구가 웹 API(`/v1/web/*`)를 그대로 부른다(인증 · 소유 확인 · 멱등 · 남용 방어 · 판정이 한 곳). ②**호출자는 사용자 키가 정한다** — `Authorization: Bearer <사용자 키>` 또는 `X-User-Key`(웹이 쓰는 그 키). 도구 인자에 `customer_id` 가 없고 그 키 사용자의 **본인 여행만** 열린다. 키 없음·틀림은 연결 단계에서 401(`WWW-Authenticate: Bearer`). ③`mcp` 모듈 토글을 **요청마다** 본다(끄면 404). ④쓰기 도구는 `travel.mcp.write_enabled`(기본 **꺼짐**)가 켜졌을 때만 **등록**된다 — 프로젝트의 「MCP 는 read-only」 원칙을 기본으로 지킨다. 켜도 바뀌는 것은 **일정뿐**(판마다 기록 · 되돌리기 가능)이고 결제 · 업체 예약은 안 건드린다. ⑤키 원문은 오류 · 결과 어디에도 없다.

| 도구 | 종류 | 하는 일 (웹 API) |
|---|---|---|
| `tripilot_list_trips` | 읽기 | 내 여행 목록 (`GET /v1/web/trips`) |
| `tripilot_get_trip` | 읽기 | 일정 — 항목마다 종류(`kind_label` 식사·활동·이동) · 끼니 · 시각 · 장소 정보 · 다른 안. `outline` 한 줄 요약, `day` 로 그날만, 지도 핀은 뺀다 |
| `tripilot_get_notices` | 읽기 | cs 프로젝트 앱이 보낸 알림 전부 |
| `tripilot_get_proposals` | 읽기 | 「바꿀까요?」 하고 물어 둔 대기 제안 |
| `tripilot_get_itinerary_schema` | 읽기 | 일정 등록 JSON 스키마(`customer_id` 는 뺀다) |
| `tripilot_check_trip_risks` | 읽기 | ★`[2026-10-06]` **일정 위험 점검** — 곧 시작할 일정마다 외부 정보 6종(예보 · 특보 · 재난문자 · 교통 통제 · 대기질 · 지진)이 문제를 가리키나. 항목마다 `problem`(원인) · `clear` · `unknown`(확인 불가). 기본은 **감시가 모아 둔 캐시만 읽는다**(`GET /v1/web/trips/{id}/risks`) — 아래 「읽기 도구 둘」 |
| `tripilot_get_recovery_brief` | 읽기 | ★`[2026-10-06 사용자 결정]` **재난 뒤 상황 꾸러미** — 재난으로 멈춘 여행을 사용자가 다시 시작한 뒤(72시간 안) 읽는다: `facts`(출처 있는 사실) · `unknowns`(우리가 모르는 것) · `items`(항목마다 영향 판정 `affected`/`unknown`/`unaffected` + 이유) · `constraints`(`avoid_districts` · `affected_item_ids` · `lighter_day`) · `chosen`. 다시 시작한 정지가 없으면 `recovery: null`. `unknown` 을 「영향 없음」으로 다루지 않고 밀도를 임의로 낮추지 않는다(`GET /v1/web/trips/{id}/safety/recovery`) |
| `tripilot_judge_move` | 읽기 | ★`[2026-10-06]` **이동 판정** — 서울 안 두 장소 → 출발 시각 · 경로(노선) · 소요 · 근거 등급 · 확인 시각 (`POST /v1/web/moves/judge`) — 아래 「읽기 도구 둘」 |
| `tripilot_ask` | 쓰기 | 자유 문장을 여행 창구에 그대로 전한다 — 질문은 사실로, 요청은 조건 확인 뒤 변경 (`POST …/messages`) |
| `tripilot_report_issue` | 쓰기 | 지연(`minutes`) · 휴무 · 품절(`products`) 구조화 신고 (`POST …/reports`, 웹 쌍둥이 신설) |
| `tripilot_swap_item` | 쓰기 | 항목을 다른 안으로 (`POST …/items/{item}/alternate`, 웹 쌍둥이 신설) — **현재 판 번호를 cs 프로젝트 앱에서 읽어** 보낸다 |
| `tripilot_choose_proposal` | 쓰기 | 대기 제안에 답(안을 고르거나 원래대로) |
| `tripilot_rollback` | 쓰기 | 옛 판으로 되돌리기(자동·수동 변경 모두) |
| `tripilot_submit_itinerary` | 쓰기 | AI 가 만든 일정을 **판정**(영업시간 · 이동 · 동선 · 밀도)받고 통과하면 내 여행으로 등록. 못 통과하면 `problems` 를 돌려준다 |
| `tripilot_plan_trip` | 쓰기 | cs 프로젝트 앱의 일정 생성기가 짜서 판정을 통과한 것만 등록(첫날 · 일수 · 인원 · 취향 글) ★`[2026-10-07]` 재난 뒤 다시 짤 때 선택 인자 `avoid_districts`(꾸러미의 제외할 구 — 그 구의 후보를 뺀다) · `lighter_day`(사용자가 「오늘은 가볍게」를 골랐을 때만 true — 밀도 목표 한 단계 낮춤) |

### 읽기 도구 둘 — 일정 위험 점검 · 이동 판정 `[2026-10-06 사용자 요청]`

둘 다 **읽기 전용**이라 쓰기 스위치(`travel.mcp.write_enabled`)와 상관없이 늘 등록된다. MCP 는 새 규칙을 만들지 않는다 — 규칙은 웹 입구(`/v1/web/*`)에 있고 도구는 그것을 그대로 부른다. 계약 [rest-endpoints.md 「일정 위험 점검 · 이동 판정」](rest-endpoints.md).

**`tripilot_check_trip_risks(trip_id, item_id?, within_hours?, fresh?)`** — 감시(3분 주기)가 하는 점검과 **같은 점검**을 사람이 읽을 모양으로.
- **항목마다 셋 중 하나**: `problem`(문제 있음 · `problems[]` 에 원인 — 재난문자 본문 · 특보 종류 · 통제 …) · `clear`(6종 **모두** 확인했고 문제 없음) · `unknown`(문제는 못 찾았지만 **못 확인한 종류가 있다** — `unknown_categories[]`). ★확인 불가를 「문제 없음」으로 말하지 않는다(결정 15). 「해당 없음」(실내 장소의 예보)은 확인 불가가 아니다. 문제가 찾아졌으면 못 확인한 종류가 있어도 `problem`.
- **확인 시각 둘**: `checked_at`(보고를 만든 시각) · 종류마다 `categories[].confirmed_at`(그 소스 값을 **처음 받아 온** 시각 — 캐시 값이면 그때). `oldest_confirmed_at` 이 가장 낡은 것.
- **점검 시각 · 먼 일정** `[검토 반영]`: 점검은 `max(항목 시작, 기준 시각)` 으로 한다 — 이미 시작한 항목을 시작 시각으로 점검하면 시작 뒤에 난 사건이 창 밖이라 안 보인 채 `clear` 가 된다. 곧 시작하는 항목은 시작 시각 그대로(감시와 같은 캐시 키 — 캐시 적중). **시작이 `snapshot_hours`(3) 넘게 남은 항목**은 특보 · 대기질 · 교통 · 재난문자 · 지진이 「지금 상태」만 말하므로(대기질은 시각을 무시) 그 종류를 `too_early`(확인 불가)로 두고 `clear` 로 말하지 않는다(문제가 있으면 `problem` + `as_of_now`). 예보만 앞을 본다. 기본 `horizon_hours` 는 3.
- **일부만 답한 소스** `[검토 반영]`: 교통은 ITS · UTIC 중 한쪽만 답해도 점검기는 `ok` 로 돌려준다 — 집회 · 행사를 놓쳤을 수 있어 `unknown`(`partial`, `answered_by` · `missing_from`). 구분 못 한 재난문자(`unclassified_count`) · 모델 추정 대기질(`estimated`)은 `cautions` 로 드러낸다.
- **이유 문구는 고정 문장** `[검토 반영]`: 점검기의 `reason`(소스 미연결 사유에 환경변수 · 파일 이름이 들어 있다)을 내보내지 않는다.
- **동시 처리 상한** `[검토 반영]`: 하루 횟수 제한(기본 꺼짐)과 별개로 같은 입구를 동시에 처리하는 수에 상한(`travel.mcp.max_concurrent` — 점검 4 · 이동 판정 4)이 있고 넘으면 기다리지 않고 503 `busy`(`Retry-After: 5`). 캐시 읽기도 호출마다 DB 연결을 여러 번 열고 항목마다 스레드를 만든다. 부하 시험은 하지 않았다.
- **하루 한도를 안 깎는다(D-017)** — 기본(`fresh=false`)은 **감시가 모아 둔 공유 응답 캐시(`source_response_cache`)만 읽는다**: 바깥에 한 번도 안 나가고(`CacheOnlyLimiter`) 한도 줄 · 실패 수에 안 센다. 캐시에 없는 종류는 `unknown`(`code=not_cached`). 감시가 같은 장소 · 시각으로 점검해 둔 항목은 캐시에 있다(같은 호출 모양 — 감시는 90분 안 항목을 점검한다).
- **`fresh=true`** 는 캐시에 없는 종류를 새로 부른다(`fresh` 점검기가 조립 안 된 서버는 503 — 몫 없는 점검기로 조용히 대신하지 않는다) — 단 **낮은 우선순위**: 소스의 **하루 · 이번 달 한도의 `travel.mcp.risk_check.fresh_share`(0.5)까지만** 쓴다(`CallBudget.share` — 차감하는 **같은 SQL 안에서** 비교하므로 동시 호출도 몫을 못 넘고, 줄의 상한 칸은 진짜 값 그대로이며, 몫으로 거절한 것은 감시의 「거절 수」에 안 센다). DB 를 못 읽으면 **부르지 않는다**(일반 호출의 `allow` 정책과 반대). 한 번에 `fresh_max_items`(3)개까지 · `risk_check` 로 센다(키 10 · 주소 30 · 서비스 40 / 하루 — 제한이 켜져 있을 때 429 · 503). 새로 부른 값은 캐시에 남아 감시도 쓴다. `[한계]` 몫은 **DB 로 세는 소스에만** 걸린다(`travel.source_budget_sources` · 한도 env — `open_meteo` 등은 제외, 예산 층이 꺼져 있으면 몫 없이 나가고 조립이 경고 로그를 남긴다) · 몫은 줄의 **전체 사용량**에 대한 비율이라 감시 사용량이 50% 를 넘으면 fresh 는 그날 못 부른다 · 몫이나 DB 오류로 못 부른 것도 `source_failed` 로 보인다(소스가 알려 주지 않는다).
- **캐시 읽기도 센다** — 기본 호출도 바깥 한도는 안 쓰지만 서버 DB 조회 · 스레드는 쓰므로 `risk_read`(키 600 · 주소 1,800 · 서비스 20,000 / 하루 — 제한이 켜져 있을 때)로 센다. `[코덱스 검토 반영 2026-10-06]`
- **확인 불가의 이유**: `not_cached`(캐시만 읽는 호출에서 못 읽음 — **캐시에 없는 것인지 소스가 실패한 것인지 가르지 못한다**, 이유 문구가 둘 다 말한다) · `source_failed`(새로 불렀는데 못 냈다) · `not_connected`(소스 미연결) · `missing`(점검 응답에 그 종류가 없다 — 6종 가운데 빠진 종류는 항상 확인 불가로 채워 `clear` 가 되지 않는다).
- 점검 대상은 지금부터 `horizon_hours`(12) 안에 시작하거나 진행 중인 항목(시작이 빠른 순 · 최대 `max_items`(6)). 이동 항목은 장소 기준 6종 점검 대상이 아니다(`skipped`). `item_id` 를 주면 그 항목만(시간 범위 무시).
- 못 하는 경우: 장소(좌표)를 모르면 그 항목 `unknown`(`no_place`) · 점검이 죽으면 그 항목만 `unknown`(`check_error`, 내부 오류 문구를 내보내지 않는다) · 점검기가 조립 안 된 서버는 503 `risk_check_unavailable`.

**`tripilot_judge_move(origin_*, destination_*, trip_id?, origin_item_id?, destination_item_id?, depart_at? | arrive_by?)`** — 이동 판정기(시간표 판정 — 일정 짜기 · 등록 판정 · 채팅 「가는 길」이 쓰는 그것)를 직접 부른다.
- 장소는 이름 + 좌표 또는 내 여행의 일정 항목(`trip_id` + `*_item_id` — 본인 여행만). **서울 밖은 판정하지 않는다**(`out_of_scope`). 시각은 `depart_at`(이 시각에 출발 — 판정기가 도착 목표에서 거꾸로 셈하므로 두 번 부른다) 또는 `arrive_by`(한 번) 중 **하나**, 둘 다 없으면 지금 출발.
- 결과 `grade`(근거 등급)는 **고른 경로가 무엇에 근거하나**로 가른다(경로마다 `grade` 도 있다): `timetable`(고른 경로가 **열차**(버스가 없다) — 시간표 판정 · 출발 · 도착 시각 · 소요 · `route`(`label` · `uses` 노선 · 도보 m · 요금) · `alternatives` · 판정에 쓴 시간표 판 `basis`(`timetable_built_at` · `rules_version` · `timetable_stale`)) · `estimate`(①고른 경로가 **도보 · 택시 · 버스가 낀 경로** — 열차 시간표가 아니라 거리 · 도로 길찾기 · 버스 노선 단위 배차 추정으로 셈한 값(`grade_note`). 도보는 보행망 길찾기가 없으면 직선 거리 × 우회계수인데 판정기가 어느 쪽인지 알려 주지 않는다 필수 이동 판정기가 비활성·누락되면 **HTTP 503 `team_unavailable`**로 실패하며 어림값을 성공 결과처럼 반환하지 않는다) · `none`(판정기가 「갈 방법이 없다」(막차 뒤 · 첫차 전)고 한 것 `status=no_route`, 또는 **판단하지 못한 것** `status=undetermined`(데이터 없음 · 확인 못 함 · 택시 길찾기 불통 — 갈 방법이 없다는 뜻이 아니다) — 이유를 싣고 어림값을 덧붙이지 않는다. 이유 문구의 주소 · 환경변수 · 파일 경로는 가린다). ★「시간표 판정」이지 **실시간 운행 확정이 아니다**(지연 · 사고는 반영하지 않는다). 판정기가 예외를 던지거나 이상한 모양을 주면 500 이 아니라 `unavailable`(`reason.code=engine_error`). 서울 밖 검사는 판정기 · 근거에 닿기 전에 한다.
- **출발 시각(`depart_at`)** — 판정기는 도착 목표에서 거꾸로 셈하므로 도착 목표를 출발 +90 → +180 → +360분으로 **최대 셋** 넓혀 첫 성립 경로를 찾고, 찾으면 그 소요에 맞춘 목표로 한 번 더 판정해 출발을 당긴다(둘째가 안 되면 첫 결과 — **가장 이른 출발이라는 보장은 없다**). 못 찾으면 `no_route` + `searched`(「출발 후 360분 안에 도착하는 목표까지만 확인」) — 6시간 넘는 길은 「없다」가 아니라 「안 찾았다」다. 결과에 `requested_depart_at` · `wait_min`(요청 시각에서 판정기가 고른 출발까지 분). ★둘째 판정이 안 돼 첫 결과를 쓰면 `earliest_not_guaranteed=true` — 판정기는 「가장 늦게 떠나도 되는 후보」를 고르므로 그 출발이 가장 이른 출발이라는 보장이 없고 `wait_min` 이 첫차 대기가 아니라 탐색 방식 때문일 수 있다.
- **바깥 유료 소스(Places · Route Matrix)를 부르는 길이 없다** — 판정기는 이 서버의 시간표 · 도로 그래프와 **자체 길찾기 서버(GraphHopper — 설정한 주소로 HTTP 호출)**만 쓴다(2026-10-06 코드 확인: 이동 판정기 폴더에 Google 호출 없음 · 따릉이 실시간은 이 경로에서 꺼져 있다). 그래서 하루 한도 걱정 대신 계산 부하를 `move_judge`(키 200 · 주소 600 · 서비스 2,000 / 하루)로 센다.

`[미확인]` 감시와 MCP 의 캐시 키가 같은 날 실제로 얼마나 겹치는지(= 기본 호출이 `unknown` 으로 끝나는 비율)는 **재지 않았다** — 감시가 돌지 않는 환경(개발)에서는 기본 호출이 대부분 `unknown` 이다. 값(`travel.mcp.risk_check.*` · `web_guard.limits.risk_check` · `risk_read` · `move_judge`)은 우리가 고른 것이다. 점검 대상에서 끝 시각을 모르는 항목은 시작한 뒤에는 진행 중으로 보지 않는다(끝을 지어내지 않는다). 외부 개인 AI 로 종단 접속한 기록은 없다.

**접속.**
```
원격(Claude Code)   claude mcp add --transport http tripilot https://<주소>/mcp/ --header "Authorization: Bearer <사용자 키>"
로컬(stdio 프록시)  TRIPILOT_USER_KEY=<사용자 키> python -m app.domains.travel_ops.modules.mcp.mcp_server --base-url http://127.0.0.1:8042 [--write]
```
사용자 키는 웹에 처음 접속할 때 한 번 보여 준다(`POST /v1/web/session`). 시험 `tests/e2e/test_mcp_server.py` 는 **MCP 프로토콜로 실제 접속**한다(initialize → 도구 호출) — 도구 이름 개수만 세던 옛 검사가 못 보던 것이다. 시험용 로컬 개발 서버(uvicorn)에 SDK 클라이언트로 HTTP 접속해 `/mcp/` · `/mcp` 둘 다 열리고 키 없이는 401 임을 확인했다(2026-10-02).
`[2026-10-12 로컬 구현]` 개인 AI OAuth의 발견·회원 동의·인가 코드 + S256 PKCE·토큰 교환·갱신·폐기를 추가했습니다. OAuth 토큰은 Bearer 헤더만 받으며 검증된 사용자·scope를 내부 웹 API로 전달합니다. 에이전트 키도 MCP 입구에서 확인합니다. 쓰기 스위치는 기본 꺼짐이며 키·OAuth 모두 본인 여행과 읽기·변경 권한을 검사합니다. [OAuth 계약](personal-ai-oauth.md) · [격리 검증 보고](../records/reports/2026-10-12_personal-ai-oauth.md).

`[미확보]` 실제 외부 개인 AI(Claude · ChatGPT)의 **종단 접속 기록**과 x600 서버의 이번 OAuth 배포 기록은 확보하지 않았습니다. 쓰기 도구의 별도 호출 한도는 웹 남용 방어(`message` 횟수)를 그대로 씁니다.


## 사용 종료된 접속 경로

옛 Case 도구 3종과 고정 principal 보조 함수는 현재 앱·시험에서 제외하고 [보존 기록](../records/commerce_2026-10-11/wiki--external--mcp-tools.md) 및 legacy에 남겼습니다. 현재 도구의 회귀 시험은 [MCP 프로토콜 시험](../../tests/e2e/test_mcp_server.py)·[여행 읽기 시험](../../tests/e2e/test_mcp_read_tools.py)입니다.

## 관계

- [REST 계약](rest-endpoints.md) — MCP가 위임하는 현재 여행 API
- [권한 경계](auth-boundary.md) — 고객별 접근 조건


## 이전 절 링크

<a id="mcp-도구"></a>
<a id="-지금의-mcp--여행-도구-2026-10-02-사용자-지시"></a>
<a id="읽기-도구-둘--일정-위험-점검--이동-판정-2026-10-06-사용자-요청"></a>
<a id="옛-도구-3종-쇼핑몰-시절--연결-안-됨"></a>
<a id="도구-3종-옛--쇼핑몰-case-도구"></a>
<a id="-mcp는-read-only다"></a>
<a id="-쓰기-3단계"></a>
<a id="-이-확장에는-순서가-있었다--방어가-먼저다"></a>
<a id="보안-원칙-5가지"></a>
<a id="개수가-고정돼-있다"></a>
<a id="scope-확인"></a>
<a id="idempotency"></a>
<a id="무엇을-하지-않는가"></a>
<a id="a2a와-다르다"></a>
<a id="불변식"></a>
<a id="계약-원문에서-보강-2026-09-03"></a>
<a id="도구-시그니처--계약은-비동기-코드는-동기"></a>
<a id="mcp-ownership응답-제약"></a>
<a id="-2026-09-06-open_support_case가-분류를-시도조차-안-했다--고쳐졌다"></a>
<a id="관계"></a>
