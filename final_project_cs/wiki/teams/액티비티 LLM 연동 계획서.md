# 액티비티 LLM 연동 계획서

> 브랜치 `role-activity-test` — 활동팀(Activity Team)의 규칙 판정 코드를 **GPT-5.4 nano + 웹 실시간 검색** 판정으로 바꾸는 실험.
> LLM 구현과 관련한 결정·변경·실측은 이 파일 맨 아래 **「업데이트 기록」**에 날짜순으로 적는다.

## 1. 요약

계산으로 답이 정해지는 판정(남은 시간, 정원, 취소 기한·위약금)은 **코드에 그대로 둔다.**
지금 정규식이나 키워드로 **글을 해석하는 판정 네 가지**와 **새로 추가하는 실시간 운영 상태 판정**만 LLM으로 맡긴다.
처음에는 **섀도 모드**로 시작한다. 규칙과 LLM을 함께 돌리되 고객 답변은 규칙 결과로 만들고, 둘이 다르게 판정한 경우만 기록한다.
일치율과 정확도를 잰 뒤에 LLM 결과를 답변에 쓸지 정한다.

## 2. 확정된 결정 (2026-10-06, 사용자)

| 항목 | 결정 |
|---|---|
| 1차 교체 범위 | 정기휴무 해석 · 운영시간 원문 해석 · 실내·실외 추정 · 재난문자 관련성 + **실시간 운영 상태(새 판정)** |
| 시작 모드 | **섀도 모드** (`activity_judge_mode = shadow`) |
| 어댑터 위치 | 기존 `app/infrastructure/llm/openai.py` 는 고치지 않는다. Responses API 어댑터를 **새 파일**로 만든다 |

## 3. 사전 확인 사항

- **GPT-5.4 nano**
  - Responses API에서 `web_search` 도구를 지원한다.
  - Structured Outputs를 지원한다.
  - reasoning effort는 `none`(기본)·`low`·`medium`·`high`·`xhigh` 중에서 고른다.
  - 가격은 1M 토큰당 입력 $0.2, 캐시 입력 $0.02, 출력 $1.25다.
  - 출처: [OpenAI 모델 문서](https://developers.openai.com/api/docs/models/gpt-5.4-nano), [웹 검색 가이드](https://developers.openai.com/api/docs/guides/tools-web-search)
- **지금 구현은 Responses API를 쓰지 않는다.**
  - OpenAI 호출은 모두 `chat.completions.create` 다: `app/infrastructure/llm/openai.py:76`, `app/modules/travel_ops/feedback.py:109`, `eval/` 스크립트들.
  - 나머지는 임베딩 호출(`embeddings.create`)이다.
  - 설치된 SDK는 `openai==2.44.0` 이다(`requirements.txt:59`).
- **원칙과 충돌한다.**
  - 지금 코드는 「판정은 계산으로 한다. LLM 을 부르지 않는다(v10 §4-D)」를 전제로 한다(`activity/team.py:7`, `activity/feasibility.py:4`, `activity/alternatives.py:5`).
  - 그래서 결정 문서 [D-CS-008](../decisions/D-CS-008-activity-llm-judgment-experiment.md) 을 올렸다(RULE.md §2-3, draft).
- **스파이크 실측 결과 (2026-10-06)** — 근거: [스파이크 실측](../records/evidence/2026-10-06_액티비티_LLM_스파이크_실측.md)

  | # | 질문 | 결과 |
  |---|---|---|
  | 1 | `temperature`·`seed` 를 받는가 | `temperature` 는 effort=none 일 때만 받는다. `seed` 는 400 오류(Unknown parameter) → **재현성을 seed로 확보할 수 없다** |
  | 2 | effort=none 에서도 `web_search` 가 되나 | 된다. json_schema 와 함께 써도 된다 |
  | 2' | json_schema 를 강제하면 `url_citation` 주석이 오나 | **오지 않는다(0건).** 대신 `include=["web_search_call.action.sources"]` 로 받은 출처 목록과 대조하면 5/5건 일치 |
  | 3 | 웹 검색 요금 | $10.00 / 1k calls + 검색 내용 토큰은 모델 요율. 호출 1회에 검색이 2~5번 일어나 **건당 약 $0.02~0.04(추정)**. `open_page` 도 과금 단위인지는 확인 필요 |
  | 4 | 지연 | effort=low + web_search 5회: 6.92·7.60·9.27·20.10·27.99초(p50 9.27초). **5회 중 2회가 가드레일 20초를 넘었다** |
  | + | 같은 입력에 같은 판정이 나오나 | 아니다. 같은 질의 8회 중 `open` 6회, `unknown` 2회 |

## 4. 교체 범위

| 판정 | 지금 위치 | 방침 | 이유 |
|---|---|---|---|
| 이미 시작됨 · 정원 초과 · 시각 모름 | `feasibility.py:359` | 코드 유지 | 숫자 비교라 LLM이 더할 것이 없다 |
| 취소 기한 · 위약금율 | `cancellation.py:651` | 코드 유지 | 금액을 틀리면 손해가 생긴다. 구조화된 조건이 이미 있다(D-CS-006) |
| ① 정기휴무 요일 일치 | `feasibility.py:545` | **LLM** | 정규식은 `매주 X 휴무` 만 읽는다. 「매월 둘째 주」, 「공휴일 다음날」 같은 표현을 놓친다 |
| ② 운영시간 원문 | `feasibility.py:420` | **LLM** | 지금은 원문을 전달만 하고 판정에 넣지 않는다 |
| ③ 실내·실외 추정 | `weather.py:572`, `csv_places` 분류 | **LLM** | 키워드나 분류에 걸리지 않으면 `None` 이 된다 |
| ④ 재난문자 관련성 | `feasibility.py:441` | **LLM** | 지금은 등급만 보고 「지역·주제 관련성은 확인하지 않았다」고 경고만 남긴다 |
| ⑤ 실시간 운영 상태 (새 판정) | 없음 | **LLM + 웹 검색** | 임시휴무, 행사 취소, 공사 같은 공지를 확인한다 |
| 대체 장소 운영 확인 | `alternatives.py:78,144` | 2차 대상 | 후보마다 호출하면 비용과 지연이 커진다 |

## 5. 구조

```
ActivityTeam (feasibility / weather …)
   └─ build_judge(mode, judge_llm) → ActivityJudge      ← activity/judge/modes.py
        ├─ RuleJudge      지금 함수를 그대로 감싼 것         ← judge/rule.py
        ├─ ShadowJudge    규칙으로 즉시 답 + LLM 은 백그라운드, 차이는 로그   ← judge/modes.py
        └─ LLMFirstJudge  LLM 으로 답, 호출 실패면 규칙(llm_fallback_rule)  ← judge/modes.py
             └─ LLMJudge  요청 → 모델 → 코드 검증(인용·출처)        ← judge/llm.py
                  └─ OpenAIResponsesJudgeLLM   ← app/infrastructure/llm/openai_responses.py
요청은 judge/requests.py 가 만든다(날짜 사실은 코드가 계산). 값 집합은 judge/types.py.
```

`[2026-10-06, 3단계]` 판정 종류와 허용 값(모든 종류에 `unknown` 이 있다):

| 종류 | 값 | 웹 | 인용 검증 대상 |
|---|---|---|---|
| `closure` 정기휴무 | `closed` · `not_closed` · `unknown` | 끔 | `restdate_text` |
| `operating_hours` 운영시간 | `within` · `outside` · `unknown` | 끔 | `usetime_text` |
| `weather_sensitive` 실내·실외 | `outdoor` · `indoor` · `unknown` | 끔 | 없음 (이름으로 추정) |
| `disaster_effect` 재난문자 | `blocks` · `no_effect` · `unknown` | 끔 | 문자 본문. 0건이면 `no_effect` 에 인용이 필요 없다 |
| `live_status` 실시간 운영 상태 | `open` · `closed` · `unknown` | 켬(설정) | 출처 목록 대조 |

- `not_closed` 는 「열려 있다」가 아니라 「원문상 휴무로 잡히지 않는다」는 뜻이다.
- 요청에 공휴일 여부는 넣지 않는다(`is_public_holiday: null`). 그래서 공휴일 예외가 걸린 원문은 `unknown` 이 맞다.

### 5.1 설정

- `settings` 에 두는 값
  - `activity_judge_mode`: `rule | shadow | llm`, 기본값 `shadow` (이 브랜치 한정)
  - `activity_judge_model`: 기본값 `gpt-5.4-nano`
  - `activity_judge_web_search`: 웹 검색 사용 여부
  - `activity_judge_reasoning_effort`: reasoning effort
- `config/guardrails.yaml` 에 두는 값: 판정별 시간 제한, 호출 예산
  - 가드레일 수치는 한 곳에만 둔다(CLAUDE.md §3).
  - 기존 `reliability.llm_call_timeout_seconds` (20초)를 웹 검색 호출에도 그대로 쓸지는 실측 후 정한다.

### 5.2 어댑터 — `openai_responses.py` (새 파일)

- 호출 형태: `client.responses.create(model=…, input=…, tools=[{"type": "web_search"}] (선택), text={"format": json_schema}, reasoning={"effort": …}, include=["web_search_call.action.sources"])`
- `temperature`·`seed` 는 넘기지 않는다. `seed` 는 400 오류를 내고, `temperature` 는 effort=none 일 때만 받기 때문이다(스파이크 Q1).
- 반환값: 파싱한 판정, 웹 검색 출처 목록(`action.sources`), 검색 호출 수, 입력·출력 토큰 수, 지연 시간
- 기존 `OpenAITeamLLM` 과 겹치는 두 부분은 같은 폴더의 공용 함수로 빼서 두 어댑터가 함께 쓴다. 기존 동작은 바꾸지 않는다.
  - `prompts` 테이블에서 활성 프롬프트를 읽는 부분
  - `record_llm_call` 감사 기록

### 5.3 출력 스키마 (모든 판정에 공통)

```json
{
  "verdict": "open|closed|indoor|outdoor|relevant|irrelevant|unknown",
  "confidence": 0.0,
  "reason": "…",
  "quotes": ["입력 원문에서 그대로 옮긴 구절"],
  "citations": [{"url": "…", "title": "…", "quote": "…", "published_at": "…"}]
}
```

### 5.4 코드가 맡는 뒤처리

「모름」을 「없음」이나 「성립」으로 읽지 않는다는 원칙은 LLM 쪽에서도 지킨다.

1. **인용 검증:** `quotes` 가 입력 원문에 실제로 없으면 `unknown` 으로 내린다. `place_hours.py` 의 `HoursRead`(`method: rule|llm`, `dropped`) 패턴을 재사용한다.
2. **출처 검증:** 웹 근거로 판정했다면 `citations[].url` 이 그 호출의 `web_search_call.action.sources` 목록에 있어야 한다. 하나도 없으면 `unknown` 으로 내린다. 게시 날짜가 오래된 근거도 `unknown` 으로 처리한다.
   - `[변경 2026-10-06]` 처음에는 `url_citation` 주석으로 검증하려 했다. 그런데 json_schema 를 강제하면 이 주석이 0건이라 출처 목록 대조로 바꿨다(스파이크 Q2').
3. **실패 대비:** 시간 초과, 스키마 위반, 429 응답이면 RuleJudge 결과로 돌아가고 실패 코드를 남긴다. 2026-09-14에 크레딧이 소진된 적이 있다.
4. **확정 불가 보호:** LLM이 코드가 확정한 불가(정원 초과, 이미 시작)를 「성립」으로 뒤집을 수 없다.

### 5.5 근거와 프롬프트

- **근거(evidence)**
  - 웹 결과는 `source_id="web_search"` 로 남긴다.
  - URL, 짧은 인용, 조회 시각만 저장하고 본문 전체는 저장하지 않는다.
  - 카카오 값을 다룬 방식과 같다(`place_lookup.py`).
- **프롬프트**
  - `prompts/activity_judge/<판정>.v<N>.md` 에 둔다. 프롬프트 키는 `activity_judge.<판정>` 이 된다.
  - `[변경 2026-10-06]` 처음에는 `prompts/judge/` 에 두려 했다. 그런데 그 폴더는 평가용 판정 프롬프트(`judge_v*.txt`)가 이미 쓰고 있고, 프롬프트 키는 폴더 이름에서 만들어진다(`app/tools/read_tools.py:703`). 그래서 폴더를 따로 쓴다.
  - 키를 `ALLOWED_PROMPT_KEYS`(`app/tools/read_tools.py:686`)에 넣어야 등록된다. 빠지면 실제 호출이 「no active prompt」로 멈춘다(`tests/unit/test_prompt_key_registration.py`). 3단계에서 함께 넣는다.
  - 기존 `prompts` 테이블(`prompt_key`, `active`)에 등록한다.

### 5.6 섀도 모드 동작

- 각 판정 지점에서 RuleJudge와 LLMJudge를 함께 실행한다.
- 고객 답변, `decisions`, 실패 코드는 **RuleJudge 결과만으로** 만든다. 지금 동작과 같다.
- `[변경 2026-10-06]` 차이 기록은 **DB 표 `activity_judge_shadow`(마이그레이션 031)에 남긴다**(A안, 사용자 결정). 같은 내용을 `INFO` 로그(`acop.activity.judge_shadow`)로도 남긴다. 앱에 로깅 설정이 없어 로그만으로는 운영에서 아무 데도 남지 않았기 때문이다. 기록 함수는 조립(`composition.build_activity_judge_shadow_sink`)이 넣고, 쓰기에 실패해도 판정은 그대로 가며 실패만 `WARNING` 으로 남긴다. 담는 항목:
  - Case id, capability, 판정 종류, 규칙 결과, LLM 결과
  - 일치 여부, 인용·출처 검증에서 탈락했는지
  - 지연 시간, 토큰 수
- 로그에 담지 않는 것: 좌표, 장소명, 고객 문장 (`team.py:_record_failure` 와 같은 기준)
- LLM 호출이 실패해도 고객 응답에는 영향을 주지 않는다.
- `[추가 2026-10-06]` 웹 검색 호출은 20초를 넘을 수 있다(스파이크 Q4에서 5회 중 2회). 섀도 판정이 고객 응답을 늦추지 않게 하는 방법으로 두 가지를 검토했다.
  - (가) 응답을 먼저 보내고 섀도 판정은 백그라운드로 돌린다 — **채택 (2026-10-06, 2단계)**
  - (나) 섀도 판정에 별도 시간 제한을 두고, 넘으면 결과를 버리고 `llm_timeout` 만 기록한다 — 채택하지 않음
  - 고른 이유: Controller 는 Case 하나에 Team 을 한 번 실행하고 그 결과로 답한다. 그래서 (나)를 고르면 시간 제한만큼 고객 응답이 늦어진다. 섀도 모드는 「고객 응답에 영향 없음」이 전제라 (가)만 그 전제를 지킨다. (나)로는 늦은 호출의 지연도 잴 수 없다.
  - 감수하는 것: 프로세스가 끝날 때 돌던 섀도 판정은 잃는다. 실험 표본이 조금 줄 뿐 고객 응답에는 영향이 없다.
  - 시간 제한은 `reliability.activity_judge_call_timeout_seconds: 45` (우리가 고른 값)다. 백그라운드 실행 자체는 3단계 `ShadowJudge` 에서 만든다.

## 6. 단계별 작업

| 단계 | 내용 | 예상 |
|---|---|---|
| 1. 결정 문서 · 스파이크 ✅ 2026-10-06 | `D-CS-008` 초안(테스트 브랜치 한정, v10 §4-D의 예외 범위, 되돌리는 조건). nano + web_search를 직접 호출해 §3의 「확인 필요」를 실측하고 `wiki/records/evidence/` 에 남긴다 | 반나절 |
| 2. 어댑터 ✅ 2026-10-06 | `openai_responses.py`, 공용 함수 분리, settings·guardrails 키 추가, `composition.py` 주입 | 1일 |
| 3. Judge 계층 ✅ 2026-10-06 | `RuleJudge`(지금 함수 4개를 감쌈 — 기존 시험이 그대로 통과해야 함), `LLMJudge`, `ShadowJudge`, 뒤처리 검증기. `failure_codes.py` 에 `llm_timeout` · `llm_schema_invalid` · `llm_uncited` · `llm_fallback_rule` 추가와 `DESCRIPTIONS` 갱신 | 1~2일 |
| 4. 판정 연결 ✅ 2026-10-06 | `_feasible_operating` · `_guess_weather_sensitive` · `_feasible_disaster` 가 judge를 부르게 한다. 새 단계 `_feasible_live_status`(웹 검색)를 추가한다. 비용을 줄이려고 실외이거나 시작까지 72시간 안일 때만 호출한다 | 2일 |
| 5. 평가 ✅ 2026-10-06 | 골든셋 약 60건을 만들어 아래 지표를 잰다 | 1~2일 |
| 6. 기록 · 전환 판단 | `wiki/records/reports/` 에 리포트를 내고 wiki에 결론 한 줄을 적는다. 평가 수치를 보고 `shadow → llm` 전환 여부를 결정한다 | 반나절 |

**5단계 평가 세부**

- 골든셋 출처: 기존 시험 사례 + 휴무 표현이 다양한 TourAPI 실제 원문
- 지표
  - 규칙 대비 일치율
  - 정답 라벨 대비 정확도
  - `unknown` 비율
  - 인용·출처 검증 탈락률
  - p95 지연
  - 건당 비용
- 표기: RULE §1.4에 따라 분모, 모델, seed, 프롬프트 버전, 데이터셋 해시와 bootstrap 95% CI를 함께 적는다. 3회 반복한다.
- 시험 위치
  - 단위 시험은 가짜 judge로 네트워크 없이 돌린다.
  - 실호출 시험은 `tests/live/` 에 두고 마커로 분리한다.

## 7. 위험 요소

- **지연 (실측됨):** 웹 검색 호출의 p50은 9.27초이고, 5회 중 2회가 20초를 넘었다. §5.6 (가)에 따라 섀도 판정은 고객 응답 경로 밖(백그라운드)에서 돈다.
- **재현성 (실측됨):** seed를 쓸 수 없고 같은 입력 8회 중 판정이 두 가지로 갈렸다. 평가는 3회 이상 반복하고, 판정이 회차마다 바뀌는 비율도 지표에 넣는다.
- **웹 정보 신뢰도:** 오래된 블로그 휴무 공지를 근거로 삼을 수 있다. 게시 날짜를 요구하고, 오래된 근거는 `unknown` 으로 처리한다. 실측에서 `published_at` 은 3회 중 1회만 채워졌다. `[정함 2026-10-06, 3단계]` 날짜가 없는 근거는 **버리지 않고** `undated_citations` 로 센다. 버리면 거의 모두 「모름」이 되기 때문이다. 게시일이 `travel.activity_judge.citation_max_age_days`(180일, 우리가 고른 값)보다 오래되면 버린다.
- **비용 (추정):** 건당 약 $0.02~0.04이고 거의 전부 검색 요금이다. ⑤번 판정은 호출 조건(실외 또는 72시간 이내)으로 제한한다.

## 8. 전환 조건 (섀도 → LLM)

판정 종류별로 따로 정한다. 기준 수치는 5단계 평가 결과를 보고 이 파일에 적는다. 그 전에는 `shadow` 를 유지한다.

`[초안 2026-10-06 — 사용자 확정 전]` 5단계 리포트의 제안이다. 확정 전까지는 모든 종류가 `shadow` 다.
- 라벨을 사람이 검토했다.
- 골든셋에서 LLM 의 위험한 오답이 규칙보다 적고, 정확도 차이(LLM − 규칙) CI 하한이 0보다 크다.
- 운영 섀도에서 그 종류의 비교 가능 관측이 100건 이상이고, 불일치 표본을 사람이 검토해 LLM 이 맞은 비율이 규칙보다 높다.
- 웹 판정(`live_status`)은 라벨 셋과 429 대책이 생길 때까지 대상이 아니다.

---

## 업데이트 기록

LLM 구현과 관련한 결정·변경·실측을 날짜순으로 적는다. 항목마다 근거(파일:줄번호, 리포트·evidence 링크)를 붙인다.

### 2026-10-06
- 계획서를 만들었다.
- 1차 범위는 「LLM」 네 가지 + 실시간 운영 상태로 정했다(사용자 결정).
- 섀도 모드부터 시작한다(사용자 결정).
- Responses API 어댑터는 새 파일로 만들기로 했다.
- 사전 확인: 저장소의 OpenAI 호출은 전부 Chat Completions 또는 임베딩이고, Responses API를 쓰는 곳은 없다(`legacy/` 제외 검색).
- **1단계 완료.**
  - 결정 문서 [D-CS-008](../decisions/D-CS-008-activity-llm-judgment-experiment.md)(draft)을 올렸다.
  - 스파이크를 실측했다. 근거: [실측](../records/evidence/2026-10-06_액티비티_LLM_스파이크_실측.md), [리포트](../records/reports/2026-10-06_1540_Activity_LLM_1단계_스파이크_리포트.md)
- 실측으로 바꾼 설계
  - 출처 검증을 `url_citation` 에서 `web_search_call.action.sources` 대조로 바꿨다(§5.4).
  - 어댑터는 `temperature`·`seed` 를 넘기지 않는다(§5.2).
  - 섀도 판정을 고객 응답 경로에서 분리한다(§5.6).
- 남은 확인
  - `open_page` 동작도 웹 검색 과금 단위에 들어가는지
  - 지연 p95 (n=5라 아직 산출하지 않았다)

### 2026-10-06 (2단계)
- **2단계 완료 — Responses API 어댑터와 배선.** 근거: [실측](../records/evidence/2026-10-06_액티비티_LLM_2단계_어댑터_검증.md), [리포트](../records/reports/2026-10-06_1650_Activity_LLM_2단계_어댑터_리포트.md)
- 바꾼 코드
  - 새 어댑터 `app/infrastructure/llm/openai_responses.py` (`OpenAIResponsesJudgeLLM.judge()` → `JudgeCall`). 웹 검색을 켜면 `include=["web_search_call.action.sources"]` 로 출처 목록을 받는다. `temperature`·`seed` 는 넘기지 않는다. 응답을 읽을 수 없으면 `JudgeResponseError` 를 낸다.
  - 공용 함수 `app/infrastructure/llm/_registry.py` (`load_active_prompt`, `write_audit`, `AuditWriteError`). `openai.py` 는 이것을 쓰도록 바꿨고 동작은 그대로다.
  - 설정 `activity_judge_mode`(기본 `shadow`)·`activity_judge_model`·`activity_judge_reasoning_effort`(기본 `low`)·`activity_judge_web_search`(기본 켬). `.env.example` 에 주석으로 적었다.
  - 가드레일 `reliability.activity_judge_call_timeout_seconds: 45`
  - 배선: `composition.build_activity_judge_llm()` → `ActivityTeam.judge_llm`. 운영 조립 경로에서만 넣고, 모드가 `rule` 이거나 키가 없으면 `None` 이다.
- 정한 것
  - 섀도 판정은 백그라운드로 돌린다(§5.6 (가)).
  - 프롬프트 폴더는 `prompts/activity_judge/` 로 한다(§5.5).
- 시험 결과
  - 단위·계약·LLM 통합 시험: 1917 passed, 73 skipped. 기준선 1896 passed에 새 시험 21건이 더해진 수다.
  - 실호출 시험(`-m live`) 1건: 1 passed

### 2026-10-06 (3단계)
- **3단계 완료 — 판정 계층.** 근거: [실측](../records/evidence/2026-10-06_액티비티_LLM_3단계_판정계층_검증.md), [리포트](../records/reports/2026-10-06_1800_Activity_LLM_3단계_판정계층_리포트.md)
- 바꾼 코드
  - 새 패키지 `app/modules/travel_ops/activity/judge/`: `types` · `requests` · `rule` · `llm` · `modes`. 구조와 값 집합은 §5에 있다.
  - 프롬프트 `prompts/activity_judge/*.v1.md` 다섯 개. `ALLOWED_PROMPT_KEYS` 에 등록했다.
  - 실패 코드 `llm_timeout` · `llm_schema_invalid` · `llm_uncited` · `llm_error` · `llm_fallback_rule` 를 추가했다. `llm_error` 는 계획에 없던 코드로, 429·키 없음·네트워크 오류를 가른다.
  - 가드레일 `travel.activity_judge.{citation_max_age_days: 180, shadow_max_workers: 2, shadow_max_pending: 16}` (모두 우리가 고른 값)
  - 어댑터 오류를 표준 예외로 바꿨다: 시간 초과 → `TimeoutError`, 읽을 수 없는 응답 → `ValueError` 계열. 판정 계층(`app/modules`)이 `openai` 를 import 하지 못하기 때문이다.
- 정한 것
  - 게시일이 없는 웹 근거는 버리지 않고 센다(§7).
  - LLM 모드에서는 **호출 실패**(시간 초과·스키마·그 밖)일 때만 규칙 판정으로 대신한다. 근거 검증에서 떨어지면 「모름」으로 두고 규칙으로 덮지 않는다.
  - 섀도 판정이 밀려 상한을 넘으면 그 판정을 건너뛰고 `activity_judge_shadow_skipped` 로 기록한다.
- 로컬 개발 DB(`127.0.0.1:5433/acop_cs`)에 새 프롬프트 5개를 등록했다(`python -m scripts.register_prompts`). 계약 시험 `test_active_prompts_are_the_deployed_set.py` 가 DB 등록을 요구한다. **다른 환경도 같은 명령을 한 번 돌려야 한다.**
- 실호출 점검(DB 프롬프트 + 실제 모델, 6건)
  - 공휴일 예외가 있는 둘째 주 화요일 휴무 → `unknown`. 규칙은 `not_closed` 였다.
  - 계절별 운영시간 → `within`. 규칙은 해석하지 않는다(`unknown`).
  - 다른 지역의 위급재난 문자 → `no_effect`. 규칙은 `blocks` 였다.
  - 경복궁 실시간 상태 → `open`. 인용 URL 이 출처 목록과 일치했다.
- 시험 결과
  - 2000 passed, 73 skipped. 2단계 1917 passed에서 83건이 늘었다. 판정 계층 64 · 어댑터 2 · DB 프롬프트 계약 5 · 파일마다 도는 기존 검사 12.
  - Team 은 아직 판정 계층을 부르지 않는다(4단계). 그래서 고객 답변은 바뀌지 않았다.

### 2026-10-06 (4단계)
- **4단계 완료 — 성립 판정이 판정 계층을 거친다.** 근거: [실측](../records/evidence/2026-10-06_액티비티_LLM_4단계_판정연결_검증.md), [리포트](../records/reports/2026-10-06_1930_Activity_LLM_4단계_판정연결_리포트.md)
- 판정 지점 (`app/modules/travel_ops/activity/feasibility.py`)
  - `_feasible_operating`: 휴무(`closure`)와 운영시간(`operating_hours`). 휴무 원문이 없으면 부르지 않는다.
  - `_feasible_disaster`: 재난문자(`disaster_effect`). 문자가 0건이면 부르지 않는다.
  - `_guess_weather_sensitive`: 실내·실외. DB 값이 있으면 부르지 않는다.
  - 새 단계 `_feasible_live_status`: 실시간 운영 상태(웹). 판정 LLM 이 있고, 실외이거나 시작 72시간 안일 때만 부른다.
- **주소는 CSV 장소 목록에서 가져온다(사용자 결정).** `source_content_id` → `activity_total_data.csv` 의 `addr1`·`addr2`. 경복궁 실측: 「서울특별시 종로구 사직로 161 (세종로)」.
- 섀도 모드: 고객 결과는 규칙 모드와 **완전히 같다.** LLM 이 모든 판정에서 반대로 답하게 한 시험 5개 시나리오에서 결과 전체(답변·decisions·근거·경고·실패 코드)가 일치했다.
- LLM 모드에서만 일어나는 일
  - LLM 판정이 결과에 들어간다(`*_judged_by: "llm"`, 근거 `activity.judge.<kind>`).
  - 새 실패 코드: `live_closed`(웹 공지상 휴무), `outside_hours`(운영시간 밖). 둘 다 장소 때문으로 보고 대체 장소를 찾는다(`replacement._blocked_by_place`).
  - 재난문자를 LLM 이 판정하지 못하면(모름) 등급 기준(지금 규칙)으로 막는다. 모름을 「막지 않음」으로 읽지 않는다.
- 가드레일 `travel.activity_judge.live_status_within_hours: 72` (우리가 고른 값)
- 실측에서 찾은 것
  - 실제 모델로 섀도를 돌렸더니 처음에는 다섯 판정이 모두 `llm_error` 였다. 원인은 시험 작업의 `run_id` 가 `agent_runs` 에 없어 감사 기록이 외래 키에 걸린 것이다.
  - 운영 경로는 Controller 가 `agent_runs` 를 먼저 만들므로 해당하지 않는다(`case_service.py:41`). 판정 LLM 이 들어가는 경로도 Controller 를 거치는 조립뿐이다.
  - 다만 로그만으로는 원인을 몰랐다. 그래서 섀도 로그에 예외 종류(`llm_error`)를 남기도록 고쳤다.
- 실측 결과 (경복궁, 내일 14시, 부산 침수 위급재난 문자)
  - 고객 답변은 0.01초 만에 규칙 결과(위급재난 → 불가)로 나갔다.
  - 백그라운드 판정 5건은 11.1초 뒤에 끝났다. 휴무·실내외는 규칙과 일치했고, 재난문자는 **LLM 이 `no_effect`(다른 지역)로 규칙과 달랐다.** 운영시간은 `within`, 실시간 상태는 `open`(출처 1)이었다.
- 시험 결과
  - 단위·계약·LLM 통합: 2016 passed, 73 skipped. 3단계 2000 passed에서 16건 늘었다(연결 시험 14 · 섀도 로그 2).
  - 여행 시험 1370건은 손대지 않고 그대로 통과했다.
  - 통합·시나리오·e2e: 614 passed, 8 failed. 실패 8건은 RAG 시험이고, 로컬 DB 에 OpenAI 임베딩이 적재되지 않은 환경 문제다(「openai 제공자의 벡터 칸이 비어 있다」). 이번 변경과 무관하다.

### 2026-10-06 (섀도 기록 위치 — A안)
- **결정: 섀도 기록은 DB 전용 표에 모은다(사용자 결정, A안).** 근거: [실측](../records/evidence/2026-10-06_액티비티_LLM_섀도기록_표_검증.md), [리포트](../records/reports/2026-10-06_2030_Activity_LLM_섀도기록_표_리포트.md)
- 이유: 앱에 로깅 설정이 없다(`app/`·`scripts/` 에 `basicConfig`·`dictConfig`·파일 핸들러 0건). 그래서 `INFO` 섀도 로그는 운영에서 사라지고, LLM 비용만 나가고 비교는 남지 않았다.
- 표: `activity_judge_shadow` (`app/infrastructure/db/migrations/031_activity_judge_shadow.sql`)
  - 칸은 섀도 로그와 같다. 여기에 `tenant_id`, `origin`(`live`·`eval`), 평가용 `eval_run`·`eval_case`·`eval_repeat` 를 더했다.
  - `run_id`·`case_id` 에 외래 키를 걸지 않는다. 4단계에서 감사 기록이 외래 키에 걸려 판정이 통째로 버려진 일이 있었다.
  - 장소명·원문·판단 이유는 싣지 않는다. 저장소 함수가 정해진 칸만 쓰므로 다른 키가 섞여 와도 버려진다.
- 쓰기 경로: `composition.build_activity_judge_shadow_sink()` → `ActivityTeam.judge_shadow_sink` → `ShadowJudge` 의 sink. 백그라운드 스레드에서 쓰므로 고객 응답은 늦어지지 않는다.
- 로컬 개발 DB 에 031 을 적용했다(두 번 적용해 재실행 안전을 확인). **다른 환경은 `python -m app.infrastructure.db.migrate` 를 돌려야 한다.**
- 실측: 실제 모델로 섀도 실행 1회 → 표에 5행이 쌓였고, 종류별 일치율을 SQL 한 줄로 집계했다. 점검 행은 지웠다.
- 시험: 2183 passed, 74 skipped, 1 failed. 실패 1건은 `acop_composer` 미설치로 원래부터 깨져 있던 시험이다. 새 시험은 sink 4건 · 배선 1건 · DB 왕복 4건(롤백 트랜잭션)이다.

### 2026-10-06 (5단계)
- **5단계 완료 — 골든셋 평가.** 근거: [실측](../records/evidence/2026-10-06_액티비티_LLM_5단계_평가_실측.md), [리포트](../records/reports/2026-10-06_2130_Activity_LLM_5단계_평가_리포트.md)
- 골든셋: `eval/activity_judge/` 60건(라벨 52), sha256 `5a0c98e5…`. **라벨은 작성자(Claude)가 달았고 사람 검토 전이다.**
- 원문 해석 네 판정 (gpt-5.4-nano · effort low · v1 프롬프트 · 3회 · 항목 군집 부트스트랩)
  - LLM 정확도 0.987 (154/156) [0.962, 1.000], 규칙 0.462 (24/52) [0.327, 0.596]
  - 차이 +0.526 [0.391, 0.654]
  - 위험한 오답: LLM 2/156, 규칙 13/52
- LLM 위험한 오답 2건은 모두 closure-06 이다. 「법정공휴일」 조건을 무시했다. 요청에 공휴일 여부가 없다(`is_public_holiday: null`).
- 실시간 판정(라벨 없음)
  - 성공 16/24. 8건은 429.
  - 회차 간 일관성 3/8, 지연 p50 15.7초 · p95 40.7초, 성공 건당 약 $0.032.
  - 부분 휴관(온실만 휴관 등)에서 판정이 갈렸다.
- **429:** 웹 판정은 호출 1건이 17k~30k 토큰이라 몰리면 분당 한도에 걸린다(동시 6이면 24/24 실패).
- **규칙 결함 발견:** 정기휴무 정규식이 CSV 원문 「매주 X」 309건 중 307건을 놓친다(운영 동작). → [결함 리포트](../records/reports/debugs/2026-10-06_1610_정기휴무_규칙이_매주X_원문_307건을_놓친다.md) (미해결, 결정 필요)
- §8 전환 기준 초안을 적었다(사용자 확정 전).

### 2026-10-06 (직접 돌려 보기 스크립트)
- `scripts/try_activity_judge.py` 를 추가했다. 원하는 입력으로 Activity Team 성립 판정을 끝까지 돌린다.
  - 입력: 장소 이름(CSV 에서 찾음), 시각, 휴무·운영시간 원문, 재난문자, 예보
  - 보여 주는 것: 고객 결과와, 판정 종류별 규칙 대 LLM 비교 · LLM 이유 · 인용 · 출처
  - 모드: `shadow`(기본) · `llm` · `rule`
  - 기록: 섀도 기록 표에 `origin='eval'`, `eval_run='try-…'` 로 쓴다. 운영(`live`) 집계에 섞이지 않는다.
  - 시험: `tests/unit/test_try_activity_judge_script.py` (규칙 모드, 네트워크 없음, 4건)
- 실행해 보고 찾은 것(경복궁, 10/12 월, 휴무 원문을 일부러 「매주 월요일」로 넣음)
  - 규칙 모드: 「성립: True」. 정기휴무 정규식 결함이 그대로 드러났다(결함 리포트 2026-10-06_1610).
  - 섀도 모드: 고객 결과는 규칙 그대로 나갔다. 뒤에서 LLM 은 휴무를 `closed`, 다른 지역 재난문자를 `no_effect` 로 판정해 규칙과 달랐다.
  - **LLM 모드에서 답변이 서로 어긋났다.** 「휴무 안내에 따르면 이 날짜는 휴무입니다」와 「웹 공지상 이 날짜는 정상 운영으로 확인됩니다」가 한 답변에 함께 나왔다. 원문 해석과 웹 판정이 엇갈릴 때 무엇을 앞세울지 규칙이 없다. → 열린 항목
  - **웹 판정이 프롬프트 지시를 어겼다.** 프롬프트는 「일반적인 정기휴무 안내만으로 판정하지 않는다」고 하는데, 모델이 「휴궁일은 화요일이니 월요일은 정상 운영」으로 추론해 `open` 을 냈다. 이유 문장에는 「확정은 어렵습니다」라고 쓰면서도 판정은 `open` 이었다. 출처가 검색 목록에 있어 검증은 통과했다. → 프롬프트 v2 후보

### 2026-10-06 (정기휴무 규칙 결함 — 별도 브랜치에서 수정)
- **결정(사용자):** 결함은 `develop` 에서 수정 브랜치 `fix/activity-closure-rule` 을 따서 고친다. worktree 경로는 `../SKN32-FINAL-6TEAM-fix-closure`. 공휴일 조회 도구(`read.holiday`)를 붙이는 데 문제가 없는지도 검토했다.
- 수정: 새 공용 함수 `closure_rules.read_closure` 를 성립 판정과 대체 장소가 함께 쓴다. CSV 「매주 X」 누락은 307 → 0건이 됐다. 못 읽은 원문은 이제 「모름」이다.
- **결함 리포트를 이 브랜치에서 그 브랜치로 옮겼다**(`wiki/records/reports/debugs/2026-10-06_1610_…`, 상태 「해결됨」). 위 5단계 기록과 리포트의 링크는 그 브랜치가 `develop` 에 합쳐진 뒤 이 브랜치로 들어오면 다시 이어진다.
- 공휴일 조회 검토 결과
  - **운영 키가 특일 서비스에 미등록(403 「등록되지 않은 서비스키」)이라 지금은 늘 「모름」이다.** data.go.kr 활용신청이 필요하다.
  - 도구 예산은 최대 9/12 라 괜찮다.
  - 실패를 캐시하지 않아, 소스가 멈추면 성립 점검 한 번에 최대 +8초가 걸린다.
  - 명절 「당일」 판정은 가정에 기대고 있고 실측하지 못했다(사흘이 같은 이름으로 온다는 가정).
- **LLM 실험과의 관계**
  - `develop` 을 이 브랜치로 합칠 때 `feasibility._feasible_operating` 에서 충돌이 난다.
  - 합친 뒤에는 섀도 비교 기준(RuleJudge 휴무)이 새 규칙으로 바뀐다. 5단계 평가의 규칙 쪽은 다시 재야 한다(LLM 비용 없음). 수정된 규칙으로 잰 골든셋 휴무는 16/16(낙관적 — 골든셋을 본 뒤 만든 규칙).

### 2026-10-06 (fix/activity-closure-rule 병합)
- 수정 브랜치 `fix/activity-closure-rule`(`f1b3836`)을 이 브랜치에 병합했다. 그 브랜치가 `origin/develop`(`2f3594a`)에서 분기했기 때문에 그 사이 `develop` 커밋(식당 팀 PR #34 등)도 함께 들어왔다.
- 충돌은 `feasibility._feasible_operating` 한 곳이었다. 이렇게 풀었다:
  - 휴무는 **판정 계층을 그대로 거친다**(섀도·LLM 모드 유지).
  - 계층 안의 규칙 판정(`RuleJudge._closure`)이 새 `closure_rules.read_closure` 를 쓴다.
  - 성립 판정이 `read.holiday` 로 물은 공휴일 사실을 휴무 요청에 싣는다(`judge_requests.closure(…, holidays)`). 규칙과 LLM 이 같은 사실을 본다.
  - LLM 에는 `is_public_holiday` 와 `known_holidays` 로 간다. 5단계에서 LLM 이 틀린 유일한 원인(closure-06, 공휴일 정보 없음)이 해결될 자리다. 다만 특일 키가 403 이라 실제 효과는 키를 해결한 뒤에 난다.
- 시험 조정
  - 「규칙이 『매월 둘째 주』를 못 읽는다」를 전제로 한 실험 시험 2건을 고쳤다.
  - 섀도 차이 시험은 아직 규칙이 놓치는 「다른 지역 위급재난 문자」로 바꿨다.
  - 공휴일 사실 전달 시험 1건을 추가했다.
- 결과: 2247 passed, 74 skipped(실패 0), `ruff check .` 통과.
- **섀도 비교 기준이 바뀌었다** — 골든셋 규칙 점수(LLM 호출 없이 다시 잼, 작성자 라벨)
  - 전체: 24/52 → 33/52
  - 휴무: 7/16 → 16/16 (위험한 오답 9 → 0). 골든셋을 본 뒤 만든 규칙이라 낙관적이다.
  - 운영시간 · 실내외 · 재난문자는 그대로다(3/14 · 6/10 · 8/12, 재난문자 위험한 오답 4).
  - 그래서 휴무 판정에서는 LLM 의 이점이 사라졌다. LLM 0.958 vs 규칙 1.000. 휴무를 `llm` 모드로 올릴 이유는 지금 없다.
