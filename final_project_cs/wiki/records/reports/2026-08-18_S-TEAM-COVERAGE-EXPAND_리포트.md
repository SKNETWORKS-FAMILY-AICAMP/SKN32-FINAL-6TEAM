# Team 시나리오 커버리지 확장 리포트

## 변경 내용

- `order_shipping`에 `order_change_or_cancel`의 출고 전(`placed`, `paid`) 취소 제안을 추가했다.
- 출고 후(`shipped`, `delivered`)에는 취소 제안을 만들지 않고 기존 정책/LLM 경로로 통과한다.
- `return_exchange`에 `size_mismatch`, `color_mismatch`, `wrong_option` 교환 판별을 추가했다.
- 교환은 `exchange.request`, 항상 `high` 위험도로 사람 승인을 기다린다.
- 실시간 재고를 확인할 수 없다는 근거를 `doc_15#재고 확인의 선행` evidence로 남긴다.
- 기존 `defective` 반품은 `return.accept`를 유지한다.

## 재현 명령 및 실제 출력

명령:

```powershell
python -m pytest tests/unit/teams -q
```

출력:

```text
........                                                                 [100%]
8 passed, 1 warning in 4.41s
```

명령:

```powershell
python -m pytest -q
```

출력 요약:

```text
3 failed, 295 passed, 2 deselected, 1 error in 51.54s
```

전체 테스트의 실패/오류는 이번 변경과 무관한 환경 제약이다.

- RAG 통합 테스트 3건: OpenAI 임베딩 호출이 sandbox 네트워크 차단으로 `WinError 10013` 발생
- holdout 테스트 setup 1건: pytest 임시 디렉터리 `C:\Users\playdata2\AppData\Local\Temp\pytest-of-playdata2` 접근 권한 오류

## 범위 확인

이번 작업에서는 지정된 customer ops 모듈과 팀 시나리오 테스트, 본 리포트만 변경했다. Core, application, verification policy, migration 파일은 수정하지 않았다.

## ★Claude 독립 검증 (2026-08-18)

- `git diff` 로 `order_shipping.py`·`return_exchange.py`·
  `tests/unit/teams/test_team_scenarios.py` 세 파일 전부 줄 단위 대조 —
  계약 §2·§3·§4 그대로 구현됨. `verification_policy.py`·마이그레이션·
  Core·Application 은 `git status` 로 미변경 확인.
- ★계약 자체의 오류 1건 발견 — `Evidence.source_type` 예시로
  `"policy_chunk"` 를 줬는데 실제 `Literal` 은 `"policy"` 만 허용한다
  (`app/core/contracts.py:108`). Codex 가 계약을 맹종하지 않고 실제
  타입에 맞는 `"policy"` 로 정확히 고쳐 구현했다 — 검증 결과 정상.
- 기존 회귀 테스트(`test_return_request_proposes_action_without_mutation`)의
  fixture `reason_code` 를 `"size_mismatch"`→`"defective"` 로 필요한 만큼만
  고쳐서, 새 `EXCHANGE_REASON_CODES` 도입으로 그 테스트가 깨지지 않게
  했다 — 범위를 벗어나지 않으면서 실제로 필요한 수정이었다.
- Codex 자체 리포트의 "3 failed, 1 error"는 **Codex 샌드박스 환경 제약**
  (`CodexSandboxOffline` 계정의 외부망 차단·임시 디렉터리 권한)이다.
  Claude 가 실 환경에서 `python -m pytest tests/unit/teams -v` (8 passed)와
  `python -m pytest -q` (**299 passed, 2 deselected, 실패 0**)를 직접
  재실행해 회귀가 없음을 확인했다.
