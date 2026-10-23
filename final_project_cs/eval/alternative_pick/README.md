# 대체 후보 1순위 판정 — 실행 · 채점 도구

> 작성 2026-10-17 · 계획: `docs/activity/대체 후보 3곳 중 최적 장소 판정 — LLM 테스트 계획.md` · 사례 원본: `../situation_cards/`

| 파일 | 하는 일 | 외부 호출 |
|---|---|---|
| `build.py` | 상황 카드(결합본) + 작성자 문장 + 합의 라벨 → `cases.jsonl` · 매니페스트(해시 둘: 입력 · 전체) | 없음 |
| `run.py` | 사례마다 운영 함수(`alternative_order.preference_inputs · payload · schema · apply`)로 부르고 관측을 `results.jsonl` 에 한 줄씩 | **있음**(`--dry-run` 이면 없음) |
| `score.py` | 관측 + 사례 → M1~M9 · 묶음별 · 전환 기준(`summary.json`), M5 사람 확인 시트 | 없음 |

## 순서 (final_project_cs 에서)

```
python -m eval.alternative_pick.build --labels eval/situation_cards/labels/<합의본>.json   # 문장 · 라벨이 다 모인 뒤
python -m eval.alternative_pick.run --cases eval/alternative_pick/cases.jsonl             # 80 × 3 + 40 × 2 = 320회
python -m eval.alternative_pick.score eval/reports/alternative_pick/<run>
python -m eval.alternative_pick.score eval/reports/alternative_pick/<run> --export-reasons # → reasons_review.csv
python -m eval.alternative_pick.score eval/reports/alternative_pick/<run> --reasons <채운 시트>.csv
```

- 도구 점검만: `build --smoke`(템플릿 문장 + 분류 태그 초안) → `run --cases …/cases_smoke.jsonl --dry-run` → `score`. **smoke 수치는 쓰지 않는다** — holdout 카드의 후보라 이것으로 프롬프트를 고치면 holdout 을 본 셈이다.
- 끊기면 `run --resume eval/reports/alternative_pick/<run>` — 남은 관측만 부른다.
- 라벨만 고쳤으면 다시 부르지 않고 `score <run> --cases <새 cases.jsonl>` (입력 해시가 같아야 한다).
- 지시문 기본은 DB 등록 프롬프트(`--prompt db`, 감사 기록). 등록 전이면 시작 전에 멈춘다. `--prompt file` 은 `prompts/activity_judge/alternative_order.v*.md` 최신판.

## 감시 경로 판 — `watch.py` (2026-10-19)

감시 루프가 연 Case 는 고객 문장이 없다(10-19 결함 수정 뒤 LLM 은 설문 + 고객 답만 받는다 — `alternative_order.customer_words`).
동결 holdout(`cases.jsonl`)은 고치지 않고, 같은 후보 · 설문에 `customer_text=None` 인 사례(`L-xx-W`)를 따로 만든다.

| 나눔(운영과 같은 기준) | 10-19 판(동결 `cases_watch.jsonl` · 실행 20261019T144241Z) | 10-20 뒤 |
|---|---|---|
| 취향 칸 없음 — 운영도 안 부름 | 24 · 사례에서 뺌 | 59(아래 우선순위만 33 + 중복 2 포함) |
| 우선순위만 | 33 · 규칙 라벨(셋 다 허용 · 위험 없음 · 코드 순서 유지 기대) | **없음** — `[2026-10-20 사용자 결정]` 우선순위를 LLM 에 넘기지 않는다(`alternative_order.SURVEY_FIELDS`). 10-19 실행에서 4/99 가 우선순위를 취향으로 읽고 순서를 바꿨다 |
| 취향 설문 있음 | 21 · **사람 라벨**(`situation_cards_watch`) | 21 그대로 |
| 입력이 같아 뺌 | 2(L-69 = L-10 · L-76 = L-70) | 0(둘 다 우선순위만이라 안 부름으로 감) |

★10-19 실행 결과는 우선순위를 넘기던 때 값이다. 고친 뒤 값을 내려면 사람 라벨 21건으로 판을 다시 만들어(`build --watch --watch-labels …`) 다시 잰다.
고객 요청 경로 holdout v2(20261019T075053Z)도 우선순위를 넘기던 때 값이다.

```
python -m eval.human_review export situation_cards_watch --out 라벨_감시_이름.csv      # 21행, 2인 블라인드
python -m eval.human_review apply situation_cards_watch 라벨_감시_이름.csv --reviewer 이름 --out-dir eval/situation_cards/labels
python -m eval.alternative_pick.build --watch --watch-labels eval/situation_cards/labels/<합의본>.json   # → cases_watch.jsonl
python -m eval.alternative_pick.run --cases eval/alternative_pick/cases_watch.jsonl
```

- 라벨 전 도구 점검: `build --watch --draft`(사람 라벨 자리를 셋 다 허용으로, 수치로 쓰지 않음).
- 채점 결과의 `by_path` 가 `chat` · `watch:rule` · `watch:human` 을 따로 낸다. `watch:rule` 의 M4 = 「우선순위만 받았을 때 순서를 지키나」.

## dev 38 · holdout-2 39 (2026-10-20)

`대체 후보 판정 — 허용 기준과 성능 향상 테스트 계획.md` 2절. 둘 다 holdout 80 과 원래 장소 · 후보가 겹치지 않는다.

| 자료 | 만드는 것 | 문장 · 라벨 | 쓰는 곳 |
|---|---|---|---|
| dev 38(`cases_dev.jsonl`) | `python -m eval.alternative_pick.dev` — 카드 틀 40 중 38(L-53 · L-54 못 묶음) | 템플릿 · 규칙 라벨 | v2 · v3 비교(20261020T023547Z · 023855Z) |
| holdout-2 39(`situation_cards/cards_llm_bound_h2.jsonl`) | `python -m eval.alternative_pick.holdout2 --allow-partial` — dev 가 안 쓴 틀 40 중 39(L-50 못 묶음) | **사람 문장**(`write_by_작성자N_h2.csv`) · 2인 라벨 예정 | v3 최종 판정(1회) |

- 결합은 `dev.bind_fresh`(운영 화면 3곳). holdout-2 는 그것으로 못 묶은 16장(C · D 대부분)을 **운영 순위 상위 10곳**에서 골랐다(`holdout2.bind_top10` · 카드 `candidates_by`) — 결과를 경로별로 따로 볼 수 있다.
- 실행 옵션: `run --prompt file --prompt-file alternative_order.v3.md --class-names`(v3 = E1 분류 이름 + E2 이유 규칙 + E3 받은 순서). 운영은 아직 v2 · 분류 이름 끔.
- ★`[2026-10-20]` holdout-2 판정 뒤 v3 지시문을 `prompts/activity_judge/` 로 옮기고 운영이 분류 이름을 싣게 했다(kind_modes 는 shadow 그대로). 다음 실험판은 `eval/alternative_pick/prompts/` 에 둔다 — `prompts/` 에 두면 등록 스크립트가 가장 높은 판을 운영에 켠다.

## dev 스트레스 · 이유 문장 지킴이 (2026-10-20)

- `python -m eval.alternative_pick.stress` → `cases_dev_stress.jsonl`(54건): dev 카드에 「A 아니면 B」 · 「B 말고 A」 · 「조용한 A」 문장을 기계로 붙인다(규칙 라벨 · 비교용).
  ★「말고」 꼴은 A · B 가 겹치는 조합(「실내 말고 전시」)을 거르지 않는다 — 그 위험 판정은 사례 결함이다.
- 운영 `alternative_order.apply(…, customer_text=, classes=)` 가 이유 문장 지킴이(`guard_reason`)를 거친다 — 실행기도 같다.
  그래서 지킴이 이전 실행 결과의 이유는 지킴이를 거치지 않은 문장이다.

## 채점 기준 요약

- **보정 후(served)** = 고객 화면 1순위(실패 · 폐기면 코드 순서). **원답(raw)** = 모델 `order[0]`.
- M2 위험 = 보정 후 1순위가 금지 목록 **또는** 원답 1순위가 후보 밖. 서비스 기준(보정 후만)도 따로 낸다.
- M6 은 호출 수 기준 — 단서가 없어 운영도 부르지 않는 사례(`not_called`)는 뺀다. `valid + corrected + discarded + failed = 호출 수`.
- M8 = 섞은 판의 LLM 1순위가 원래 판 1회차와 같은 사례 비율. 어느 쪽이든 폐기 · 실패면 비교에서 뺀다(`excluded`).
- M5 는 사람 확인 전 `pending` — 전환 기준도 「확인 전」. 비용(M9)은 `activity_judge.metrics` 의 gpt-5.4-nano 요율 추정.
- 전환 기준은 holdout · 사람 라벨 · 실호출일 때만 판정, 그 밖은 「참고만」.
- `[2026-10-19 A안]` 전환 기준 = **M2 · M5 · M6b · M6e**(안전). M1 · M3 · M7 · M8 은 참고. M1 참고값은 골라야 하는 사례(`M1_discriminating` — 허용 답이 후보 일부)로 따로 내고, 뺀 사례 수(`M1_excluded_cases` — 셋 다 허용 · 없음)를 같이 적는다. 라벨 정답 칸의 `없음` → `acceptable=[]` · `no_fit=true`.

시험: `tests/unit/eval/test_alternative_pick_eval.py`(DB · 외부 호출 없음).
