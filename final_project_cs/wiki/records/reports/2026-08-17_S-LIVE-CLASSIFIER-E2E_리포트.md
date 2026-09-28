# S-LIVE-CLASSIFIER-E2E 리포트

## 변경 사항

신규 `tests/live/test_feedback_classifier_live_e2e.py`에 실제 운영 classifier를 사용하는 REST API 라이브 e2e 테스트를 추가했다.

- `create_app(controller=None)` 호출로 classifier 주입을 생략
- 쇼핑몰 배송완료 오판 메시지를 `POST /v1/cases`로 전송
- 분류 실패에 따른 `escalated` 상태가 아닌지, 쇼핑몰 intent와 `issue_code`가 생성되는지 검증
- 테스트 tenant/customer 및 관련 case 데이터를 teardown에서 삭제

## 검증

실 LLM 호출은 수행하지 않고 아래 명령만 실행했다.

```text
python -m pytest tests/live/test_feedback_classifier_live_e2e.py -q --collect-only
python -m pytest -q -m "not live"
```

실행 결과:

- `--collect-only`: `no tests collected (1 deselected)` 및 종료 코드 1. `pytest.ini`의 자동 `addopts` 필터가 수집 단계에도 적용되어 새 라이브 테스트를 제외했다.
- `-m "not live"`: `292 passed, 3 failed, 2 deselected`. 새 테스트를 포함한 라이브 테스트 2건은 기본 실행에서 제외됐다.
- 실패한 3건은 기존 RAG 통합 테스트의 OpenAI 임베딩 호출이 이 실행 환경의 외부 네트워크 차단으로 실패한 것이다. 이번 신규 테스트의 실 LLM 호출은 수행하지 않았다.
