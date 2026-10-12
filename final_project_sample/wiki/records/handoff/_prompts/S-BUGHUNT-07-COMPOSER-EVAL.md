# S-BUGHUNT-07-COMPOSER-EVAL — Composer 쓰기채널·eval/stats 버그 사냥 (리포트만, 수정 금지)

## 배경

라운드 1~6 이력(전부 `wiki/records/reports/debugs/2026-08-17_버그사냥_*.md`) — 지금까지
16건 발견, 11건 수정, 2건 버그 아님 확인, 3건 문서화 후 보류(그중 resume
token 미검증이 가장 중요한 미해결 항목).

## 이번에도 다르게 한다 — ★고치지 않는다, 보고만 한다

이유는 앞선 라운드와 같다(`RULE.md` §3.6-3).

## 스캔 범위

1. `app/application/composer_service.py`, `app/presentation/api/composer.py`
   — 이번 세션에서 새로 만든 구성 쓰기 채널(`/composer/validate`,
   `/composer/apply`). **만든 사람이 스스로 검토하면 맹점이 있다** — 새 눈으로
   본다
2. `eval/stats/bootstrap.py`, `eval/stats/mcnemar.py` — 통계 검정. 지금까지
   어느 라운드도 안 봤다
3. `eval/stats/agreement.py` — 이번 세션에 새로 만든 judge agreement 도구.
   이것도 만든 사람이 검토했다

## 찾을 것

라운드 1~6 과 같은 기준. 특히:

- **composer_service.py 의 `base_revision` 낙관적 동시성이 실제로 원자적인지** —
  두 `apply_candidate()` 호출이 정말 경합하면 어떻게 되는지(단일 프로세스
  락은 있는데, 락 안에서 파일 I/O 실패 시 락이 풀리는지, 임시 파일이 남는지)
- **`validate_candidate()`/`apply_candidate()` 가 만드는 임시 파일이 예외
  경로에서 항상 정리되는지** — 특히 `load_project_config()` 자체가 예외를
  던지는 경로들
- **bootstrap.py 의 재표본추출이 실제로 무작위인지, seed 고정이 재현성을
  해치지 않는지** — 같은 seed 로 두 번 돌리면 정말 같은 CI 가 나오는지
- **mcnemar.py 의 exact/chi-square 분기 임계값이 정확한지** — 코너 케이스
  (discordant pair 0개, 전부 같은 방향)에서 죽거나 잘못된 값을 내는지
- **agreement.py 의 Cohen's kappa 가 표준 공식과 정확히 일치하는지** —
  카테고리가 하나뿐일 때(expected==1.0) 분기가 맞는지

**확신 없으면 "의심됨 — 확인 필요"로 표시.** 억지로 개수 채우지 않는다 —
못 찾으면 못 찾았다고 적는다.

## 만들 것

`wiki/records/reports/2026-08-17_버그사냥_07_Composer_eval.md` 하나만. 형식은 이전
라운드와 같다:

```
### <파일:줄번호> — <한 줄 요약>
- 시나리오: <구체적 입력/상태 → 무엇이 잘못되는지>
- 왜 기존 테스트가 못 잡는가: <이유>
- 재현 시도: <실제로 재현을 시도했다면 그 결과. 못 했으면 "재현 안 해봄, 코드 읽기로만 판단">
- 위험도: 높음 | 보통 | 낮음
```

## 완료 기준

```powershell
python -m pytest -q   # 이 스트림은 코드를 안 건드리므로 그대로 349 passed 여야 한다
```
