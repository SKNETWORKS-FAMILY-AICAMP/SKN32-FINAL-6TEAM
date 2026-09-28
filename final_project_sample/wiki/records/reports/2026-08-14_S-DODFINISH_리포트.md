# 2026-08-14 S-DODFINISH 재측정 수집 리포트

## 수집 항목

- DoD-04: REST Case 생성, `agent_runs`, `graph_revision`, checkpoint 키.
- DoD-05: Context budget 단위 명령과 예산 초과 직접 입력의 token·omissions.
- DoD-10: VOC 단위 명령, `demo` daily feedback, 별도 tenant Case 6개·이전 Case 2개 측정.
- DoD-11: API/controller 통합 명령, 동일 요청 10회 DB 행 수, 승인 상태·버전, `unknown` 검색.
- DoD-18: `waiting_approval` Case의 UI HTML 검색과 trace version 위치.

원문: [DoD-04_v3.md](../evidence/_raw/DoD-04_v3.md), [DoD-05_v3.md](../evidence/_raw/DoD-05_v3.md), [DoD-10_v3.md](../evidence/_raw/DoD-10_v3.md), [DoD-11_v3.md](../evidence/_raw/DoD-11_v3.md), [DoD-18_v3.md](../evidence/_raw/DoD-18_v3.md)

## 실행하지 않은 명령과 이유

- 외부 LLM 호출: 외부망/API 호출 제약을 고려해 fake classifier와 fake Team을 주입했다.
- 실제 provider timeout 유도: provider 호출을 발생시키지 않고 `git grep`로 코드 문자열만 조회했다.
- DoD-18 승인 후 UI 재조회: 해당 측정에서는 `waiting_approval` 화면 본문을 조회한 뒤 승인 요청을 보내지 않았다.

## 데이터 정리

- DoD-10 별도 tenant `measure_voc_19ee61da9afe4b60840cfdd78665279e`의 Case, report, outbox, customer, tenant를 삭제했다.
- DoD-04/11/18 별도 measurement tenant의 연결 데이터를 각 측정 종료 후 삭제했다.
- `demo` tenant에는 daily feedback 명령만 실행했다.

## 완료 조건 명령 실제 출력

```text
v3_count=5
127 passed, 3 failed, 1 deselected, 2 warnings in 26.55s
tenants=1
```

- 실패한 3개 항목은 `tests/integration/rag/test_rag_integration.py`의 embedding 조회였다.
- 출력 예외는 `openai.APIConnectionError: Connection error.`였고, 내부 원인은 `api.openai.com:443` 소켓 접근 거부였다.
- 테스트 파일과 애플리케이션 파일은 수정하지 않았다.
