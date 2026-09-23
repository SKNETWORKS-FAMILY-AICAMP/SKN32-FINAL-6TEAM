# S-CAPABILITY 리포트

## 변경 요약

Controller가 Billing/Technical capability를 직접 판정하던 경로를 제거하고, 주입받은 `TeamRegistry`에 `case_type`과 `intent`를 질의하도록 변경했다.

Registry는 다음 순서로 Team을 해석한다.

1. `supported_contract_versions`가 호환되는 등록 Team만 대상으로 한다.
2. `active=True`이고 `accepted_case_types`에 case type이 있는 Team만 후보로 둔다.
3. intent namespace와 일치하는 capability를 우선한다.
4. 후보가 정확히 하나가 아니면 `RegistryError`를 발생시킨다.

비활성 Team은 등록 자체는 가능하지만 라우팅 후보가 되지 않는다. 해석 실패는 Controller에서 기본 Team으로 대체하지 않고 `ROUTING_FAILED`를 기록한 뒤 `escalated`를 반환한다. `app/core/registry.py`는 계속 `app.modules`를 import하지 않는다.

## `_capability()` 변경 전후

변경 전에는 `intent`와 `issue_code`에 `technical`, `entitlement`, `access`가 포함되는지 검사해 두 capability 중 하나를 반환했다.

```python
intent = (case.get("intent") or "").lower()
issue = (case.get("issue_code") or "").lower()
return "entitlement.diagnose" if "technical" in intent or "entitlement" in issue or "access" in issue else "billing.investigate"
```

변경 후에는 Team 이름과 capability vocabulary를 Controller가 알지 않고 Registry에 위임한다.

```python
intent = case.get("intent")
entry = self.registry.resolve(case_type=intent or "", intent=intent)
return self.registry.capability_for(entry, intent)
```

실제 라우팅에서도 같은 Registry 해석 결과의 manifest와 capability를 사용한다. 따라서 새 `demo` Team의 `demo.investigate`도 Controller 수정 없이 선택된다.

## 새 Team 추가 시 고쳐야 할 파일 수

구조검사의 기존 산정은 `Team 모듈 1개 + composition root 1개 = 최소 2개`였다.

이번 수정 뒤에도 실제 운영 등록을 포함한 총 파일 수는 **2개**다. 다만 Controller의 capability 하드코딩 파일은 더 이상 수정 대상이 아니다. 즉, 새 Team 구현/manifest 파일 1개와 Registry를 구성하는 기존 composition root 파일 1개만 필요하며, Controller와 Core Registry의 Team별 코드는 0개다. 테스트에서는 주입된 `TeamRegistry([기존 Team..., DemoTeam()])`만으로 새 Team 라우팅을 입증했다.

## §3 테스트 결과 원문

핵심 변경 범위:

```text
python -m pytest tests/contract/test_core_isolation.py tests/unit/ports/test_team_ports.py tests/integration/controller/test_controller_integration.py -q
16 passed, 1 warning
```

전체 요청 명령:

```text
python -m pytest tests -q
123 passed, 3 failed, 1 deselected, 2 warnings
```

실패한 3건은 모두 `tests/integration/rag/test_rag_integration.py`의 OpenAI Embeddings 호출이며, 구현 변경과 무관하게 외부 연결에서 실패했다.

```text
httpx.ConnectError: [WinError 10013] 액세스 권한에 의해 숨겨진 소켓에 액세스를 시도했습니다
openai.APIConnectionError: Connection error.
```

`live` 테스트는 1건 deselected 상태다. RAG를 제외한 나머지 테스트는 다음과 같이 통과했다.

```text
python -m pytest tests -q -k "not rag"
122 passed, 5 deselected, 1 warning
```

