# plan_qa_bench — 고객 질문이 가리키는 일정 항목 찾기, 모델 비교 실험

2026-09-29 실험의 **코드·시험 문제·작은 결과·서버 실행 기록**이다. 결과 해석은
[여행일정_질문인식_모델비교_2026-09-29.md](../../research/여행일정_질문인식_모델비교_2026-09-29.md) 가 정본이다.

## 폴더

| 폴더·파일 | 무엇 |
|---|---|
| `recog_v2.py` | 규칙(날짜·시간대·시각·종류) + 임베딩 + 별칭 색인으로 항목을 찾는 인식기(v2·v3·v4). LLM 없는 방식 |
| `plan_qa_match.py` · `plan_qa_nollm.py` | 초기 비교(지금 코드 vs 임베딩 vs LLM) — 이 안에 **사람이 쓴 질문 38개**(`Q`, `HELD`)가 들어 있다 |
| `eval_v2.py` · `eval_v4.py` | 인식기 v2·v3·v4 판정(개발용/시험용 분리) |
| `eval_llm.py` | LLM 번호 짚기 1차 비교(gemma4:12b, 두 번·순서 바꿔·규칙 되확인) |
| `eval_rerank.py` | 재평가 모델 1차(bge 계열 2종) 판정 — 옛 파일 이름을 읽는다 |
| `eval_models.py` | **최종 판정 스크립트** — 서버 결과(`llm_out.json`, `emb_rr_out.json`)를 같은 기준으로 표로 낸다 |
| `server/` | 서버(GPU)에서 돌린 코드. `llm_point2.py`(LLM 번호 짚기), `emb_rr.py`(임베딩·재평가 점수), `pipeline*.sh`(모델을 줄 세워 받고·재고·지운 순서) |
| `fixtures/` | 시험 문제. `codex_qset.json`(Codex 작성 일정 1개 + 질문 100개), `codex_qset2.json`(새 질문 40개), `job.json`(서버에 올린 묶음), `codex_brief_*.md`(Codex 의뢰문) |
| `results/` | 모델이 고른 번호(`llm_out.json`)와 서버 실행 기록(`server_pipeline*.log`) |

## 저장소에 없는 것 (재현 방법)

| 파일 | 왜 없나 | 어디에 있나·다시 만드는 법 |
|---|---|---|
| `pairs.json` · `scores.json` · `emb_rr_out.json` | 커서(0.5~0.85MB) — 질문·항목 쌍 3,498개와 모델이 매긴 점수 | 로컬 `datasets/travel/plan_qa_bench/raw/` (깃 제외). 다시 만들려면 `server/emb_rr.py` |
| `kakao_cats.json` | 카카오 장소 검색이 준 분류 이름(장소 약 30개) — 카카오 약관상 공용 저장소에 두지 않는다 | 로컬 데이터 폴더에만. 다시 받으려면 카카오 키워드 검색 API 로 각 장소의 `category_name` |
| `alias_cache.json` | 위 분류로 모델이 만든 별칭 색인 | 로컬 데이터 폴더에만. `recog_v2.RecognizerV3` 가 없으면 다시 만든다 |
| 관광공사 소개글 | 창작물이라 저장하지 않는다(2026-09-28 결정). v4 실험에만 쓰였고 효과가 없었다 | 보관하지 않음 |

## 다시 돌리려면

`eval_*.py` 는 한 작업 폴더(`SP`)에 아래처럼 놓여 있다고 가정하고 `python eval_models.py <SP>` 로 돈다.

```
<SP>/recog_v2.py  plan_qa_match.py  plan_qa_nollm.py  eval_*.py
<SP>/codex_qset.json  codex_qset2.json          ← fixtures/
<SP>/kakao_cats.json  alias_cache.json           ← 로컬 데이터 폴더
<SP>/rerank_job/job.json  llm_out.json           ← fixtures/ · results/
<SP>/rerank_job/pairs.json  emb_rr_out.json      ← 로컬 데이터 폴더
```

- `plan_qa_match.py` 가 저장소의 `app.modules.travel_ops` 를 불러오므로 `final_project_cs/` 에서 실행한다.
- 로컬 올라마(`127.0.0.1:11434`)에 `bge-m3` · `gemma4:12b` 가 있어야 한다(임베딩·별칭 만들기).
- 서버 쪽은 GPU 서버에 `server/` 를 올려 `pipeline*.sh` 순서대로 돌렸다. 서버 주소·접속 정보는 이 저장소에 적지 않는다.
