# 대체 식당 평가 — v0 → v1 (2026-10-07)

시나리오 `eval/datasets/dining_alternatives_v1.jsonl`(17건, 지은 장소) · 채점 `eval/runners/dining_alternatives.py` · 시나리오 자체 점검 `eval/tests/test_dining_alternatives.py`.

## 다시 재는 법

```powershell
cd final_project_cs
$env:PYTHONPATH="$PWD;$PWD\..\final_project_sample"; $env:PYTHONUTF8="1"
.\.venv\Scripts\python.exe -m eval.runners.dining_alternatives --label <이름> --out eval\reports\<날짜>_dining_alternatives_<이름>.json
```

순수 계산이다(DB · 외부 API 없음) — 같은 코드면 같은 결과. 장소 id 를 5가지로 바꿔 돌아(`--seeds`) 모든 판에서 같은 판정일 때만 인정한다.

## 결과

| | v0-develop | v1-route-likeness |
|---|---|---|
| **안정적인 정답** | **5/17** | **17/17** |
| 장소 id 순서로 갈림(`unstable`) | 12 | 0 |
| 한 판이라도 다음 일정에 늦는 곳을 고름 | 2 | 0 |
| 묶음 — 동선 / 비슷함 / 브랜드 / 기본 | 1/5 · 0/6 · 1/3 · 3/3 | 5/5 · 6/6 · 3/3 · 3/3 |

★17건은 고치면서 같이 본 **개발 세트**다 — 17/17 은 부풀려진 값일 수 있다. 확인용 세트(보지 않은 시나리오)를 따로 만들어 재야 한다.

## v0 의 원인

`replan.Candidate.rank` 가 식당 후보를 가격 → 원래 시각과의 차이 → **장소 id** 로 정렬했다. 식당 자료에는 가격이 거의 없어 사실상 장소 id 순이었다. 거리 · 다음 일정까지의 이동 · 종류를 보지 않았다.

## v1 에서 바꾼 것

- **동선** (`replan.MealRoute`) — 식사 뒤 걸어서 다음 일정에 **원래 식당보다 더 늦게** 닿는 곳은 탈락. 원래 식당에서 다음 일정까지 걸어서 20분(`WALKABLE_LEG_MIN`) 안일 때만 — 더 먼 구간은 교통을 탄다고 보고 도보로 탈락시키지 않는다. 앞 일정 → 식당은 탈락시키지 않고 순위에만(식당 입장 몇 분은 다음 일정을 놓치는 것과 다르다).
- **비슷함** (`meal_likeness`) — 같은 브랜드 > 같은 메뉴(이름 · 세부 분류의 메뉴 말) > 같은 큰 종류 > 모름 > 다름. 원장 `category`(큰 종류만 — 세부 칸이 없다), 카카오 분류, `cuisine` 을 읽는다. 원장 근처 가게를 들여올 때 `category` 를 싣는다.
- **순위** — 늘어난 이동이 10분(`ROUTE_TOLERANCE_MIN`) 안인가 → 비슷함 → 가격 → 늘어난 이동 → 원래 식당에서의 도보. 활동 · 경로 후보는 새 칸이 모두 0 이라 예전 순서 그대로다.

## 시험

`tests/unit tests/e2e tests/scenario tests/integration/dining eval/tests` — 2,292 통과 · 실패 0 · 건너뜀 71(`run_tests_local.ps1`).
처음 판에서 시나리오 시험 10개가 깨졌고 두 규칙을 고쳤다 — ①시간 여유로 「걸어서 닿나」를 재면 2시간 반 사이 97분 도보도 걸어서 닿는다고 봤다 ②앞 활동 13:00 끝 · 점심 13:00 인 계획은 원래 식당도 몇 분 늦어 후보가 모두 탈락했다.

## 남은 것

- 「그 가게 자체」를 원한 경우(고정 · 예약 · 특정 노포)는 다른 가게가 아니라 **같은 가게의 다른 시각 · 다른 날**을 먼저 찾아야 한다 — 지금은 다른 가게를 고르고 `pending.protected_reason` 이 「묻기」로 돌린다.
- 도보만 잰다 — 다음 일정이 먼 구간은 이동 팀 계산기로 바꿔야 정확하다.
- 원래 식당이 원장과 이어지지 않은 장소(카카오 · 관광지)면 종류를 모를 수 있다 — 그때는 거리 · 동선만으로 고른다.
- 확인용 세트.
