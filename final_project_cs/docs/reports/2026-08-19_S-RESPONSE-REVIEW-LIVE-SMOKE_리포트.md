# Response Generation & Review 실 LLM 스모크 테스트 리포트

## 1. 범위

- `tests/live/test_response_review_live_smoke.py` 신규 추가
- `OpenAITeamLLM`을 직접 생성해 `ResponseGenerationReviewTeam`에 주입
- Registry/Controller/REST 경로를 거치지 않고 합성 `TeamTask`를 직접 실행
- `pytest.mark.live`로 표시해 기본 pytest 실행에서 제외

## 2. 검증 항목

테스트는 OpenAI API 키가 없을 때만 `pytest.skip`하고, 키가 있으면 실제 LLM 호출 후 다음을 확인한다.

- `result.outcome`이 `completed` 또는 `escalated`
- `result.decisions`가 비어 있지 않음
- 한 번의 `execute()` 호출로 검증

## 3. 재현 명령 및 실제 출력

### 기본 실행

명령:

```powershell
python -m pytest tests/live/test_response_review_live_smoke.py -q
```

출력:

```text
1 deselected, 1 warning in 1.76s
```

프로젝트의 `.pytest_cache` 생성 권한 경고로 프로세스 종료 코드는 1이었지만, 해당 테스트는 `deselected`되었고 테스트 실패는 없었다.

### 실 라이브 실행

명령:

```powershell
python -m pytest tests/live/test_response_review_live_smoke.py -m live -q
```

출력 요약:

```text
F                                                                        [100%]
FAILED tests/live/test_response_review_live_smoke.py::test_response_generation_review_team_with_real_llm
openai.APIConnectionError: Connection error.
PermissionError: [WinError 10013] 액세스 권한에 의해 숨겨진 소켓에 액세스를 시도했습니다
1 failed, 2 warnings in 5.34s
```

API 키는 비어 있지 않아 스킵되지 않았고, 실제 `OpenAITeamLLM` 호출까지 수행되었다. 다만 현재 실행 환경의 외부 네트워크/소켓 정책이 `api.openai.com:443` 연결을 차단하여, LLM 응답 및 `result` 검증까지 도달하지 못했다. 따라서 이번 환경에서는 실 호출 통과를 확인하지 못했으며, 이를 통과로 간주하지 않는다.

## 4. 결과

- 테스트 파일 구현: 완료
- 기본 실행에서 라이브 테스트 제외: 확인
- API 키 미설정 스킵 경로: 미사용(API 키가 설정됨)
- 실 LLM 스모크 테스트 통과: 환경 네트워크 차단으로 미확인

## ★Claude 실 환경 검증 (2026-08-19)

Codex 샌드박스는 외부망이 막혀 있어 실 통과를 스스로 확인할 수 없었다 —
정직하게 "미확인"으로 보고한 것을 그대로 인정한다. Claude 의 실 환경
(네트워크 접근 가능)에서 재실행했다:

```powershell
python -m pytest tests/live/test_response_review_live_smoke.py -m live -v
```
```
tests/live/test_response_review_live_smoke.py::test_response_generation_review_team_with_real_llm PASSED
1 passed in 10.13s
```

실제 OpenAI 호출로 GEN→결정론 REV 사이클이 예외 없이 완주했고
`outcome ∈ {completed, escalated}`, `decisions` 비어있지 않음을 확인했다.
기본 `pytest -q` 도 재확인: **316 passed, 3 deselected**(라이브 테스트
3건 — 기존 2 + 이번 1 — 이 정상적으로 제외됨). `docs/evidence/
DoD-29_ResponseGenerationReview.md` 를 이 결과로 갱신했다.
