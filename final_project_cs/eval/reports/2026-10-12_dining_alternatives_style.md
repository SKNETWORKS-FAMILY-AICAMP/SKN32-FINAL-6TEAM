# 대체 식당 평가 — 음식 결 (2026-10-12)

시나리오 `eval/datasets/dining_alternatives_style_v1.jsonl`(개발 4) · `dining_alternatives_style_holdout_v1.jsonl`(확인용 4) · 채점 `eval/runners/dining_alternatives.py`(장소 칸에 `category` · `style` 을 원장처럼 싣게 했다).

## 무엇을 재나

이름에 메뉴 말이 없는 식당(「노루정」 = 고깃집)이 문을 닫았을 때, 같은 「한식」이지만 결이 다른 가까운 곳(한상차림 · 해산물)보다 결이 같은 곳(고기구이)을 고르는가. 결을 모르면 예전처럼 큰 분류로 내려가는가. 동선이 결보다 먼저인가.

## 결과

| | 고치기 전 | 고친 뒤 |
|---|---|---|
| 개발 4 | 2/4 (ok 2 — 가까운 다른 결) | 4/4 |
| **확인용 4** | **1/4** (ok 3) | **4/4** |
| 기존 개발 (`dining_alternatives_v1`) | 19/19 (10-08 v3, 이동 계산기 켬) | 17/17 (이동 계산기 끔 — transit 2 건너뜀) |
| 기존 확인용 8 (`dining_alternatives_holdout_v1`) | 8/8 (10-08 v3) | 8/8 |

- 장소 id 를 5가지로 바꿔 돌았다(`--seeds 5`) — 갈린 판정(`unstable`) 0, 동선 위반 0.
- 결과 파일: `2026-10-12_dining_alternatives_style_before.json` · `_style_after.json` · `_style_holdout_before.json` · `_style_holdout_after.json` · `_holdout_v4-style.json`.

★**표본이 작다(8건).** 시나리오와 규칙을 같은 사람(Claude)이 같은 날 썼다 — 확인용 4건은 고치기 전에 쓰고 고친 뒤 한 번만 쟀지만, 「결이 같으면 먼저」라는 설계를 아는 채로 썼다. 방향을 보여 줄 뿐 실제 고객 대체에서 얼마나 나아지는지는 말하지 않는다.

★**평가는 원장 결 규칙의 정확도를 재지 않는다** — 시나리오는 결을 직접 넣는다. 규칙의 정확도는 로컬 원장 무작위 60곳 눈 검사로만 봤다(작업 리포트 참조).

## 다시 재는 법

```powershell
cd final_project_cs
$env:PYTHONPATH="$PWD;$PWD\..\final_project_sample"; $env:PYTHONUTF8="1"
.\.venv\Scripts\python.exe -m eval.runners.dining_alternatives --label <이름> --dataset eval\datasets\dining_alternatives_style_v1.jsonl
```
