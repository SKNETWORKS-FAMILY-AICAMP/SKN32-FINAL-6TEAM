# Introspection contract v1

`GET /introspection`은 `ops:introspect` scope로 보호되는 read-only JSON API다.
응답은 `app.introspection.contract.snapshot()`의 조립 메타데이터를 그대로
반환하며, `contract_version`은 `1.0`이다.

응답에는 활성 모듈과 Port 선언, Team manifest/선언, 실제 Port 구현 이름,
guardrails, LLM provider/model 및 마스킹된 `api_key`가 포함된다. API key 원문과
tenant 운영 데이터(document/chunk/case/outbox 카운트)는 포함하지 않는다.
