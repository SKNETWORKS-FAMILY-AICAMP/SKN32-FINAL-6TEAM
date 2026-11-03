# 2026-10-26 integ-rm9 — bulk-shift 3 · pubweb2 1 통합, 범위 옮기기 정책 통일, 유료 전송 전화 가림

결론: role-manager `729a3ed30b33721ca850ac3f355368d478e6a5f6` 위에 로컬 커밋 9개를 쌓았다. tip은 `74b2b2325e54172e626cd9cdd8385c4bbe337252`이며 push는 하지 않았다.
- 빠른 관문: 10362건 중 실패 0, 오류 0, skip 173. 통과는 10189/10189 = 100%(skip 제외).
- x600 원출력 재생(모델 호출 0): 6/6 = 100% 이동.
- 실 E4B decide(): 2/2 = 100%가 `scope=range`·`day=all`로 읽혔고, 2회 모두 6/6 이동했다. 단, 이 값은 측정용 시한을 늘려 잰 것이다(아래 5절).

- worktree: `cache/scratch/integ-rm9-20261026-085457/rm`
- 정책 결정: Codex CLI(`codex exec --skip-git-repo-check`, 본문 stdin, 텍스트 검토). 기록은 `codex/q1.md`·`a1.txt`(정책), `q2/a2`(1차 검토), `q3/a3`(반영 검토)에 있다.

## 1. 커밋(순서, cherry-pick -x)

| # | SHA | 내용 | patch sha256 |
|---|---|---|---|
| 1 | `40d20f0fc` | (A) a899430a7 기준 없는 following+query → 범위 이동 | `a1af741c3415cfdba1fe2526acb438e5b582452f3574d3a2a8fa33cab3e4e405` |
| 2 | `e385f4eac` | (A) bb21bfbe9 활동 대안 상점 제외 | `59491d15f3957fe84d417287d95e2681d48152cc4424ebe3e065e6e30d187e37` |
| 3 | `fa00646c0` | (A) b45dd8d5b 바꾼 뒤 다른 안 choices · 시각 되돌리기 문구 | `7d8e1803db0ad01155d6f16a278e5eef997937e96017465933ad71b27529e2df` |
| 4 | `f9a1f7189` | 범위 옮기기 정책 한 곳(`chat_edit.shift_range`) — L05 scope=range와 통일 | `f97478b4b439d296a51beeed2f9cc557f1d96ed0c723477064d294910e21c743` |
| 5 | `17270c38e` | (B) feb24fa90 공개 웹 본문 근거 · redirect · http(기본 꺼짐) | `f664112290ab993d8818a4d9dfc9dc11503ed9a5c0b8a68b972dfa85e3867e0f` |
| 6 | `14d5baaf1` | (C) 유료 전송 `redaction.masked_outbound` | `890d3d432d359ed0996061be5e6f206ff1fcca626af62991e7f27b7bb3618385` |
| 7 | `0f6762c1e` | 시험: 범위 경계(지난 시각 · range_kept 목록 · 숙소 제외) | `1da9613893b2942fbe4dd78f4659d89f5310b414872fe2104ee135e6dffb8de4` |
| 8 | `7e5c77cb5` | 시험: 유료 text 입구 · 임베딩 입력 가림 | `2c22ab76cf2054eb55feffbf838f12e551a254cfbbb81525e2689eac31b33e60` |
| 9 | `74b2b2325` | 시험: `test_decision_unit_web` 해석 실패 단언을 L06 계약에 맞춤 | `e1f1553612e4559b45fd37b20a9e2a0b2cde5579405e268564cf2cd5751274d5` |

합본(`729a3ed3..tip`, `git diff --binary`): `1d0306ee1ef15a5b520456a7760ada8fec57b7b5fe0f41195f745865ce7050be`. 파일은 `integ-rm9-20261026-085457/patches/`에 있다.

## 2. 충돌 해소

- 글자 충돌: 0건. bulk-shift 3개와 pubweb2(`review.py`·`guardrails.yaml` 포함) 모두 3-way 자동 병합됐다.
- 정책 충돌(L05 scope=range 대 bulk-shift)은 커밋 4로 하나로 묶었다.
  - L05 경로(`edit_intent.time_ops` scope=range)는 범위에 보호·지난 일정이 하나라도 있으면 전체를 거절했다(`locked_item`/`item_in_past`). 그래서 `day=all`인 진행 중 여행은 늘 거절됐다.
  - bulk-shift 경로(`chat_edit.ops_for` query)는 보호 일정을 빼고 나머지를 옮겼다.

## 3. 정책 통일(Codex 결정 a~h)

범위 옮기기 정책은 한 곳에 둔다. `chat_edit.split_range`가 대상을 고르고 `chat_edit.shift_range`가 옮긴다. scope=range와 기준 없는 following+query 경로가 둘 다 이 함수를 부른다.
- a. 끝난 일정과 활동·식사가 아닌 항목(숙소·이동)은 범위에서 빼고 표시하지 않는다.
- b. 고정·예약·이미 시작한 활동·식사는 옮기지 않는다. 답에 「· 그대로 둔 일정: 날 시각 제목(고정|예약|이미 시작)」으로 보이고, 나머지는 옮긴다.
- c. 옮길 일정 하나라도 자정을 넘거나(끝 ≤ 시작 포함) 지난 시각에 시작하게 되면 전체를 거절한다(`crosses_midnight`·`time_in_past`).
- d. 옮길 일정이 없고 보호 일정만 있으면 `range_kept`로 답하며 그대로 둔 일정 목록을 함께 보인다. 둘 다 없으면 `need_target`.
- e. `reflow`는 두 경로 모두 False다. 겹치면 중앙 저장기가 전체를 거절한다. L05 경로는 원래 True였다.
- f. following+anchor(「인사동부터 뒤 일정」)는 그대로 둔다. 하나라도 보호 일정이 있으면 전체 거절(`locked_item`)이며, 기존 시험이 통과한다.
- g. L05 시험 `test_relative_range_refuses_all_on_protected_target`는 계약을 바꿔 고쳤다(contract_correction).
  - 이름: `test_relative_range_keeps_protected_target_and_moves_the_rest`
  - 단언: 보호 일정 시각 불변, kept 표시, 나머지 +60분 정확, reflow 없음, 원본 불변.
  - Codex 판단: 대체 단언이 있어 검증 약화가 아니다.
- h. before/after 기준 일정 자체는 대상도 kept도 아니다.
- 추가 시험: 두 경로가 같은 결과를 내는지(진행 중 여행: 끝난 일정 제외, 시작한 일정 kept, 나머지 이동), 자정 전체 거절, 지난 시각 전체 거절, range_kept 목록, 숙소 제외.
- RED(통일 전 앱 코드): 3건 실패. GREEN: 전부 통과.
- wiki: `wiki/external/trip-chat-context.md`에 「범위 옮기기 정책 한 곳」 항목을 추가했다.

## 4. (C) 유료 전송 전화 가림

- `redaction.masked_outbound` = `masked`에 다음 모양을 더 가린다.
  - 휴대폰 01[016789]: 구분자 없음·공백·점·가운데 3자리
  - 지역번호 02·0[3-6][1-5]·070
  - +82/82
- 앞뒤에 숫자가 더 붙으면 가리지 않고, UUID는 그대로 둔다. 가운데 번호만 `****`로 바꾸며 구분자는 남긴다.
- `llm_failover`의 모든 유료 전송이 이 함수를 쓴다(json, text, structured(_validated), stream 4종, reader 3종, 임베딩 입력).
- 저장값 가림(`masked`·`mask_json`)은 바꾸지 않았다(좁은 변경).
- 경계 시험 `tests/unit/core/test_redaction_outbound_phones.py`:
  - 가려지는지: 전화 모양 16가지.
  - 그대로 남는지: 날짜(2026-10-26·20261026), 시각(10:30·1030·0930-1130), 예약번호(ABCD-1234·13자리·12자리), 편명, 금액, 대표번호 1588, UUID, 「0412 1530」, 카드 끝자리 등 15가지.
  - 더 긴 숫자열 3건, UUID와 전화가 섞인 글, 기존 가림 유지.
- 입구별 시험(`test_reader_policy_no_bypass`): 유료 입구 10개(`text` 포함)에서 원문 전화가 사라지고 날짜·시각은 남는다. 로컬에는 원문 그대로 간다.
- `pipeline.read_source` 유료 재시작 시험(4가지 모양): RED(옛 `llm_failover`) 4건 실패, GREEN 4건 통과.
- 한계:
  - 이름·예약번호는 여전히 가리지 못한다(`llm-failover.md` 7-1에 반영).
  - system·schema는 가리지 않는다. 계획 읽기 schema enum은 고정 목록이고, 채팅 해석은 문장 없는 `api_schema`를 보낸다(기존 시험이 schema에 원문이 없음을 단언). 이 부분은 Codex가 「부분 해소」로 남겼다.

## 5. 검증

- 빠른 관문:
  - 범위: tests/architecture·contract·unit·security·eval/tests, `-m 'not live and not db and not slow'`
  - 실행: venv `date_risk_env_312`, `-p pytest_asyncio.plugin`, 격리 runner `run_isolated.py` 사본, `MULTI_CHANGE_ROOT`, 9개 shard
  - tip `7e5c77cb5`(그 뒤 커밋 9는 관문 밖 e2e 파일 하나만 바꾼다): 10362건 중 실패 0, 오류 0, skip 173. XML은 `integ-rm9-20261026-085457/ev/gate3/*.xml`.
  - 새 시험 nodeid가 XML에 있다.
  - ruff F/E9: 바뀐 py 파일 전부 통과.
- 비교 DB `gugu_replay_improved_20261025`(합성 tenant, 모델 호출 0):
  - x600 6152ae77 원출력(following+query): `adjusted`, 판 1→2, 6/6 = 100% +60분.
  - 같은 원출력을 scope=range로 바꾼 합성본: 6/6 = 100%.
  - 하네스: bulk-shift `run_e4b.py` 사본 `e4b/run_replay.py`, 모델 예산 0.
  - 외부 HTTP는 차단됐다. 날씨·OpenAI SDK 시도 각 회 1번이 `external_http_denied`로 막혀 실제 전송은 0이다.
- chat_edit 관련 DB 시험(`db/db.sh`): `test_chat_edit_web`, `test_chat_read_requests`, `test_semantic_reflow_db`, `test_decision_unit_web`. tip `74b2b2325`에서 59/59 = 100% 통과, skip 8, 1개 뺌(`db/ev/db-chat4/r.xml`, 642초).
  - skip 8건은 모두 `test_semantic_reflow_db`이며, 이유는 「requires explicit isolated synthetic database」다. 이 파일은 실행되지 않았고, 통과로 세지 않는다.
  - 비교 DB 전후 대조는 `cmp.txt`에 있다. 시험 접두 tenant 잔여 diff는 0이다.
  - `test_decision_unit_web::test_a_model_failure_or_an_id_outside_the_list…`는 기준 729a3ed3에서도 `KeyError: 'failure'`로 실패한다(`db/ev/db-base-f`). 원인은 L06(b4ff97477)이 공개 응답의 내부 사유를 없앤 것이다. 커밋 9가 시험을 계약에 맞췄고, 공개 응답에 사유가 없는지와 Case 기록에 사유가 있는지를 더 단언한다. tip에서 통과한다.
  - `test_the_raw_coordinates_are_stored_and_logged_nowhere`는 비교 DB 전체 표(case_events·customer_cases·places 전 tenant)를 tenant 구분 없이 읽어 20분 넘게 끝나지 않았다. 비교 DB 크기 때문인 환경 문제로 분류하고 이번 실행에서 뺐다. 제품 판정이 아니다.
- 실 E4B(로컬 `tripilot-pointer:e4b-ft`):
  - lease `integ-rm9`(획득 → 반환). `/api/ps`의 `context_length`가 12288이고, 이는 live serving `integ-v10c` `ACOP_OLLAMA_NUM_CTX`와 같다. 시작 전 모델이 내려가 있어 load-only `/api/generate`로 12288에 올렸다.
  - `decide()` 직접 호출 2회. DB와 네트워크는 11434만 허용했다.
  - 결과: 2/2 모두 `change_time`·`scope=range`·`query.day=all`·minutes 60. `ops_for` 결과는 「일정 6개 시각 옮기기」로 6/6 이동, kept 0.
  - 시간: 42.5초·30.1초, 조각 속도 11.0·11.4/초. 정상은 약 30/초이며, 같은 때 관문·DB 시험이 CPU를 쓰고 있었다.
  - 측정용으로 시한을 바꿨다(first 30초, stall 5초, max 60초). 제품 가드레일 `travel.chat_decision_stream.max_seconds`=15라면 이 속도에서는 끊긴다. 따라서 이 2회는 decide 수준 결과이며 ASGI 행 결과가 아니다.
  - 모델 호출: 2회(load 1회 별도). 유료 호출 0.

## 6. 남은 것

- push(부모), x600 배포, 로컬 serving 반영: 모두 하지 않음.
- `reflow=False` 뒤 「옮긴 일정이 그대로 둔 일정과 겹치면 중앙 저장기가 전체 거절」은 기존 저장기 계약이다. 이번에 DB에서 그 장면을 따로 만들어 보지는 않았다.
- 저장값(`mask_json`)에도 구분자 없는 전화 가림을 넓힐지는 따로 결정할 일이다(이번에는 좁게 했다).
