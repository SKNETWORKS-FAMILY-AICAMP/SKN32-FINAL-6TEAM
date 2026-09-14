# S-VOC 인라인 분류기 쇼핑몰 어휘 교체 리포트

## 1. 작업 목표

`feedback.py`의 인라인 분류기 어휘를 현재 쇼핑몰 도메인과 Case 라우팅 계약에 맞추고, 신규 Case가 `ClassificationFailed`로 잘못 거절되지 않도록 수정했다.

## 2. 실제 수행 내용

- `app/modules/customer_ops/feedback.py`
  - `INTENTS`를 `order`, `shipping`, `return`, `exchange`, `other`로 교체했다.
  - `ISSUE_CODES`를 지정된 13개 쇼핑몰 issue code로 교체했다.
  - 모듈 docstring의 issue-code 목록을 새 어휘로 교체했다.
  - OpenAI 시스템 프롬프트의 intent 목록을 새 어휘로 교체했다.
  - `SENTIMENTS`, `SEVERITIES`, `classify()` 로직, 예외 처리, `_openai_llm()` 구조는 변경하지 않았다.
- `tests/unit/voc/test_feedback.py`
  - 주입 LLM fixture와 기대값을 `order/order_payment_failed`로 교체했다.
  - batch test의 SQL literal을 `order/order_payment_failed`로 교체했다.

## 3. 검증 방법 및 결과

### VOC 단위 테스트

실행:

```powershell
python -m pytest tests/unit/voc -q
```

결과: `8 passed` (pytest cache 디렉터리 권한 경고 1건)

### 수동 분류 확인

실행:

```powershell
python -c "from app.modules.customer_ops.feedback import classify; print(classify('배송이 너무 늦어요', lambda _: {'sentiment':'negative','intent':'shipping','issue_code':'shipping_delayed','severity':'medium'}))"
```

결과:

```text
Classification(sentiment='negative', intent='shipping', issue_code='shipping_delayed', severity='medium')
```

### 전체 비-live 테스트

실행:

```powershell
python -m pytest -q -m "not live"
```

결과: `291 passed, 3 failed, 1 deselected`

실패한 3건은 `tests/integration/rag/test_rag_integration.py`의 기존 RAG 검색 테스트이며, OpenAI Embeddings 호출 시 샌드박스 네트워크 권한 오류(`[WinError 10013]`)가 발생했다. 변경된 VOC 파일과의 assertion 실패나 회귀는 확인되지 않았다.

## 4. 미해결 사항 및 다음 작업

- 코드 변경과 직접 관련된 VOC 단위 테스트 및 수동 분류 확인은 완료됐다.
- 전체 테스트의 RAG 3건은 네트워크가 허용된 환경 또는 임베딩 mock/fixture가 준비된 환경에서 재실행해야 한다.
