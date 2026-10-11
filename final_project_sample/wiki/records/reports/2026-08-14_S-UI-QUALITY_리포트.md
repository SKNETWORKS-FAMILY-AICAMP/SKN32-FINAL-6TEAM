# S-UI-QUALITY 구현·검증 리포트

## 1. 범위

지시서가 허용한 `app/presentation/ui/**`, `tests/e2e/**`, `wiki/records/reports/` 안에서만 수정했다.
`app/core/**`, `app/domain/**`, `app/application/**`, `app/infrastructure/**`, `app/presentation/api/**`, `app/composition.py`, `config/**`, `eval/**`, `knowledge/**`, `scripts/**`, `wiki/records/handoff/**`, `wiki/records/evidence/**`는 수정하지 않았다.

## 2. 채운 것

- VOC의 `intent / issue count` JSON 덤프를 오늘/직전 7일 표로 변경했다. 데이터가 비어 있으면 0을 만들지 않고 `분류 집계 없음` 또는 `미분류`로 표시한다.
- VOC 급증 alert를 critical 카드로 표시하고, alert가 없으면 `급증 alert 없음`을 표시한다.
- Composer의 모듈/Port/Team/읽기 전용 컴포넌트 영역을 `theme.card()`, `theme.table()`, `theme.page()` 기반으로 옮겼다.
- Composer 입력/선택지/모바일 표의 공용 테마 스타일을 추가했다.
- 기존 `waiting_approval` 경고색, 근거 없음 잠금·이유, degraded 배너, admin key 마스킹 동작을 유지했다.

## 3. 실제 HTTP 렌더링 원문

실행:

```powershell
python -m uvicorn app.presentation.api.app:app --port 8055
```

실제 HTTP 클라이언트로 확인한 결과:

```text
/ui/cases 200 :: <!doctype html><html lang='ko'>...<title>Case 목록 · A-COP</title>...
/ui/cases/00000000-0000-0000-0000-000000000000 200 :: <!doctype html><html lang='ko'>...<title>Case 상세 · A-COP</title>...
/ui/cases/00000000-0000-0000-0000-000000000000/trace 200 :: <!doctype html><html lang='ko'>...<title>Trace · A-COP</title>...
/ui/approvals 200 :: <!doctype html><html lang='ko'>...<title>Approval · A-COP</title>...
/ui/voc 200 :: <!doctype html><html lang='ko'>...<title>VOC 일일 리포트 · A-COP</title>...
/ui/admin 200 :: <!doctype html><html lang='ko'>...<title>Basement Admin · A-COP</title>...
/ui/composer 404 :: {"detail":"Not Found"}
```

Composer 404는 `config/project.yaml`의 `composer_ui: { enabled: false }`에 따른 의도된 feature flag 동작이다. Composer를 활성화한 구성 파일을 사용한 E2E에서는 200을 반환하고 `theme.page()` 기반 HTML을 렌더링했다.

기존 화면 계약 문자열도 E2E에서 확인했다: `post_cancel_charge`, `masked answer`, `append-only`, `v1` 선행, `approval_required`, `rationale evidence`, `근거 없음`, disabled 승인 버튼, `12000`, `sk-****`, team id들.

## 4. 추가 테스트

`tests/e2e/test_operations_ui.py`에 다음 회귀 검증을 추가했다.

- `waiting_approval` 목록에 `pill--warn`과 상태 문자열이 렌더링되는지 확인
- degraded Case 상세에 `ContextPack`, 누락 항목, critical notice가 렌더링되는지 확인

결과:

```text
python -m pytest tests/e2e -q
13 passed, 1 warning
```

## 5. 전체 검증과 발견한 결함

```text
python -m pytest tests -q
156 passed, 3 failed, 1 deselected
```

실패 3건은 기존 `tests/integration/rag/test_rag_integration.py`가 OpenAI embedding 외부 호출을 수행하다 실행 환경의 `api.openai.com` 소켓 차단(`WinError 10013`)으로 실패한 것이다. UI 변경과 무관하며, 금지된 infrastructure 범위를 수정하거나 `pytest.skip`으로 숨기지 않았다.

기준선 지시서의 `158 passed`는 현재 환경에서 재현되지 않았고, UI 관련 테스트는 통과했다.

