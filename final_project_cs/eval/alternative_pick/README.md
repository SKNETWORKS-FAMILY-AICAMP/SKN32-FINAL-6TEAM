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

## 채점 기준 요약

- **보정 후(served)** = 고객 화면 1순위(실패 · 폐기면 코드 순서). **원답(raw)** = 모델 `order[0]`.
- M2 위험 = 보정 후 1순위가 금지 목록 **또는** 원답 1순위가 후보 밖. 서비스 기준(보정 후만)도 따로 낸다.
- M6 은 호출 수 기준 — 단서가 없어 운영도 부르지 않는 사례(`not_called`)는 뺀다. `valid + corrected + discarded + failed = 호출 수`.
- M8 = 섞은 판의 LLM 1순위가 원래 판 1회차와 같은 사례 비율. 어느 쪽이든 폐기 · 실패면 비교에서 뺀다(`excluded`).
- M5 는 사람 확인 전 `pending` — 전환 기준도 「확인 전」. 비용(M9)은 `activity_judge.metrics` 의 gpt-5.4-nano 요율 추정.
- 전환 기준은 holdout · 사람 라벨 · 실호출일 때만 판정, 그 밖은 「참고만」.
- `[2026-10-19 A안]` 전환 기준 = **M2 · M5 · M6b · M6e**(안전). M1 · M3 · M7 · M8 은 참고. M1 참고값은 골라야 하는 사례(`M1_discriminating` — 허용 답이 후보 일부)로 따로 내고, 뺀 사례 수(`M1_excluded_cases` — 셋 다 허용 · 없음)를 같이 적는다. 라벨 정답 칸의 `없음` → `acceptable=[]` · `no_fit=true`.

시험: `tests/unit/eval/test_alternative_pick_eval.py`(DB · 외부 호출 없음).
