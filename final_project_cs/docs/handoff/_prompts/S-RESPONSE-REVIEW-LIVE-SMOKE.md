# 구현 지시 — Response Generation & Review 실 LLM 스모크 테스트 1건

## 0. 배경

`docs/evidence/DoD-29_ResponseGenerationReview.md` 의 남은 항목 중
"실 LLM 호출 미검증"을 메운다. 지금까지 `test_response_review.py` 6건은
전부 `FakeLLM` 이었다 — 실제 `OpenAITeamLLM` 을 주입해 진짜로 한 번
돌아가는지 확인하는 테스트가 없다.

이 Team 은 `config/project.yaml` 에 등록돼 있지 않고 Controller 라우팅과
안 엮여 있다 — 그건 이번 범위가 아니다. 이 테스트는 **Team 을 직접
인스턴스화**해서(`app/presentation/api/cases.py` 나 다른 실 라이브 테스트가
REST 를 거치는 것과 다르게, Registry/Controller 를 안 거치고) 실행한다.

## 1. 소유 범위

```
쓰기 대상: tests/live/test_response_review_live_smoke.py 하나만
읽기: tests/live/test_feedback_classifier_live_e2e.py (같은 라이브 테스트
      관례 참고 — pytest.mark.live, 환경변수·API 키 확인 방식)
      app/modules/customer_ops/response_review.py
      app/infrastructure/llm/openai.py
```
다른 파일은 건드리지 않는다.

## 2. 테스트 내용

1. `@pytest.mark.live` 로 마킹한다(기존 라이브 테스트와 같은 관례 —
   기본 `pytest -q` 에서는 제외되고 `-m live` 로만 돈다).
2. `OpenAITeamLLM()` 을 실제로 생성해 `ResponseGenerationReviewTeam(llm)`
   에 주입한다. `app.core.settings.get_settings().openai_api_key` 가
   비어 있으면 `pytest.skip(...)` 한다(다른 라이브 테스트와 동일 관례).
3. 합성 `TeamTask` 를 하나 만든다 — `input_text` 는 실제 커머스 문의
   답변 초안처럼("주문하신 상품은 내일 도착 예정입니다." 같은 평범한
   안내 문장, 금칙어·PII 없음), `context.current_state={"sentiment":
   "neutral"}`, `context.evidence=[]`, `db_facts` 없음(claims 검증 없이
   통과하는 단순 케이스).
4. `execute()` 를 실제로 호출하고, 다음을 확인한다:
   - 예외 없이 끝난다
   - `result.outcome` 이 `completed` 또는 `escalated` 둘 중 하나다(모델
     응답이 결정론 검사를 통과할지는 모델 재량이라 미리 단정하지 않는다
     — 다만 `failed` 는 아니어야 한다, `malformed_llm_response` 류
     실패가 나오면 그건 실제 통합 결함이다)
   - `result.decisions` 가 비어 있지 않다(최소 1회 GEN→REV 사이클이 돌았다는 증거)
5. 실행 후 사용한 토큰·비용을 최소화한다 — 반복 없이 **1회만** 돈다.

## 3. 검증

```powershell
python -m pytest tests/live/test_response_review_live_smoke.py -m live -q
```
실제로 실행해서(스킵 없이) 통과하는지 출력을 리포트에 붙인다. API 키가
없어서 스킵됐다면 그 사실을 정직하게 적는다 — 스킵을 통과로 세지 않는다.

## 4. 완료 조건

- [ ] `tests/live/test_response_review_live_smoke.py` 신규, 다른 파일 미변경
- [ ] `pytest -q`(마커 제외 기본 실행)에서 이 테스트는 deselected 로만
      잡히고 실패로 잡히지 않는다
- [ ] `docs/reports/2026-08-19_S-RESPONSE-REVIEW-LIVE-SMOKE_리포트.md`
      제출 — §3 재현 명령의 실제 출력 포함
