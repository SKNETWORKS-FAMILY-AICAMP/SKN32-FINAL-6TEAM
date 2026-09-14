# 구현 지시 — REST API 실 classifier 종단(e2e) 라이브 테스트 추가

## 0. 배경

`wiki/records/evidence/PROD-CLASSIFIER-DOMAIN-MISMATCH_수정.md` 에서 고친
"운영 classifier 가 쇼핑몰 Case 를 분류 못 하던 결함"은 **수동으로**(Claude 가
터미널에서 직접 함수를 호출해) 검증했다. 이 종류의 결함(classifier 어휘가
실제 도메인과 어긋남)을 **재발 시 pytest 로 자동으로 잡는 e2e 테스트가 없다.**

기존 `tests/integration/api/test_api_runtime.py` 의 모든 테스트는
`classifier=lambda _message: {"intent": "billing", ...}` 처럼 **classifier 를
주입해 진짜 `feedback.classify()`(→ 진짜 LLM 호출)를 우회한다.** 그래서 이
결함을 전혀 잡지 못했다.

`tests/live/test_llm_live.py` 에 이미 실 LLM 호출 1건짜리 라이브 테스트 패턴이
있다(`pytest.ini` 의 `-m "not live"` 로 기본 제외, `-m live` 로 명시 실행).
같은 패턴으로 **classifier 를 주입하지 않은** `POST /v1/cases` e2e 라이브
테스트를 추가한다.

## 1. 소유 범위

```
tests/live/test_feedback_classifier_live_e2e.py     ← 신규 파일만
wiki/records/reports/                                        ← 리포트 제출
```

★금지: 기존 파일 수정 없음(`app/**`·`tests/integration/**`·`tests/live/test_llm_live.py`
등 전부 건드리지 않는다). 이번 스트림은 **파일 하나 추가**가 전부다.

## 2. 무엇을 만드는가

`tests/integration/api/test_api_runtime.py` 의 `api_fixture`(파일 상단, tenant·
customer·인증 토큰을 만들고 끝에 정리하는 fixture)를 **그대로 참고해서** 라이브
버전을 만든다. 차이는 딱 하나 — **`classifier` 를 주입하지 않는다**
(`create_app(controller=None)` 만 호출 — `classifier=None` 이면
`app/presentation/api/app.py::create_app()` 가 `composition.build_classifier()` 를
기본값으로 쓴다, 이게 실제 운영 classifier 다). `controller` 는 `None` 으로 둔다
— Team 실행까지는 필요 없고, **분류가 실제로 성공해 `routing` 상태까지 갔는지**
만 확인하면 된다(`app/presentation/api/cases.py:94` 참고 — `controller is None`
이면 그 상태에서 멈춘다).

```python
"""Real end-to-end proof that the production classifier accepts shopping-
mall intents. Marked ``live`` because it makes one real LLM call — excluded
by default (pytest.ini ``addopts = -m "not live"``), run explicitly with
``pytest -m live``.

Regression this guards: 2026-08-17, ``feedback.INTENTS`` was still the old
subscription domain (``billing``/``technical``) while ``composition
.build_classifier()`` -- the exact function this test exercises -- is the
default classifier wired into ``POST /v1/cases``. Every real shopping-mall
Case would have failed classification silently (safely escalated, but never
routed). See wiki/records/evidence/PROD-CLASSIFIER-DOMAIN-MISMATCH_수정.md.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.presentation.api.app import create_app
# (tenant/customer/token 셋업은 tests/integration/api/test_api_runtime.py 의
#  api_fixture 를 참고해 그대로 재현한다 — import 로 재사용할 수 있으면 재사용,
#  안 되면 이 파일 안에 필요한 만큼만 복제한다. 과도하게 복제하지 않는다 —
#  이 테스트에 필요한 것은 tenant 1개, customer 1개, "case:write" 스코프
#  토큰 1개뿐이다.)


@pytest.mark.live
def test_real_classifier_accepts_a_shopping_mall_message_via_the_rest_api():
    ...
    app = create_app(controller=None)
    client = TestClient(app)
    response = client.post(
        "/v1/cases",
        headers={"Authorization": ...},
        json={"request_id": "live-classifier-e2e", "customer_id": str(...),
              "message": "배송완료로 떴는데 상품을 못 받았습니다. 확인 부탁드립니다.",
              "channel": "web"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] != "escalated", f"real classifier rejected the message: {body}"
    assert body["intent"] in {"order", "shipping", "return", "exchange", "other"}
    assert body["issue_code"]
```

위는 뼈대이지 그대로 복붙할 완성본이 아니다 — `api_fixture` 의 tenant/customer/
token 생성·정리 로직을 정확히 따라 실제로 동작하게 채워 넣는다. 테스트 정리
(teardown)에서 만든 tenant/customer/case 데이터를 반드시 지운다(다른 라이브
테스트처럼 흔적을 남기지 않는다).

## 3. 검증

★**너는 이 테스트를 실제로 통과시키려 하지 마라.** 네 실행 환경(`codex exec`
샌드박스)은 외부 네트워크(OpenAI API)가 막혀 있을 수 있다 — 이번 세션에서
RAG 임베딩 테스트가 같은 이유로 네 환경에서 실패했었다. 대신:

```powershell
python -m pytest tests/live/test_feedback_classifier_live_e2e.py -q --collect-only
python -m pytest -q -m "not live"      # 이 새 테스트가 기본 제외되는지 확인 (deselected 수가 늘어야 한다)
```

이 두 개만 확인하고 끝낸다. **실 LLM 호출은 Claude 가 직접 한다.**

## 4. 완료 조건

- [ ] `tests/live/test_feedback_classifier_live_e2e.py` 신규 생성, 다른 파일 무변경
- [ ] `pytest ... --collect-only` 로 테스트가 정상 수집됨(문법 오류 없음)
- [ ] `pytest -q -m "not live"` 의 `deselected` 카운트가 기존보다 1 늘어남(이 테스트가
      기본 실행에서 제외됨)
- [ ] `wiki/records/reports/2026-08-17_S-LIVE-CLASSIFIER-E2E_리포트.md` 제출
