# S-ISOLATION 구현 리포트

## 변경 사항

- PII 마스킹 구현인 `masked`와 재귀 마스킹 함수 `mask_json`을 `app/core/redaction.py`로 이동했다.
- `app/core/transition.py`는 이제 `app.core.redaction`에서 `mask_json`을 가져온다.
- `app/presentation/security.py`에는 `masked`와 `mask_json`의 기존 이름을 유지하는 단방향 re-export를 남겼다. 새 Core 모듈은 Presentation을 참조하지 않는다.
- `tests/contract/test_core_isolation.py`는 `app/core/**`의 모든 Python 파일을 AST로 검사하고 `app.modules`, `app.presentation`, `app.infrastructure`, `app.application` 및 하위 모듈 import를 금지한다. 실패 메시지에는 위반 파일과 import 이름이 포함된다. `app.core.*`, 표준 라이브러리, 서드파티 import는 허용되며 `psycopg`도 별도 예외 없이 허용된다.

## 검증

- 계약 테스트에 임시로 `from app.presentation.security import mask_json`을 삽입했을 때 `Core isolation violation: ... imports app.presentation.security` 메시지로 실패하는 것을 확인했다.
- 임시 위반은 즉시 되돌린 뒤 최종 소스에는 남기지 않았다.
- `python -m pytest tests/contract/test_core_isolation.py -v`: `1 passed`.
- `python -m pytest tests/security/test_pii_redaction_runtime.py -q`: `1 passed`.
- `python -m pytest tests -q`: `123 passed, 3 failed, 1 deselected`. 실패 3건은 모두 기존 RAG 통합 테스트의 OpenAI 임베딩 호출이 현재 환경의 네트워크 권한 오류(`WinError 10013`, `api.openai.com`)로 실패한 것이다. 이 변경으로 인한 실패는 계약 테스트와 PII 런타임 테스트에서 확인되지 않았다.

```text
python -m pytest tests -q
python -m pytest tests/contract/test_core_isolation.py -v
```
