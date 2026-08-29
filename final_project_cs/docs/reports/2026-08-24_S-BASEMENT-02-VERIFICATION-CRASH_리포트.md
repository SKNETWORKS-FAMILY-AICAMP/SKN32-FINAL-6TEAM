# S-BASEMENT-02-VERIFICATION-CRASH 수정 리포트

## 결론

`app/core/verification.py`의 `_to_decimal()`이 `Decimal` 변환 결과의 유한성을 확인하도록 수정했다. `NaN`, `Infinity`, `-Infinity`는 기존 숫자 변환 실패와 같은 `None`으로 처리되어 이후 비교 연산이나 `int()` 변환으로 서버 예외가 발생하지 않고 검증 실패가 된다.

`final_project_sample/` 및 다른 `verify_proposal`/`Facts` 검증 로직은 수정하지 않았다.

## 변경 사항

- 대상: `app/core/verification.py`
- `_to_decimal()`에서 변환 결과를 지역 변수에 저장한 뒤 `decimal.is_finite()`가 참일 때만 반환하도록 변경
- 비유한 값은 새 예외나 새 반환 형식을 만들지 않고 `None` 반환
- 대상 테스트: `tests/unit/core/test_proposal_verification.py`
  - `Decimal("NaN")`
  - `Decimal("Infinity")`
  - `Decimal("-Infinity")`
  - 세 값 모두 예외 없이 `refund_amount` 검증 실패인지 확인

## 검증 결과

### 수정 전 재현

추가한 3개 테스트를 수정 전에 실행한 결과 모두 실패했다.

- `NaN`: `decimal.InvalidOperation`
- `Infinity`: `OverflowError: cannot convert Infinity to integer`
- `-Infinity`: `OverflowError: cannot convert Infinity to integer`

### 수정 후 관련 테스트

```text
python -m pytest tests/unit/core/test_proposal_verification.py -vv
19 passed, 1 warning
```

비유한 금액 3개와 기존 정상 금액 비교·거부 테스트를 포함해 모두 통과했다.

### 전체 비-live 테스트

요청한 명령:

```text
python -m pytest -q -m "not live"
```

실행 결과:

```text
346 passed, 10 failed, 11 errors, 3 deselected, 2 warnings
```

요청에 제시된 기존 기준 `359 passed`와 비교하면 이번 실행은 전체 성공 기준에 도달하지 못했다. 실패/오류는 verification 관련 변경과 무관한 기존 환경 의존 문제로 확인됐다. 주요 증상은 다음과 같다.

- pytest 임시 디렉터리(`C:\\Users\\playdata2\\AppData\\Local\\Temp\\pytest-of-playdata2`) 권한 오류
- DB/consumer 및 API 통합 테스트 실패
- RAG 통합 테스트의 OpenAI embeddings 외부 연결 차단(`WinError 10013`)

해당 전체 테스트 실패들은 이번 변경 파일의 verification 단위 테스트 실패가 아니며, 관련 테스트 19개는 모두 통과했다.
