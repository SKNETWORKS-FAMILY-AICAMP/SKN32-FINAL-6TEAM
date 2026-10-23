# 일정 항목 짚기 시험 · 학습 세트 위치

2026-10-16 부터 이 세트들은 저장소 루트의 `datasets/core/pointing/` 한 곳에 있다 — `testset/`(시험에만) · `trainset/`(학습에만). 그 폴더는 git 에 올라가지 않으므로(`/datasets/` 제외 규칙, 공개 말뭉치 원문 때문) 팀이 보는 위치 목록은 이 파일이다. 세트 설명 · 규칙은 로컬의 `datasets/core/pointing/README.md` 에 있다.

스크립트는 경로를 직접 쓰지 않고 같은 폴더의 [testsets.py](testsets.py) 를 거친다 — `fixture('mix8.json')` · `fixture('all_prompts_d2.json')` 처럼 파일 이름만 주면 새 자리를 돌려주고, 옮기지 않은 파일은 예전처럼 `fixtures/` 를 돌려준다.

| 폴더(`datasets/core/pointing/…`) | 무엇인가 | 옛 이름 | 옛 자리 | 문항 수 |
|---|---|---|---|---|
| `testset/itinerary_questions_v1` | 일정 질문 11유형 — 맞는 항목 하나(또는 「없음」)를 짚는가 | 769 · mix8~12 | `fixtures/mix8~12.json` · `fixtures/gold_sets.json` | 835(요청 하나 769 + 요청 둘 66) |
| `testset/questions_plus_chitchat_v1` | 일정 질문 + 관광객 말 + 일상 잡담을 섞은 실전형 입력 | D | `results/empty_probe/all_prompts.json` · `datasets/core/pointing/legacy_runs/mixed_testset/` | 2,735 |
| `testset/chitchat_only_holdout_v1` | 새 잡담만(정답 전부 「없음」) | D2 | `results/empty_probe/all_prompts_d2.json` | 1,000 |
| `testset/synthetic_chitchat_plus_questions_v1` | 합성 잡담 240 + 정답 있는 질문 120 | D3 | `results/empty_probe/all_prompts_d3.json` | 360 |
| `testset/requests_inside_chitchat_pairs_v1` | 잡담 속 요청 문장 ↔ 잡담 뺀 같은 요청 짝 | E · MX | `datasets/core/pointing/legacy_runs/mx_testset/` | 4,014(짝 2,007) |
| `testset/confusing_trap_sentences_v1` | 일부러 헷갈리게 만든 함정 문장 + 대조 문장 | H(Hard) 시험용 | `results/hard_set/` | 합의 1,316 / 전체 1,380 |
| `trainset/confusing_trap_sentences_v1` | 위와 같은 도구로 만든 학습 자료(시험에 안 씀) | H 학습용 | `results/hard_set/` | 합의 2,534 / 전체 2,760 |

**채점법은 세트가 아니다** — 옛 A · B · C 는 같은 세트를 다르게 채점하는 방법이다: A `first_mentioned`(요청 둘이면 먼저 말한 항목) · B `any_match`(말한 항목 중 아무거나) · C `exact_set`(고른 집합이 정답 집합과 똑같아야). 정답 집합은 `itinerary_questions_v1/gold_sets.json`.

- 판은 폴더 이름 끝 `_v1` · `_v2` 로 적는다. 점수를 낸 판은 고치지 않고, 문항을 바꾸면 `_v2` 폴더를 새로 만들어 `testsets.py` 의 한 줄만 바꾼다. 판마다 만든 날 · 문항 수 · 만든 방법은 `datasets/core/pointing/README.md` 「판 기록」 표에 있다. 판마다 `manifest.json`(파일 · 크기 · SHA-256)이 있다.
- 옮기기 전후 해시 일치 — 1차 62/62 · 2차 68/68(`datasets/core/pointing/_history/`). 새 자리에서 769 C 채점 · H 보고서 · E 점검을 다시 돌려 저장된 결과와 같음을 확인했다.
- `build_hard_set.py` 는 `--split test` 면 `testset/`, `train` 이면 `trainset/` 에 쓴다. 이미 점수를 낸 파일과 이름이 겹치지 않게 새 seed · 새 판을 쓴다.
- 이 폴더 `fixtures/` 에 남은 것: 옛 개발용 세트(mix4~7 · heavy · ord2 · ord3 · wos · chat7), 분류 세트(`cls/`), 증류 학습 자료(`distill/`), 769 에서 파생한 입력(pairs_* · hints_* · gate_sents_* 등).
- GPU 서버(`server/`)의 스크립트는 서버 쪽 복사본을 읽으므로 고치지 않았다(파일 이름은 같다).
