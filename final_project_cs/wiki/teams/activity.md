---
type: guide
title: Activity 에이전트 팀 안내
description: 활동 검증의 책임·범위·현재 구현과 과거 개발 기록을 구분한다
status: draft
domain: travel
---

# Activity 에이전트 팀 안내

Activity 에이전트 팀은 여행지의 자연·문화·레포츠·쇼핑 활동이 일정 조건에서 가능한지 검증하고 변경안을 제시합니다. 예약 유무·실내 여부·레저 여부만으로 활동 범위를 좁히지 않습니다.

## 책임과 경계

영업·운영 조건, 날씨, 시간과 장소의 근거를 대조하고 에이전트 팀 결과를 반환합니다. 직접 쓰기 실행을 하지 않으며 [Team 계약](team-contract/index.md)과 [코드 구조 계약](code-layout.md)을 따릅니다.

## 구현과 검증

- [Activity 구현](../../app/domains/travel_ops/instances/activity/) — 현재 작업 위치
- [활동 시험](../../tests/unit/travel/activity/) — 회귀 검증 위치
- [여행별 문제 조정 결정](../../../wiki/decisions/D-017-watch-cadence-golden-time.md) — WatchBatch 책임과 계산 등록 경로

아래 기록의 과거 미구현·실측 수치는 해당 날짜의 상태입니다. 현재 완료 판단은 현재 코드와 후속 실행 기록을 대조합니다.

## 재난문자 감시 주기 — 2026-10-24 확인

재난문자 수집 · 감시는 코어 몫이고(D-017), 활동 팀은 감시가 넘긴 결과로 장소 닫힘 · 대체 후보를 판정합니다.

| 무엇 | 값 | 정본 · 출처 |
|---|---|---|
| 여행 감시 주기 | **3분**(`watch_interval_seconds: 180`, 허용 오차 30초) | [guardrails.yaml](../../config/guardrails.yaml) `watch_interval_seconds` — 팀 결정 [D-017](../../../wiki/decisions/D-017-watch-cadence-golden-time.md) |
| 재난문자 응답 재사용 | **20분**(`disaster_msg_cache_seconds: 1200`) — 실제 재난문자 API 신규 호출은 최대 20분에 한 번, 하루 최대 72회 | 같은 파일 `disaster_msg_cache_seconds` — 우리가 고른 값(하루 한도 100 은 `[미확인]`) |
| 되잡기 일꾼 회차 | 1분 — 감시는 3분 문(`job_gate`)을 지난 회차에만 돈다 | 같은 파일 `watch_interval_seconds` 주석 |

- 감시 화면 계약: [watch-monitoring.md](../external/watch-monitoring.md)(「3분 주기 여행 감시」 · 안전 확인 = 재난문자 · 지진).
- ☆옛 값: [활동 상세 기록](../records/reports/2026-10-15_activity_상세.md) 「재난문자API 5분 간격 폴링」(`watch.py` `ACTIVITY_GAP_MINUTES = 5.0`, 2026-10-02 구현)은 10-03 감시 주기 3분 결정 전 기록입니다. 지금 소스에는 이 상수가 없습니다(2026-10-24 검색, 남은 것은 옛 `.pyc` 뿐).

## 기상예보 API — 2026-10-24 확인

활동 팀은 예보를 **주의 문구로만** 전하고 「불가」를 만들지 않습니다. 취소 · 순연 기준은 운영 규정(`read.policy`)의 몫이고, 규정이 없으면 「규정 기준은 확인되지 않았다」고 말합니다(`team.py` `_weather_note`). 예보는 관찰이 아니라서 조회 시각(`confirmed_at`)과 예보 대상 칸(`matched_hour`)을 함께 밝힙니다.

| 무엇 | 값 | 정본 · 출처 |
|---|---|---|
| 소스 순서 | **Open-Meteo 1차 → 기상청 단기예보 대체**(`weather_provider: open_meteo`, 기본값). 1차가 못 주면 다음 소스로 값을 내고 `source` · `fell_back_from` 에 남긴다. 둘 다 실패하면 「모름」(`all_failed` 기록) | `app/core/settings.py` `weather_provider` · `ports/data_sources/base.py` · `weather_chain.py` |
| Open-Meteo | `api.open-meteo.com/v1/forecast` — 키 없음 · 시간별 기온 · 강수확률 · 강수량 · 풍속 · 하루 10,000 회(비상업, **상업 배포 전 요금제 재확인**) | `ports/data_sources/open_meteo.py` · `rate_open_meteo_per_day` |
| 기상청 단기예보 | 공공데이터포털 `VilageFcstInfoService_2.0/getVilageFcst` — 위경도 → 격자 변환, 발표 하루 8번(02 · 05 · … · 23시, 발표 약 10분 뒤 조회), 약 80시간 앞까지. 키(`ACOP_DATA_GO_KR_KEY` 또는 `ACOP_KMA_API_KEY`)가 없으면 빠지고 Open-Meteo 만 쓴다. 하루 한도 1,000 은 `[미확인]` 보수값 · DB 로 센다 | `ports/data_sources/kma.py` · `rate_kma_per_day` · `source_budget_sources` |
| 응답 재사용 | 5분(`source_cache_seconds: 300`) — 프로세스를 건너 DB 로 공유. 감시 주기(3분)보다 길어 틱 둘에 한 번 새로 받는다(계산값) | [guardrails.yaml](../../config/guardrails.yaml) `source_cache_seconds` · `source_cache_shared` |
| 주의 문구 기준 | 강수확률 **60%** 이상 · 풍속 **40 km/h** 이상 — 판정 기준이 아니라 주의 문구 기준, 우리가 고른 값(측정 아님) | 같은 파일 `travel.weather` |
| 실내 장소 | 실내면 예보를 보지 않는다. 실내외를 모르면 야외 기준으로 보고 그 사실을 경고로 적는다(비 예보뿐이면 고객에게 실내 · 야외를 묻는다) | `team.py` · 장소 `weather_sensitive` |
| 감시에서 | 감시 6종(예보 · 특보 · 재난문자 · 교통 · 대기질 · 지진) 중 **예보만 앞을 본다** — 시작이 3시간보다 멀면 나머지는 「지금 상태」라 확인 불가(`too_early`) | 같은 파일 `snapshot_hours: 3` · [watch-monitoring.md](../external/watch-monitoring.md) |

- 날씨 판정 LLM(`weather_sensitive`)은 `shadow` 다 — 고객 답은 규칙 · 예보 그대로, LLM 값은 기록만(아래 절 표).
- 한계: 주의 기준 60% · 40 km/h 는 측정에서 나온 값이 아니다. 기상청 하루 한도 · Open-Meteo 상업 요금은 확인하지 않았다. 둘 다 실패하면 서버를 끄는 판단(결정 15 뒷부분)은 사슬이 하지 않고 감시 쪽 몫으로 남아 있다(`weather_chain.py` 머리말 — `[미확보]` 2026-09-14 기준).

## 활동 판정 LLM 운영 전환 — 대체 후보 순서 `llm` (2026-10-21 사용자 결정)

결론: **대체 후보 순서만 운영(`llm`)으로 켰다.** 코드가 찾고 검증한 후보 3곳 안에서 **보여 줄 순서와 이유 문장만** LLM 이 정한다(고객 요청 · 감시 두 경로). 후보를 고르거나 빼지 않고, 실패 · 시간 초과(8초) · 예산 초과 · 쓸 수 없는 답이면 코드 순서를 그대로 낸다. 결정 [D-CS-015 「대체 후보 순서 llm」](../decisions/D-CS-015-activity-llm-judgment-on-develop.md#대체-후보-순서-llm--2026-10-21-사용자-결정).

| 판정 종류(`travel.activity_judge.kind_modes`) | 모드 |
|---|---|
| **`alternative_order` 대체 후보 순서** | **`llm`** (2026-10-21) |
| `closure` · `weather_sensitive` · `disaster_effect` · `live_status` | `shadow` — 고객 답은 규칙, LLM 값은 기록만 |
| `operating_hours` | `rule` |

- 정본: [guardrails.yaml](../../config/guardrails.yaml) `kind_modes`. **전역 `ACOP_ACTIVITY_JUDGE_MODE` 가 `rule` 이면 종류별 모드와 상관없이 LLM 을 부르지 않는다** — 코드 기본값은 `rule`, `.env.example` 은 `shadow`. 배포 서버 `.env` 값은 `[미확인]`.
- 모델 `gpt-5.4-nano`(effort low) · 지시문 v5(`prompts/activity_judge/alternative_order.v5.md` — 전시 ≠ 공연, 맞는 후보가 없으면 받은 순서) · 분류 이름 · **이유 문장 검사기**(`alternative_order.guard_reason` — 확인할 수 없는 말 · 「아니면/아님」 거꾸로 읽기 · 장소 번호 · 존댓말이 걸리면 정해 둔 문장으로 바꾸고 순서는 그대로).
- 통과 기준(완화안 2026-10-20): M2 하드 · 새 위험 0 · 위험 오답 ≤ 코드 순서, M5 이유 심각 0 · 경미 ≤ 5%(전부 사람 판정), M6 설정 오류 0 · 시간 초과 ≤ 1% · 사용률 ≥ 98%. M1 적중 등은 참고값.
- 평가 5회차 — 1회차(입력 결함) → 2회차(거꾸로 읽기 → 검사기 추가) → 3회차(검사기 문구) → 4회차(분류 혼동 · 「아님」 → v5) → **5회차 통과**: 고객 요청 holdout-5 38장 위험 0 · 심각 0 · 경미 1/85 = 1.2%, 감시 20장 위험 0 · 경미 0/51. 정리 [회차별 문제점 docx](../../../docs/activity/산출물/대체후보판정_회차별_문제점_2026-10-23.docx) · 기록 [holdout-5](../records/reports/2026-10-21_대체후보판정_holdout5_v5.md) · [holdout-4](../records/reports/2026-10-21_대체후보판정_holdout4_고객요청.md) · [holdout-3](../records/reports/2026-10-20_대체후보판정_holdout3_운영판.md) · [holdout-2](../records/reports/2026-10-20_대체후보판정_holdout2_v3.md).
- 모델 비교: `gpt-6-luna` 는 같은 자료에서 시간 초과 5/190 = 2.6%(기준 ≤ 1% 미달) · 지연 p95 5~6초라 대신하지 않는다 — [nano · luna 비교](../records/reports/2026-10-21_대체후보판정_모델비교_nano_luna.md).
- 운영 기록: `[2026-10-24]` LLM 을 부른 판정마다 코드 결과 · LLM 원래 답 · 고객에게 나간 결과를 표 `activity_llm_decisions`(308)에 남기고, `python scripts/activity/llm_decision_report.py` 로 문서를 만든다([기록](../records/reports/2026-10-24_활동LLM_운영판정기록_도구.md)). 2026-10-24 기준 운영 기록 0건(로컬 섀도 표는 10-07 평가 7줄뿐) · 서버 미확인.
- 되돌리는 조건: 운영 기록 표본 30건 중 위험한 오답 1건 또는 고객 뜻을 거꾸로 전한 이유 1건 · 단순 오답 3건 이상이면 `shadow` 로 내린다.
- 한계: 표본이 작다(고객 요청 38 · 감시 20). 5회차에는 위험 후보 사례가 없어 위험 근거는 3 · 4회차에 기댄다. v5 는 4회차 결과를 보고 만들었고 5회차로 한 번 쟀다. 겹치지 않는 holdout 장소가 거의 다 쓰였다.


## 상세 본문

[Activity 상세(구현 계획 · 결정 · 구현 현황)](../records/reports/2026-10-15_activity_상세.md) — 구현 계획(10-10) · 멘토 피드백 반영(10-08) · 신분류체계 · D-CS-016(미등록 장소 적재) · 작업자 B 구현 현황. 활동 팀 작업의 최신 상세 기록이다.

## 최근 외부 브랜치 검토

[2026-10-12 최신 3커밋·Claude 5.5 Sonnet 검토](../records/reports/2026-10-12_0414_Activity_최신3커밋_Sonnet55_검토.md) — 별도 최신 사본 수신, 관련 시험 480/480 통과. 확정 계약 우선순위·서빙 관문·취향 추천 연결은 보완이 필요하며 주 작업 브랜치 병합·운영 배포는 하지 않았습니다.

[2026-10-13 전달 8번 회신 — 예약 성립 판정의 설문 전달](../records/reports/2026-10-13_활동_전달8_설문전달_회신.md) — Case 상태에 칸을 더하지 않고 활동 팀이 그 예약이 속한 여행의 설문을 도구로 읽는다. 여행을 못 찾으면 필요할 때만 질문 하나를 다시 묻고 이번 문의에만 쓴다. 공용 도구(`read.booking` 의 `trip`)는 매니저 브랜치에 들어갔고, 활동 팀 쪽(여행 설문 읽기 · 다시 묻기 · 지난 답)은 [2026-10-14 구현 · 시험](../records/reports/2026-10-14_활동_전달8_활동쪽_구현.md)했습니다.

[2026-10-13 전달 사항(10-13) 회신](../records/reports/2026-10-13_활동_전달사항_1013_회신.md) — 3건 모두 코어 반영 · develop 에 올림(운영 상태 읽기 연결 · 팀 정기 작업 자리 — 새벽 3시 시간대 · 예약 → 여행 찾기). 활동 쪽 부탁: 원장 판정에도 운영 상태 싣기 · 꺼짐 경고 · `jobs.py` 등록 · 예산 「최대 3번」 재계산.

`[2026-10-14 코어]` **`jobs.py` 등록은 코어가 했다** — 웹 운영 확인 배치가 새벽 정기점검(03:00 시작 · 03:30 목표 · 08:00 멈춤)에서 1분마다 2~4곳씩 돈다(`instances/activity/jobs.py` · 부품은 `instances/activity/live_batch.py` 로 옮김, 스크립트 `scripts/activity/check_live_status.py` 는 손으로 돌리는 껍데기). 정기점검이 묻는 「오늘 남은 건수」(`remaining`)는 활동 팀에 묻지 않고 대상 목록에서 직접 센다(최근 6시간 안에 본 곳 제외). 연결 · 판정 LLM · 웹 예산은 조립이 꽂는다(팀 폴더는 인프라를 직접 열지 않는다 — DoD-22). 판정 LLM 이 꺼져 있으면 `disabled` 로 답하고 아무것도 부르지 않는다.

[2026-10-16 쇼핑 지점끼리 운영시간 · 휴무 옮겨 적기](../records/reports/2026-10-16_쇼핑_지점_운영시간_옮겨적기.md) — 남은 쇼핑 상세 2,761곳을 detailIntro2 만 · 표본 먼저 받고(`fill_tourapi_details --intro-only --siblings`), 같은 입점 매장(2/3) · 브랜드(90%) 지점끼리 옮겨 적는다. 옮긴 값은 `by=sibling` 추정으로 표시하고, 그 지점을 직접 받으면 TourAPI 값으로 바뀐다. 실제 호출 · CSV 쓰기는 아직 안 했다.

## 시점별 기록

[정정 전 전체 본문](../records/reports/2026-10-11_activity.md) — 날짜별 계약·검증·초안을 보존했습니다. 날짜가 붙은 결과를 오늘의 전체 통과나 운영 반영으로 읽지 않습니다. 후속 결정이 없는 계약 조항은 원문의 적용 범위를 확인합니다.

### 기존 링크 연결

<a id="왜-이것이-첫째인가"></a> [기존 절: 왜 이것이 첫째인가](../records/reports/2026-10-11_activity.md#왜-이것이-첫째인가)
<a id="무엇이-이-team-의-상품인가"></a> [기존 절: 무엇이 이 Team 의 상품인가](../records/reports/2026-10-11_activity.md#무엇이-이-team-의-상품인가)
<a id="범위--관광-분류체계로-못박는다"></a> [기존 절: 범위 — 관광 분류체계로 못박는다](../records/reports/2026-10-11_activity.md#범위--관광-분류체계로-못박는다)
<a id="-2026-09-09-레저로-좁힐까-는-잘못된-질문이었다"></a> [기존 절: ★ [2026-09-09] "레저로 좁힐까" 는 잘못된 질문이었다](../records/reports/2026-10-11_activity.md#-2026-09-09-레저로-좁힐까-는-잘못된-질문이었다)
<a id="셋을-갖는다"></a> [기존 절: 셋을 갖는다](../records/reports/2026-10-11_activity.md#셋을-갖는다)
<a id="①-검증-규칙--코드가-판정한다"></a> [기존 절: ① 검증 규칙 — 코드가 판정한다](../records/reports/2026-10-11_activity.md#①-검증-규칙--코드가-판정한다)
<a id="②-감시-소스"></a> [기존 절: ② 감시 소스](../records/reports/2026-10-11_activity.md#②-감시-소스)
<a id="-2026-09-10-감시-소스는-넓은-것부터-좁은-것으로"></a> [기존 절: ★ [2026-09-10] 감시 소스는 넓은 것부터 좁은 것으로](../records/reports/2026-10-11_activity.md#-2026-09-10-감시-소스는-넓은-것부터-좁은-것으로)
<a id="③-재계획-후보"></a> [기존 절: ③ 재계획 후보](../records/reports/2026-10-11_activity.md#③-재계획-후보)
<a id="재계획이-다른-team의-일정을-건드린다"></a> [기존 절: 재계획이 다른 Team의 일정을 건드린다](../records/reports/2026-10-11_activity.md#재계획이-다른-team의-일정을-건드린다)
<a id="manifest--실제-구현"></a> [기존 절: manifest — 실제 구현](../records/reports/2026-10-11_activity.md#manifest--실제-구현)
<a id="2026-09-25-규정-질문--activityitinerary_question"></a> [기존 절: `[2026-09-25]` 규정 질문 — `activity.itinerary_question`](../records/reports/2026-10-11_activity.md#2026-09-25-규정-질문--activityitinerary_question)
<a id="2026-09-17-case-버전의-여행-일정-관리--activityitinerary"></a> [기존 절: `[2026-09-17]` Case 버전의 여행 일정 관리 — `activity.itinerary`](../records/reports/2026-10-11_activity.md#2026-09-17-case-버전의-여행-일정-관리--activityitinerary)
<a id="business_subject--도메인이-바뀌어도-안-바꾸는-칸"></a> [기존 절: `business_subject` — 도메인이 바뀌어도 안 바꾸는 칸](../records/reports/2026-10-11_activity.md#business_subject--도메인이-바뀌어도-안-바꾸는-칸)
<a id="-2026-09-09-코드가-이-규칙을-안-지킨다"></a> [기존 절: ★ [2026-09-09] 코드가 이 규칙을 안 지킨다](../records/reports/2026-10-11_activity.md#-2026-09-09-코드가-이-규칙을-안-지킨다)
<a id="-2026-09-10-계획서가-이-규칙을-받았다--v11-4-e"></a> [기존 절: ★ [2026-09-10] 계획서가 이 규칙을 받았다 — v11 §4-E](../records/reports/2026-10-11_activity.md#-2026-09-10-계획서가-이-규칙을-받았다--v11-4-e)
<a id="-두-번-다시-이렇게-부르지-않는다"></a> [기존 절: ★ 두 번 다시 이렇게 부르지 않는다](../records/reports/2026-10-11_activity.md#-두-번-다시-이렇게-부르지-않는다)
<a id="이-team이-하지-않는-것"></a> [기존 절: 이 Team이 하지 않는 것](../records/reports/2026-10-11_activity.md#이-team이-하지-않는-것)
<a id="걸리는-것"></a> [기존 절: 걸리는 것](../records/reports/2026-10-11_activity.md#걸리는-것)
<a id="관계"></a> [기존 절: 관계](../records/reports/2026-10-11_activity.md#관계)

## 관계

- [영역 안내](index.md) — 인접 문서와 읽기 순서
