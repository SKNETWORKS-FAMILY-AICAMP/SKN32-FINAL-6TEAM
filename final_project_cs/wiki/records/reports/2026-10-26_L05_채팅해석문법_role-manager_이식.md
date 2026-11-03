# L05 채팅 해석 문법 — role-manager 이식 후보 (2026-10-26)

작성 2026-10-26 KST · 기준 role-manager `a465c6022b9b4e9dcb78b0ac93b4f5a210e67b8e`(ls-remote 확인) · worktree `cache/scratch/port-l05-20261026-080737/rm` · **push 안 함**.
출처: 감사 `2026-10-26_로컬전용코드_vs_role-manager_감사.md` L05 행, 로컬 v9 source(`integ-v9-20261026-025943/source`), 3-way 기준 = 계보 pin `6c34589b`.

## 결론

- 로컬 커밋 3개를 만들었다: `83bfa1ff0`(생성 문법 + 유료 경로 스키마 분리) → `ff52d52f0`(F02) → `601bb08ab`(채팅 넣기 날짜 근거 시험).
- 빠른 관문: **9928/9928 = 100% pass**, 실패 0, skip 173(base 와 같음). base 는 9850 pass 다. 새 nodeid 는 78개이고, base 에서 빠진 nodeid 는 0개다. XML 은 `ev/gate-cand2.xml`·`ev/gate-base.xml` 에 있다.
- ruff F/E9: 바뀐 파일 전체 통과.
- 실 E4B(decide 수준): **cand 5/5 = 100%**, base 1/4 = 25%. base 는 통과하고 cand 는 실패한 행은 0개다.

## 기능별 상태

| 기능 | role-manager a465c602 | 처리 |
|---|---|---|
| temporal v7/v8 생성 문법(`_schema(message=…)` 갈래 · 인용 enum · following 기준 · `edit_intent.generation_variants`) | 없음 | 이식 |
| 범위 옮기기(T03/T04/T08/T12 — `time_ops` range) | 없음 | 이식. `stale_edit_goal` 거절을 먼저 거치게 했다(Codex) |
| T09 경계 시각 정각 시작 일정 질문(`need_time_boundary`) | 없음 | 이식 |
| T10 `spoken_minutes` 시각의 분 제외 | 있음(c286b906, 같은 코드) | 그대로 |
| T10 절대 시각 shift→start | 있음(c286b906) | 유지. v9 range 분기와 함께 둔다 |
| C02 `quoted_calendar_days` · 목록 읽기 갈래 | 없음 | 이식. 범위 `day_quotes` 도 같은 숫자 경계로 통일했다(Codex: 「11월 2일」 오인 방지) |
| 증거 실패 코드 `[evidence_validation:…]` | 없음 | 이식 |
| read_requests anyOf(general_requests 필수 · 갈래별) | 없음 | 이식(`test_read_requests` 기대 갱신) |
| F02 사실 출처 결속(이름 붙은 대상 ≠ 이웃) | `relation_dropped` 만 있음 | 결속 블록 이식 |
| 채팅 넣기 날짜 근거(add 날짜 근거) | 있음(L03 a465c602: 스키마 원문 없음 + `ground`) | 시험만 옮겼다. 원문 enum 시험 3건은 계약을 정정했다 |
| 야외/실내 `condition_is_setting`·`near_is_setting`·`_quotes_overlap` | 있음(c34bd376·1e4e3b24, 같은 코드) | 그대로(3-way 자동 일치) |
| change_explanation | — | 제외(L02 change_read) |
| prepare_decision_context | — | 제외(L04) |
| 유료 경로 스키마 원문 차단 | — | **새로 만듦**. 아래 참조 |

이식 8 · 이미 있음 4 · 새로 만듦(통합) 1 · 제외 2. 대상 13 중 처리 13 = 100%.

## 유료 경로 스키마(L03 Codex 지적 반영)

생성 문법은 고객 문장(가린 글)을 인용 `enum` 으로 싣는다. 최상위도 `anyOf` 이고, OpenAI 엄격 스키마는 최상위 `anyOf` 를 받지 않는다.

- `decision_unit._schema(plain=True)` 는 칸과 필수 목록이 같은 객체 스키마를 돌려준다. 갈래와 문장은 없다.
- `decide()` 는 받는 모델에만 `api_schema` 를 준다. 받는지는 `inspect.signature` 로 확인한다.
- `FailoverChat.structured_validated`·`structured_stream_validated` 와 `OpenAIChat` 의 같은 메서드가 유료 경로에서 그 스키마를 쓴다.
- 로컬 Ollama 는 문법을 그대로 받는다. 근거 검사(`edit_intent.validate`)는 두 경로가 같다.
- 시험은 `test_chat_decision_paid_schema.py` 다. RED(base): 4 fail / 1 pass. GREEN: 10/10 pass(관문 XML). RED 는 Codex 보완 시험 5건을 더하기 전에 잰 값이다. 이 시험은 다음을 확인한다.
  - 유료 스키마에 문장도 일정 이름도 없다.
  - 엄격 변환한 결과가 객체 모양이다.
  - 유료 답이 인용 없이 오면 거절한다.
  - 유료 전용 클라이언트도 plain 스키마를 보낸다.
- 채팅 해석 유료 넘김 계약(masked)은 바꾸지 않았다.

SYSTEM(`decision_unit.SYSTEM + edit_intent.SYSTEM`)이 바뀌었다. sha256 앞 16자리는 base `5b7074bdcf9d3e7f`(14439자)에서 cand `003a670fd9d63ead`(15629자)가 됐다. 이 변화는 실 E4B 로 재측정했다(아래).

## 시험 계약 정정(약화 아님 — Codex 판단)

- `test_date_generation`: 원문 줄 enum 시험 3건을 바꿨다. 이제 스키마에 원문이 없는지, `ground()` 가 인용 없는 날짜·시각과 원문에 없는 날짜를 버리는지 본다. L03 계약을 따른 것이다.
- `test_f02_*`: writer 투영(`basis.response`)은 L02a 묶음이다. 지금은 `basis.questions[0].unresolved == 'anchor'` 를 본다. **L02a 가 합쳐진 뒤 `needs_input` 단언을 되살려야 한다.**
- `test_decision_unsupported_actions`·`test_service_help`(rm 전용 U01 시험): 문법 갈래 전체에서 할 일을 찾는다.

## 실 E4B (decide 수준, 합성 acceptance49 문장)

조건: `tripilot-pointer:e4b-ft` digest `ef0a580a…1025`, live 러너 ctx 8192(재적재 없음), lease `port-l05` 를 받아 쓰고 반납했다. 호출은 10회다.

`travel.chat_decision_stream.max_seconds`=15 에서 첫 base 호출이 296조각을 받다가 상한에 걸려 끊겼다(29.7/s, 정상 속도). 그래서 나머지 9회는 측정용으로 `max_seconds`=60 을 썼다. 로컬 하드웨어에서는 이 상한이 해석을 끊는다. x600 은 5~7초라 해당 없다.

생성 속도는 모든 호출에서 29.6~33.4/s 였다. 하네스는 ASGI·DB 가 아니라 `e4b_probe.py` 다(decide → `ops_for`/`read_requests.reply`).

| 행 | base a465c602 | cand | 기대 |
|---|---|---|---|
| C02 「1월 2일 일정을 전부 보여줘」 | fail(목록 조회 범위 무효 DecisionFailed) | **pass** — 1월 2일 3건만 보여 줌 | answered |
| T03 「1월 2일 오전 11시 이후 … 한 시간 미뤄줘」 | 미실행(예산) | **pass** — 인사동·N서울타워 +60 | B,C shift 60 |
| T09 「… 오후 3시 이후 일정만 한 시간 미뤄줘」 | fail(근거 검증 실패) | **pass** — need_time_boundary 질문 | clarify + 경계 질문 |
| T10 「N서울타워를 오후 11시 30분으로 미뤄줘」 | pass(crosses_midnight) | **pass**(crosses_midnight) | 다음 날 무음 이동 없음 |
| F02 「N서울타워의 운영시간을 알려줘」 | fail — 인사동 운영시간으로 답함 | **pass** — 기준 일정을 되물음(anchor) | 다른 장소로 답하지 않음 |

이 결과는 decide 수준 측정이다. acceptance49 의 ASGI 경로 전체 행이 아니다. 전체 행은 runner49 overlay 가 있어야 하고, 이번에는 돌리지 않았다.

## 겹침

- L02a 작업자(`port-l07-l02a-20261026-080756/rm`, tip `2e5414727`)도 `read_requests.py` 를 고친다. 3-way 를 해 보니 충돌은 0이다.
- `trip_messages.py` 는 이번에 바꾸지 않았다.
- 다음 파일은 이 작업에서만 고쳤다: `decision_unit.py`·`edit_intent.py`·`llm_failover.py`.
  - `llm_failover.py` 는 L03 이 고친 영역과 가깝다. `structured_validated`·`structured_stream_validated` 에 인자 하나를 더했다.
- multi-change3 미커밋 후보도 `decision_unit` 을 고친다. 합칠 때 hunk 를 다시 확인해야 한다(참고만).

## 커밋·해시

| 커밋 | patch sha256 |
|---|---|
| `83bfa1ff0096a0935cb96e87e1e22c19df228024` | `33f04be6a1dfd375f4311b225ee951b783ca521b3bbeb4d63e081478f094aa37` |
| `ff52d52f0faae70ac5d3c71a009525d271d60c86` | `ca99a73f74c58a5528db79de0ac2b6301ee859fb9c38be46b6b074408692e5b6` |
| `601bb08aba8c34d67083bc3d496130ac484ee4a8` | `78d8ea3828037738b0ba0b3216345aafd9c9b5354ca255680c74ae1d1b4905ae` |
| 전체 `a465c602..601bb08a` | `22bea67856c6d65b04a66a19bfbffd694b465f151c283b9ebdbf821e44a848b8` |

변경 규모는 17 files, +1265 / −29 다. author 는 roroblack 이다.

## 남은 일

- runner49 overlay 로 ASGI 전체 행을 다시 확인한다(T01~T18, C02, F02).
- L02a 가 합쳐지면 F02 `needs_input` 단언을 되살린다.
- 로컬 `max_seconds`=15 가 해석을 끊는 문제는 L04/스트림 설정에서 따로 판단한다.
- push 는 부모가 한다. push·x600·로컬 serving 반영은 모두 아직이다.

Codex 검토 기록: `ev/codex-q1.md`·`ev/codex-a1.md`(텍스트 전용, CHANGES → 6·7·3 항목 반영).
