# S-AUDIT-SWEEP 정밀 감사 리포트

- 감사일: 2026-08-18
- 읽기 범위: `app/tools/**`, `app/infrastructure/**`, `scripts/**`
- 판정 규칙: 패턴 A/B/C만 조사했다. 테스트와 문서의 호출 표기는 런타임 호출 판정에서 제외했다.
- 변경 범위: 이 리포트 파일만 생성했다. 읽기 대상 파일은 수정하지 않았다.

## 요약

- 패턴 A: 0건 발견
- 패턴 B: 3건 발견 후보. 모두 런타임 경로에 연결되지 않은 프롬프트/LLM 감사추적 경로다.
- 패턴 C: 0건 발견

## 패턴 A — DB row 작성 호출에서 상태 기본값 누수

### 판정: 0건 발견

기본값이 있는 저장 함수는 다음과 같이 확인했다.

```text
rg -n "def (create_|insert_|register_)" app/infrastructure/db/repository.py
```

확인된 상태 관련 기본값은 `app/infrastructure/db/repository.py:42`의 `create_action_request(..., status: str = "proposed")`다. 저장소 전체 호출부는 다음으로 확인했다.

```text
rg -n --glob '!tests/**' "\\b(create_case|create_action_request|create_approval|create_prompt|create_llm_call)\\s*\\(" .
```

확인 결과:

- `app/presentation/api/cases.py:97`: `case.create`가 `status="succeeded"`를 명시한다.
- `app/presentation/api/cases.py:194-196`: `action.approve`가 `status=request.decision`을 명시한다.
- `app/application/controller.py:251-252`: Team action proposal이 `status="pending_approval"`를 명시한다.

따라서 조사 범위의 런타임 호출에는 `proposed` 기본값 누수가 발견되지 않았다. `create_prompt`의 `active=False`와 `create_case`의 선택적 `state_json`은 이번 패턴의 `status/state` 기본값 누수 조건에 해당하는 호출 문제로 판정하지 않았다.

## 패턴 B — 정의는 있으나 런타임 호출부가 없는 코드

호출부 검색은 정의 행 자체와 테스트·문서를 제외하고 다음 방식으로 교차확인했다.

```text
rg -n --glob '!tests/**' --glob '!docs/**' "\\bregister_prompt_files\\s*\\(" .
rg -n --glob '!tests/**' --glob '!docs/**' "\\brecord_llm_call\\s*\\(" .
rg -n --glob '!tests/**' --glob '!docs/**' "\\bcreate_llm_call\\s*\\(" .
```

### 1. 프롬프트 파일 등록 함수

- 파일: `app/tools/read_tools.py:118`
- 패턴: B
- 발견: `register_prompt_files(...)`가 정의되어 있으나 저장소 전체에서 정의 행 외 런타임 호출부가 0건이다. `register_prompts = register_prompt_files` 별칭도 `app/tools/read_tools.py:135`에 있지만 별칭을 호출하는 곳 역시 0건이다.
- 코드 인용: `ids.append(create_prompt(...))`로 내부 구현은 있으나, 이 함수에 진입하는 애플리케이션·스크립트 경로가 없다.
- 판단: 죽은 코드 후보. 프롬프트 파일을 DB의 `prompts` 행으로 등록하는 기능이 구현돼 보이지만 실제 배포/기동/요청 흐름에 배선되지 않았다. 단순히 CLI에서 수동 import하는 미사용 도구일 가능성은 코드만으로 확인되지 않아 “후보”로 기록한다.
- 심각도: 높음(운영 신뢰도). 프롬프트 버전·SHA 등록을 전제로 하는 감사추적 계약이 실제 DB에 반영되지 않을 수 있다.

### 2. LLM 호출 기록 도구

- 파일: `app/tools/read_tools.py:139`
- 패턴: B
- 발견: `record_llm_call(...)`는 정의 행 외 저장소 전체 런타임 호출부가 0건이다.
- 코드 인용: 함수 내부에서만 `app/infrastructure/db/repository.py:58`의 `create_llm_call(...)`을 호출한다.
- 판단: 죽은 코드 후보. LLM 호출 기록 DB writer를 감싼 함수는 존재하지만, 실제 Team 실행·API·스크립트 흐름에서 기록 함수가 호출되지 않는다. 따라서 `create_llm_call` 자체는 wrapper 내부의 1회 호출 외에는 연결되지 않은 하위 구현이다.
- 심각도: 높음(운영 신뢰도). 호출·토큰·지연·비용 추적이 저장된다고 가정하는 감사/비용 분석 결과가 비어 있을 수 있다.

### 3. LLM 호출 DB writer

- 파일: `app/infrastructure/db/repository.py:58`
- 패턴: B
- 발견: `create_llm_call(...)`의 저장소 전체 호출은 `app/tools/read_tools.py:143`의 `record_llm_call(...)` 내부 1건뿐이다. `record_llm_call`의 런타임 호출부는 0건이다.
- 판단: 직접 호출 0건인 완전한 고립 함수라고 단정하기보다는, 유일한 호출자가 죽은 wrapper인 “간접 죽은 코드”로 분류한다. `OpenAITeamLLM.complete()`나 Team 실행 경로가 이 writer 또는 wrapper를 호출하지 않는 것도 확인했다.
- 심각도: 높음(운영 신뢰도). DB writer가 존재한다는 사실만으로는 감사추적이 동작하지 않으며, 현재 연결 그래프상 실호출이 발생하지 않는다.

### 참고: 죽은 코드로 오판하지 않은 항목

- `app/tools/read_tools.py:38`의 `ReadToolbox`는 `app/composition.py:112`, `eval/runners/common.py:259`에서 생성된다.
- `app/infrastructure/messaging/outbox.py:12`의 `OutboxBrokerAdapter`는 `app/composition.py:162`, `app/presentation/ui/routes.py:99`에서 생성된다.
- `app/infrastructure/messaging/worker.py:8`의 `OutboxWorker`는 `scripts/run_outbox_worker.py:21`에서 생성되고 `process_once()`가 `scripts/run_outbox_worker.py:22`에서 호출된다.
- `app/infrastructure/llm/openai.py:11`의 `OpenAITeamLLM`은 `app/composition.py:173`, `app/presentation/ui/routes.py:101`에서 생성되고, `complete()`는 Team의 LLM 포트 호출 경로에서 사용된다.
- `scripts/**`의 검증·시드 함수들은 각 스크립트의 `main()` 또는 같은 스크립트 내부에서 호출되는 것을 확인했다.

## 패턴 C — 옛 구독·청구 도메인 잔재

### 판정: 0건 발견

요청된 검색을 그대로 실행했다.

```text
rg -rniE "\\bbilling\\b|\\bsubscription\\b|technical_entitlement|\\bentitlement\\b" app/tools app/infrastructure scripts
```

대상 경로에서 일치 결과가 0건이었다. 따라서 역사적 주석, 잘못된 현재 값, 판정 보류 항목 모두 기록할 대상이 없었다.

## 최종 변경 상태 확인

리포트 생성 후 `git status --short`를 실행한 결과다.

```text
 D "../A-COP_Mandate_Outcome_기수행구현계획서.md"
 D "../A-COP_Mandate_Outcome_문리합.html"
 D "../A-COP_구현계획서(4).md"
 D "../A-COP_구현계획서_A2A_Graph발현.md"
 D "../A-COP_구현계획서_v5.md"
 D "../A-COP_구현계획서_v6.md"
 D "../A-COP_구현계획서_v7.md"
 D "../A-COP_문리합(9).html"
 D "../A-COP_문리합_A2A_Graph발현_최종.html"
 D "../A-COP_문리합_v10.html"
 D "../A-COP_문리합_v7.html"
 D "../A-COP_향후안_문리합_우선추출소재리스트_발행물_2026-08-15.html"
?? wiki/records/handoff/_prompts/S-AUDIT-SWEEP.md
?? wiki/records/reports/2026-08-18_S-AUDIT-SWEEP_리포트.md
?? ../final_project_ui/UsersPLAYDA~1AppDataLocalTempfinal_project_ui-pytest-exact/
```

이 상태는 감사 시작 전에 이미 존재하던 변경 항목을 포함하므로, 완료 조건에 적힌 “리포트 한 줄(`??`)뿐”인 상태는 달성되지 않았다. 이번 감사에서 새로 생성한 항목은 마지막의 리포트 한 줄이며, 기존 항목은 보존하고 수정하지 않았다.

### 재검증한 실제 `git status --short` 출력

저장소 소유권 보호 때문에 명령 1회성 옵션을 사용해 재검증했다: `git -c safe.directory='C:/Users/playdata2/Documents/final_workspace' status --short`.

```text
 D "../A-COP_Mandate_Outcome_\\352\\270\\260\\354\\210\\240\\352\\265\\254\\355\\230\\204\\352\\263\\204\\355\\232\\215\\354\\204\\234.md"
 D "../A-COP_Mandate_Outcome_\\353\\270\\214\\354\\246\\254\\355\\225\\221.html"
 D "../A-COP_\\352\\265\\254\\355\\230\\204\\352\\263\\204\\355\\232\\215\\354\\204\\234(4).md"
 D "../A-COP_\\352\\265\\254\\355\\230\\204\\352\\263\\204\\355\\232\\215\\354\\204\\234_A2A_Graph\\353\\260\\230\\354\\230\\201.md"
 D "../A-COP_\\352\\265\\254\\355\\230\\204\\352\\263\\204\\355\\232\\215\\354\\204\\234_v5.md"
 D "../A-COP_\\352\\265\\254\\355\\230\\204\\352\\263\\204\\355\\232\\215\\354\\204\\234_v6.md"
 D "../A-COP_\\352\\265\\254\\355\\230\\204\\352\\263\\204\\355\\232\\215\\354\\204\\234_v7.md"
 D "../A-COP_\\353\\270\\214\\354\\246\\254\\355\\225\\221(9).html"
 D "../A-COP_\\353\\270\\214\\354\\246\\254\\355\\225\\221_A2A_Graph\\353\\260\\230\\354\\230\\201_\\354\\265\\234\\354\\242\\205.html"
 D "../A-COP_\\353\\270\\214\\354\\246\\254\\355\\225\\221_v10.html"
 D "../A-COP_\\353\\270\\214\\354\\246\\254\\355\\225\\221_v7.html"
 D "../A-COP_\\355\\231\\225\\354\\236\\245\\354\\225\\210_\\353\\270\\214\\354\\246\\254\\355\\225\\221_\\354\\232\\260\\354\\270\\241\\354\\266\\225\\354\\206\\214\\353\\240\\210\\354\\235\\274_\\353\\236\\230\\355\\215\\274\\353\\237\\260\\354\\212\\244\\353\\260\\230\\354\\230\\201_2026-08-15.html"
?? wiki/records/handoff/_prompts/S-AUDIT-SWEEP.md
?? "wiki/records/reports/2026-08-18_S-AUDIT-SWEEP_\\353\\246\\254\\355\\217\\254\\355\\212\\270.md"
?? ../final_project_ui/UsersPLAYDA~1AppDataLocalTempfinal_project_ui-pytest-exact/
```
