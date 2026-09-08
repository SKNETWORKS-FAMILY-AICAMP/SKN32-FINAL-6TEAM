# 2026-08-17 16:20 — 운영 classifier 도메인 어휘 결함 수정 (심각도 최고)

- 계획: (계획서 없음 — 도메인 마이그레이션 잔여 결함 스캔 중 발견)
- 담당: Claude(발견·어휘 설계·검수·불변조건 테스트 작성) + Codex(S-VOC-CLASSIFIER, 기계적 전파)
- 수행: `app/modules/customer_ops/feedback.py::INTENTS` 가 옛 구독 도메인
  (`billing`/`technical`/`other`)으로 남아 있었고, 이 함수가 **운영 REST API 의
  기본 classifier** 로 실제 주입되는 것을 발견 — 지금까지 모든 쇼핑몰 Case 가
  분류 실패로 떨어졌을 것. 새 어휘(`order`/`shipping`/`return`/`exchange`/`other`,
  이슈코드 13종)를 Team 라우팅 계약(`accepted_case_types`)과 정확히 맞춰 설계 후
  Codex 로 기계적 전파. 재발 방지용 불변조건 테스트
  (`test_feedback_intent_alignment.py`) 신규 작성.
- 검증: `composition.build_classifier()`(API 가 실제 쓰는 함수) 를 직접 호출해
  실 LLM 으로 쇼핑몰 메시지 분류 성공 확인. `pytest -q` 295 passed(신규 테스트
  포함). 검수 중 별건(`test_project_composition.py`)을 Codex 범위 위반으로
  잘못 의심했다가 조사 후 세션 이전 기존 변경임을 확인 — 그 과정에서 이 세션의
  반복된 전체 테스트 실행이 실제 결함을 놓치지 않는다는 것도 부수적으로 증명함.
- 리포트: `wiki/records/reports/2026-08-17_1620_S-VOC-CLASSIFIER_검증_리포트.md`
- evidence: `wiki/records/evidence/PROD-CLASSIFIER-DOMAIN-MISMATCH_수정.md`
- 미해결: 실 REST API 를 통한 Case 생성 e2e 테스트가 스위트에 없다 — 다음 작업 후보.
