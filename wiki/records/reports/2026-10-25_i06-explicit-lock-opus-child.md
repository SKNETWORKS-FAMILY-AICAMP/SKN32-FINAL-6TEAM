# I06 명시 고정 운반 — Opus 자식 후보 (2026-10-25 KST)

- 결론: agent_read SCHEMA/AgentItem/ground + pipeline._agent_rows locked claim sink 2파일 최소 후보. 합성 I06 RED 3 → GREEN 9/9. 관련 회귀 1052 pass / 9 fail(수정 전 이미지도 동일 9 fail) / 2 skip / 190 db deselected. 실모델 after 미실행, DB·network 차단, source-v7·서비스·공유DB 변경 0.
- 계약: items[].locked boolean|null, items[].locked_quote string|null (required). 원문 인용(_find) 없으면 None + report.dropped.locked. claim items[i].locked method=llm_agent evidence=source text span. booked→locked 등치·규칙 재파싱 0.
- 정본 보고서·patch·JUnit·SAFE_HANDOFF: C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/claude55-support/opus-i06
- 남은 일: SYSTEM 예시 locked 키 반영 여부, 프롬프트 버전/해시 등록 확인, 부모 통합 후 실모델 단일 owner 검증, test_date_generation(venv jsonschema 없음) 실행.
