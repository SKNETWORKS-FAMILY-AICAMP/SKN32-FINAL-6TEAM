# S-BASEMENT-10 — Introspection endpoint report

## 구현

- `app.introspection.contract.snapshot()`에 cs composition root 기준의 v1.0 read-only 조립 스냅샷을 추가했다.
- 응답은 `contract_version`, `config_revision`, `modules`, `ports`, `team_manifests`, `teams`, `port_implementations`, `guardrails`, `llm`을 제공한다.
- `ProjectConfig.revision`은 `getattr(..., None)`으로 처리한다.
- LLM API key는 `sk-****` 또는 `missing`으로만 반환하며, tenant 문서/청크/Case/outbox 운영 카운트는 포함하지 않는다.
- `GET /introspection`을 `ops:introspect` scope로 보호하고 API app에 등록했다.
- `config/guardrails.yaml`에 `ops:introspect`를 추가했다.
- 기존 `/ui/admin` 스냅샷은 필드 구조 보존을 위해 변경하지 않았다.

## 검증

- 신규 targeted 검증: **6 passed**
  - 계약 shape, 5개 활성 Team manifest, API key masking, tenant 운영 데이터 제외
  - 인증 없음 `401`, 다른 scope `403`, 올바른 `ops:introspect` scope `200`
- 전체 명령: `python -m pytest -q -m "not live"`
- 실행 결과: **370 passed, 4 failed, 14 errors, 3 deselected**

전체 실행의 비통과 항목은 이번 변경과 무관한 환경 제약이다. 14 errors는 pytest 임시 디렉터리 권한(`WinError 5`)으로 발생했고, RAG 관련 3 failures는 sandbox의 외부 OpenAI embedding 네트워크 차단으로 발생했다. 전체 출력에는 별도 기존 테스트의 환경 의존 실패도 포함되어 있다. 신규 introspection targeted 테스트는 모두 통과했다.
