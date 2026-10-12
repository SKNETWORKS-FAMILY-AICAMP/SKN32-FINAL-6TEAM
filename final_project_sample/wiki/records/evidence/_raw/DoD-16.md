# DoD-16 실측 원문 (수집: Codex, 판정 없음)

## 재현 명령
```powershell
python -m eval.stats.bootstrap --input eval/reports/sample_raw.jsonl --n 10000
python -m eval.stats.mcnemar --input eval/reports/sample_pairs.jsonl
```

## 실제 출력
```
paired_n=5; Proposed-A mean diff [0.200000] [-0.800000, 1.200000]; 유의하지 않다 (CI가 0을 걸침)
EXIT=0
discordant_b=2; discordant_c=1; discordant_total=3; method=exact; p_value=1.000000
EXIT=0
```

## 관측 사실
- bootstrap 명령의 `n` 인자는 10000이다.
- bootstrap 출력의 paired_n은 5이고 mean diff는 0.200000이다.
- McNemar 출력의 discordant_b는 2, discordant_c는 1, total은 3이다.
- McNemar method 문자열은 `exact`, p_value는 `1.000000`이다.

## 확인하지 못한 것
- 리포트 템플릿의 한계 절을 별도 명령으로 확인한 결과는 수집하지 못했다.
