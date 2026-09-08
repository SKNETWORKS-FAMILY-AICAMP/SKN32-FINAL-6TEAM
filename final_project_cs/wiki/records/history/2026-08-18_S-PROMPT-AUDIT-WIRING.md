## 2026-08-18 — 프롬프트 감사추적 배선 구현

- 계획: `wiki/records/handoff/_prompts/S-PROMPT-AUDIT-WIRING.md`
  (설계는 `wiki/records/reports/2026-08-18_S-PROMPT-WIRING-DISCUSS_검토.md` 에서 사전 교차검증)
- 담당: Claude(계약·프롬프트 콘텐츠 4건·독립검증·잔여결함 수정) + Codex(구현)
- 수행: `register_prompt_files()` 재작성(키 계산 수정·advisory lock·active
  유일성 검증), `OpenAITeamLLM` 에 `connection_factory` 주입해 활성 프롬프트
  조회·별도 트랜잭션 감사 기록·fail-closed 배선, Team 호출부 4곳에 `run_id`
  전달, `scripts/register_prompts.py` 신규, 신규 테스트 6건. Claude 가
  `git diff` 전수 검토로 계약 준수 확인, 자기보고 누락(변경 파일 목록에서
  `composition.py`/Team 파일 빠짐 — 실제로는 정확히 반영됨) 발견,
  테스트 DB 잔재 정리 로직 추가, 옛 도메인 프롬프트 12개를
  `legacy/final_project_sample/prompts/` 로 이동해 배포 스크립트가
  정상 시에도 항상 실패 종료하던 설계 공백을 해소.
- 검증: 신규 테스트 6 passed, 전체 `pytest -q` 304 passed(회귀 0),
  `scripts.register_prompts` exit 0, 실 라이브 e2e 테스트 재확인 통과.
  단 실 OpenAI 호출이 실제로 도는 시나리오의 `llm_calls` 종단 적재는
  이번 세션에서 확인하지 못함(한계로 기록).
- 리포트: `wiki/records/reports/2026-08-18_S-PROMPT-AUDIT-WIRING_리포트.md`
