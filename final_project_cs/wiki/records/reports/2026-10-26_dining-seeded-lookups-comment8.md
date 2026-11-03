# Dining 지연·`place_not_from_tools` 원인 확정과 독립 후보 patch (comment8, 2026-10-26)

> 후보 폴더: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/dining-latency-20261026-012500-3532/` (patch·evidence·REPORT_KO.md). 코드 반영·push·live swap은 부모 몫이며 아직 하지 않았습니다.

## 결론
- **review→Dining 107.9초**: 79.0초(73%)가 Dining 앞에서 동기로 돈 비식사(not_meals) 대안 준비, 27.1초가 먼저 채우기와 해석 답 반영(rev2 편집)이었습니다. not_meals 대기는 v7a에 이미 들어간 comment8 순서 수정(not_meals를 Dining 뒤로 이동)으로 첫 대기 경로에서 빠졌습니다. 이번 patch는 이 구간을 바꾸지 않습니다.
- **Dining 72.0초·실패**: 로컬 E4B(tripilot-pointer:e4b-ft)가 필수 조회(find_place·check_open_at)를 **한 번도 부르지 않고** 지어낸 `call_id`("find_place 1")와 place_uid로 답했습니다. 실제 접수 `_run`은 2일 모두 tool_calls 0, turns 2(첫 답 + JSON 재요청)였고 23.15+48.70초였습니다. 검증기의 거절은 정상 동작이었습니다. 최근 E4B Dining 실행 30건 중 23건(77%)이 도구 0회였습니다(읽기 전용 DB 집계).
- **수정**: 계획에서 인자가 정해지는 규칙 1·2의 필수 조회를 모델 턴 없이 기존 `tools.call`로 먼저 실행해 대화에 실제 결과로 넣습니다. 이 기능은 로컬 어댑터(`OllamaToolChat.seed_required_lookups=True`)에서만 켜집니다. 근거 검증·턴/시간 상한·재요청 규칙은 그대로입니다.
- **합성 실모델(E4B) before/after**(같은 fixture 4회):
  - 총 시간: 250.1·244.3초 → 45.8·59.8초
  - 필수 확인 유효: 0/6=0%·2/6=33% → 6/6=100%·6/6=100%
  - 모델 호출: 11·11회 → 4·4회

## 단계별 시간
| 구간 | 사건(실제, rev2) | before(합성, v7a) | after(합성, patch) |
|---|---|---|---|
| reader | 21.473 | 범위 밖 | 범위 밖 |
| lookup | 4.259 | 범위 밖 | 범위 밖 |
| review | 0.255 | 범위 밖 | 범위 밖 |
| review→Dining | 107.854 = 먼저 채우기+답 반영 27.1 + not_meals 준비 79.0 + 0.2 | v7a 코드 순서상 27.1(not_meals가 Dining 뒤로 감) — 실측 아님, DB 시각과 코드 순서로 산출 | 변경 없음 |
| Dining 1일차 | 48.70 (도구 0, 실패) | 148.6 (10턴, 마지막 답 schema 오류) / 155.5 (open_at 2/2 evidence_other_time) | 28.4 / 39.6 (선행 4, 모델 2회, 실패 0) |
| Dining 2일차 | 23.15 (도구 0) | 101.5 / 88.8 (도구 없이 글 1200토큰 length → model_error) | 17.4 / 20.2 (선행 2, 모델 2회, 실패 0) |
| Dining 합 | 71.99 | 250.1 / 244.3 | 45.8 / 59.8 |

- 모델 호출마다 Ollama `load_duration`이 2.1~16초 붙었습니다. before 1일차 합은 45.9초였습니다. 모델이 메모리에 상주하고 prompt cache도 맞았으므로 스케줄러·동시 사용 대기로 보입니다. 인프라 쪽 잔여라 이번 patch 범위 밖입니다.
- 합성 before가 사건보다 느린 이유는 같은 원인(필수 조회를 건너뛰거나 잘못 사용)이 다르게 나타났기 때문입니다. 1일차는 한 턴에 도구 하나씩 불러 10턴을 다 썼고, 2일차는 도구 없이 글을 쓰다 출력 상한(length)에 걸렸습니다.

## 근거
- 읽기 전용 DB(구조만): `evidence/db-judge-safe.json`(dn_agent_judge, 항목 id는 해시), `evidence/db-runs-dist.txt`, `evidence/db-alts-safe.txt`(not_meals 5건이 16:14:54.9~16:16:13.9에 돌았고 Dining은 16:16:14.1에 시작).
- 실모델 4회: `evidence/real-{before1,before2,after1,after2}.json`(단계별 wall/load/prompt/eval/tool_calls), `evidence/gate.log`. 매회 lease를 잡고 풀었으며, live counters는 전후 모두 admitted 5 = completed 5로 바뀌지 않았습니다.

## patch
- `patch/dining-seeded-lookups.patch`
  - SHA256 `33e8fd33cf0128176a89e0aef4357f7e16cbe9489fe14e1a554cbc3ffdce5a9a`
  - 3 files: agent.py, tool_chat.py, 새 시험 1개
  - live source-v7a 원본에 `git -c core.autocrlf=false apply` 왕복 3/3 해시 일치
- pre SHA:
  - agent.py `e8ef7d1d…b618d`
  - tool_chat.py `851abda5…31de`
- post SHA:
  - agent.py `c5e04e38…3ebff`
  - tool_chat.py `23fafb73…fe67b`
  - test `7766c271…aec8`
- 판단을 고정한 곳(보고 대상)은 `OllamaToolChat.seed_required_lookups = True` 한 곳입니다. 기존 `retry_incomplete_final`·`supports_final_schema`와 같은 어댑터 능력 선언 방식입니다. OpenAI 경로와 `llm_direct` 비교 모드는 예전대로 동작합니다.
- 선행하지 않는 것은 다음과 같습니다.
  - 원장 밖 가게의 `live_open_check`: 바깥 조회·예산이 걸려 있어 모델이 고릅니다.
  - 속성·휴무·폐업 확인과 다시 찾기: 모델이 정합니다.
- 프롬프트 변경은 inline `SEEDED_NOTE` 한 줄입니다. 기존 `FINAL_TURN`과 같은 방식이며, 등록 프롬프트 체계 밖이라는 점도 같습니다.

## 시험
- RED(base에 새 시험만): 3 failed / 3 passed. 실패 3건은 기능 시험이고, 통과 3건은 지어낸 가게 거절·능력 없는 클라이언트·direct 모드 불변식입니다.
- GREEN 관련 묶음: **261/261 = 100%**(기존 255 + 신규 6). base 같은 묶음은 255/255였습니다.
- 확대(dining 전체 + 어댑터 70파일):
  - cand: 901 passed / 5 failed / 2 skipped (908)
  - base: 895 / 5 / 2 (902)
  - 실패 5건은 base와 같은 nodeid입니다. 분류:
    - snapshot 자료 공백 2건: `eval/datasets/*.jsonl`이 snapshot에 없습니다.
    - social_dining 3건: 메모리 Conn에 `cursor` 없음 / 404. 이 patch와 무관한 기존 실패이고 범위 밖이며, 수정하지 않았습니다.
- 격리: DB·외부 차단 runner입니다. 실행 root는 `DLAT_TEST_ROOT`로 출력했습니다. 절대경로로 base RED를 돌렸을 때 cand 코드가 import된 잘못된 실행은 `evidence/red-invalid-imported-cand/`에 보존했습니다.

## 하지 않은 것
- live 8042·3100 kill/재시작, push, 실고객 DB 쓰기, 비교 DB 쓰기는 모두 0회입니다. 실제 고객 원문은 쓰지 않았고 합성 fixture만 썼습니다.
- 비교 DB·실제 pipeline 전체로 review→Dining 구간을 실측하지는 않았습니다. 이 구간은 DB 시각과 코드 순서로 산출한 값입니다.
- 첫 답이 `found`를 빠뜨려 기존 JSON 재요청이 매일 1회 더 드는 문제, Ollama load 2~16초/호출은 잔여 과제입니다.
