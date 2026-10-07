# 장소 찾기 평가 — 기준선 v0 (2026-10-07)

시험지 `eval/datasets/place_lookup_v1.jsonl`(34건, sha `place_lookup.dataset_digest()`) · 채점 `eval/runners/place_lookup.py` · 규칙 시험 `eval/tests/test_place_lookup.py`.

## 다시 재는 법

```powershell
cd final_project_cs
$env:ACOP_DATABASE_URL="postgresql+psycopg://postgres@127.0.0.1:5433/dining_rebuild"; $env:PYTHONPATH="$PWD;$PWD\..\final_project_sample"; $env:PYTHONUTF8="1"
.\.venv\Scripts\python.exe -m eval.runners.place_lookup --label v1-<무엇을-바꿨나> --out eval\reports\<날짜>_place_lookup_v1.json
```

★카카오는 실제로 부른다(응답 저장 금지 — `kakao_local.py` 약관). 날이 바뀌면 카카오 결과가 달라질 수 있어 **같은 날 전 · 후를 함께 재는 것**이 가장 공정하다. 보고서 `env` 에 판 · DB · 날짜가 남는다.

## 결과

| | v0-develop (실측) | 배포판 2026-10-07 (근사 · 참고) |
|---|---|---|
| **정답** | **15/34 (44%)** | 25/34 (74%) |
| ★틀린 곳을 확정(`wrong_confirmed`, 목표 0) | **11** | 0 |
| 틀렸지만 확인 필요(`wrong_review`) | 3 | 5 |
| 못 찾음(`not_found`) | 5 | 3 |
| 막힘(`blocked`) | 0 | 1 (관광공사 호출 한도) |
| 묶음별 정답 — 이름 / 위치 / 기타 | 5/10 · 6/12 · 4/12 | 7/10 · 11/12 · 7/12 |

- **v0-develop** — `role-dining` 3fad933(= develop 2f3594a 와 같은 코드, 작업 트리 변경 있음) · DB `dining_rebuild`(원장 영업 중 1,767곳) · 카카오 실호출 · 모델 꺼짐.
- **배포판(근사)** — 브라우저로 본 결과(이름 · 확인 표시 · 앞 일정과의 거리)를 같은 규칙으로 센 것. 종류 · 기준 좌표 거리를 재지 않았고 판이 다르다(role-manager). **비교 기준이 아니라 참고값**이다 — 배포판을 정식으로 재려면 `ADAPTERS` 에 role-manager 조립을 더해 로컬에서 잰다.

## v0-develop 이 틀린 곳

| 무엇 | 케이스 | 원인(develop 코드) |
|---|---|---|
| 체인을 위치와 무관하게 확정 | 011 · 013 · 016 · 025 · 026 (스타벅스 → 더북한산점 8.9km 등) | 「가까운 곳 고르기」 2차 단계가 develop 에 없다 — 카카오 첫 결과를 확인 없이 쓴다 |
| 체인 지점을 확인 없이 확정 | 006 · 012 · 014 · 015 | 맞는 지점이어도 원문이 지점을 말하지 않았는데 확인 표시가 없다 |
| 지점명을 위치로 안 씀 | 031 (강남역점 → 강남구청역점) | 지점 단서를 쓰지 않는다 |
| 이름이 아닌 말을 장소로 | 024 (점심 한식 → 한식문화공간 이음) | 「이름 없는 식사」 판정이 없다 |
| 시장 · 골목 + 가게 | 008 · 009 · 034 | 좁힌 이름(골목 · 시장 · 카페거리)을 고른다 |
| 오타 · 로마자 · 영문 체인 · 메뉴 | 004 · 027 · 010 · 028 · 023 | 원장 · 카카오에 오타 비교가 없다 · 로마자 경로 없음 |

배포판(role-manager)이 develop 보다 나은 부분(체인 근처 지점 · 확인 표시 · 이름 없는 식사)은 develop 에 아직 없다. 남은 문제는 배포판에도 그대로다 — 013 · 026(앞 일정이 후보 중 고른 곳) · 031(지점명) · 008 · 009(시장 · 골목) · 004(오타) · 028(영문 체인) · 023(메뉴).
