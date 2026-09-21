# 2026-08-12 S-EVAL live

- `eval/runners/common.py`에 `get_settings()` 기반 OpenAI adapter, JSON judge 호출, 실제 usage 기반 비용 계산, concurrency 기본값 8, case/repeat 정렬, 429 지수 백오프와 retry 기록을 추가했다.
- mock provider는 유지했다.
- dry-run 합계 예상 비용은 `$0.1155`였다.
- smoke 5건과 전량 540건은 모두 `APIConnectionError: Connection error.`로 실패했다.
- 실패 행을 `eval/reports/raw_live.jsonl`에 기록했고, mock raw 결과와 섞지 않았다. 성공 호출 0건이므로 정확도/CI/McNemar 결론은 산출하지 않았다.
