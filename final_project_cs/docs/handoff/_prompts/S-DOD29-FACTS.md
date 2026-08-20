# 구현 지시 — DoD-29 실측 사실 수집 (판정 금지, 사실만)

## 0. 배경

v8 §27 이 신설한 DoD 29번은 "Response Generation & Review 검증"이다.
이 저장소에 `app/modules/customer_ops/response_review.py` 가 막 이식됐다
(`docs/reports/2026-08-18_S-RESPONSE-REVIEW-PORT_리포트.md`). DoD 통과
여부 판정은 Claude 가 하지만, 그 전에 **사실을 정확히 수집**해야 한다 —
이 작업은 판정하지 않고 사실만 모은다.

## 1. 소유 범위

```
쓰기 대상: docs/reports/2026-08-19_DoD29-사실수집.md 하나만
읽기: app/modules/customer_ops/response_review*.py, tests/unit/teams/test_response_review.py,
      config/project.yaml, app/core/registry.py, app/application/controller.py
```
다른 파일은 건드리지 않는다.

## 2. 수집할 사실 (전부 재현 명령 + 실제 출력 붙여서)

1. `python -m pytest tests/unit/teams/test_response_review.py -v` 전체 출력
2. `config/project.yaml` 의 `teams:` 에 `response_generation_review` 가
   있는지 없는지 (`grep`)
3. `app/core/registry.py`/`app/application/controller.py` 를 읽고,
   `accepted_case_types=[]` 인 Team 이 지금 **어떤 경로로도 실행될 수
   있는지** 확인해라 — Controller 의 라우팅(`registry.resolve`)이
   `accepted_case_types` 기반이라면, 빈 리스트인 Team 은 **자동으로는
   절대 안 불린다**는 뜻이다. 이게 맞는지 코드 근거를 들어 확인해라.
   (수동으로 직접 `ResponseGenerationReviewTeam(...).execute(task)` 를
   호출하는 것 외에 다른 실행 경로가 있는지도 찾아봐라.)
4. 실 LLM 호출 경로가 있는지 — `response_review.py` 의 `LLM` Protocol 을
   실제로 구현해 주입하는 코드(합성 fake 말고 `OpenAITeamLLM` 같은 실제
   어댑터)가 저장소 어디에 있는지 찾아라. 없으면 "없다"고 명시해라.
5. golden/holdout 데이터셋(`eval/datasets/*.jsonl`)에 이 Team 을 대상으로
   한 case 가 있는지(`response_generation_review` 관련 필드나 케이스가
   있는지) 확인해라.

## 3. 하지 말 것

- "통과"/"부분통과"/"미착수" 같은 **판정 문구를 쓰지 마라.** 사실만 나열한다.
- 코드를 고치지 마라. 순수 조사다.

## 4. 완료 조건

- [ ] 위 5개 항목 전부 재현 명령 + 실제 출력으로 채워짐
- [ ] `docs/reports/2026-08-19_DoD29-사실수집.md` 하나만 생성됨
