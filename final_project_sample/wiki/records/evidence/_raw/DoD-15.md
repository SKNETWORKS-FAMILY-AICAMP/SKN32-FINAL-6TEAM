# DoD-15 실측 원문 (수집: Codex, 판정 없음)

## 재현 명령
```powershell
(Get-Content eval/datasets/golden.jsonl | Measure-Object -Line).Lines
(Get-Content eval/datasets/holdout.jsonl | Measure-Object -Line).Lines
Get-ChildItem eval/runners -File | Select-Object Name,Length
```

## 실제 출력
```
60
20
Name          Length
----          ------
baseline_a.py    205
baseline_b.py    206
common.py       5235
proposed.py      319
__init__.py       48
```

## 관측 사실
- `golden.jsonl` 줄 수는 60이다.
- `holdout.jsonl` 줄 수는 20이다.
- `eval/runners`에 `baseline_a.py`, `baseline_b.py`, `common.py`, `proposed.py`, `__init__.py`가 있다.

## 확인하지 못한 것
- A/B/Proposed runner의 전량 실행 명령은 실행하지 않았다.
- holdout 전량 실행 명령은 실행하지 않았다.
