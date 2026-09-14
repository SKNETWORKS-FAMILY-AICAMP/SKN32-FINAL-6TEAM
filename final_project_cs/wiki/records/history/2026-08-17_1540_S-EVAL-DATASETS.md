# 2026-08-17 15:40 — RAG 적재 + golden/holdout 재작성

- 계획: (계획서 없음 — 코퍼스 25문서 인수 완료 이후 자연스레 이어지는 잔여 작업.
  다음 세션에서 계획서 갱신 필요하면 `wiki/records/plans/` 에 등록)
- 담당: Claude(적재·버그수정·계약설계·검수) + Codex(S-EVAL-DATASETS, golden/holdout 80건 생성)
- 수행:
  1. `knowledge.ingest` 실행 — 25문서/306청크 DB 적재, RAG 통합테스트 4건 도메인 갱신
  2. `eval/runners/common.py` import 결함 발견·수정(삭제된 `billing.py`/`technical.py` 참조)
  3. `wiki/records/handoff/_prompts/S-EVAL-DATASETS.md` 계약 작성 → Codex 위임 →
     `eval/datasets/golden.jsonl`(60)·`holdout.jsonl`(20) 쇼핑몰 도메인으로 전면 재작성
  4. `scripts/verify_eval_datasets.py` 작성, Codex 산출물 독립 재검증
  5. 회귀 발견·수정 — `eval/tests/test_stats_and_datasets.py` 의 옛 도메인 배분 단언
- 검증: `pytest -q -m "not live"` 294 passed. `verify_eval_datasets` 전 항목 통과.
  실 LLM `--limit 2 --provider openai` 스모크 2건 모두 `error=None`.
- 리포트: `wiki/records/reports/2026-08-17_1540_RAG적재_평가데이터셋_재작성_리포트.md`
- evidence: `wiki/records/evidence/DoD-EVAL-DATASETS_검증.md`, `wiki/records/evidence/EVAL-RUNNER-IMPORT-FIX.md`
- 미해결: DoD-15·17(judge agreement, 사람 라벨 20건)은 이 작업으로 닫히지 않는다 —
  사람 라벨링이 유일한 차단 사유다. golden×3/holdout 전체 실측(540관측)은 비용 승인
  없이는 실행하지 않았다.
