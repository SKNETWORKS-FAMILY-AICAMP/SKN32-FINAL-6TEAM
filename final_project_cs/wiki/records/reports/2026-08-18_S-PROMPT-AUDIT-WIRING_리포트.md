# 작업 리포트 — 프롬프트 감사추적 배선 구현

- 담당: Codex(S-PROMPT-AUDIT-WIRING, 구현) + Claude(계약 설계 · 프롬프트 콘텐츠 4건 직접 작성 ·
  독립 검증 · 잔여 결함 2건 직접 수정)
- 계획: `wiki/records/reports/debugs/2026-08-17_2340_프롬프트_감사추적_미연결.md` →
  `wiki/records/reports/2026-08-18_S-PROMPT-WIRING-DISCUSS_검토.md`(설계 교차검증) →
  `wiki/records/handoff/_prompts/S-PROMPT-AUDIT-WIRING.md`(이번 구현 계약)

## 1. 무엇을 했나

설계 리뷰에서 확정된 배선(등록·활성화는 advisory lock + 단일 트랜잭션,
`OpenAITeamLLM` 은 Controller 의 업무 트랜잭션과 분리된 짧은 트랜잭션으로
활성 프롬프트 조회·감사 기록, `run_id` 를 Team 호출부에서 명시 전달)을
그대로 구현했다.

- `app/tools/read_tools.py::register_prompt_files()` — 키를
  `{부모디렉터리}.{stem}` 으로 계산, 허용 목록(`ALLOWED_PROMPT_KEYS`) 밖은
  건너뛰고 반환값에 남김, advisory lock 아래 등록+활성화를 한 트랜잭션으로,
  활성 행 정확히 1개 검증
- `app/infrastructure/llm/openai.py::OpenAITeamLLM` — `connection_factory`
  주입(옵션, `None` 이면 기존 인라인 동작 하위호환), `complete()` 에
  `run_id` 파라미터 추가, 활성 프롬프트 없으면 외부 호출 전에 fail-closed,
  성공 호출 후 별도 트랜잭션으로 `llm_calls` 기록(`prompt_id`/`run_id`/
  `input_tokens`/`output_tokens`/`latency_ms` 포함), 감사 기록 실패 시
  `AuditWriteError` 로 명시적 실패(응답을 조용히 반환하지 않음)
- `app/modules/customer_ops/{order_shipping,return_exchange}.py` — LLM
  Protocol 에 `run_id` 파라미터 추가, 4개 호출부(각 팀의 answer/repair)에
  `run_id=task.run_id` 전달
- `app/composition.py` — `OpenAITeamLLM(connection_factory=get_connection)` 주입
- `scripts/register_prompts.py`(신규) — 배포 시 실행할 등록 명령
- `prompts/order_shipping/*.md`, `prompts/return_exchange/*.md`(각 2개,
  Claude 직접 작성) — 실제 정책 콘텐츠. Codex 는 이 파일들을 읽기만 했다
- 신규 테스트 6건(`tests/unit/tools/test_prompt_registration.py` 3건,
  `tests/integration/llm/test_llm_call_audit_wiring.py` 3건)

## 2. Claude 가 독립적으로 확인한 것 (Codex 자기보고를 그대로 믿지 않음)

- `git diff` 로 5개 파일 변경 내용을 전부 줄 단위로 읽고 계약 §2~§6 의
  요구사항과 대조했다 — 키 계산, advisory lock, active 유일성 검증,
  connection_factory 분리, fail-closed, `run_id` 전달까지 전부 계약대로다.
- `git status` 로 금지 영역(`app/core`, `app/domain`, `app/application`,
  마이그레이션, `prompts/**` 콘텐츠)에 변경이 없음을 확인했다.
- `prompts/order_shipping/*.md`·`prompts/return_exchange/*.md` 4개 파일의
  줄 수·내용이 Claude 가 작성한 그대로임을 확인했다(Codex 가 읽기만 하고
  고치지 않았다).
- `python -m scripts.register_prompts` 를 실제로 실행해 4개 키 등록·
  active=true 1개씩임을 DB 직접 조회로 확인했다.
- `python -m pytest tests/unit/tools/test_prompt_registration.py
  tests/integration/llm/test_llm_call_audit_wiring.py -v` → **6 passed**.
  각 테스트가 실제로 무엇을 검사하는지 코드를 읽고, mock 이 진짜
  `OpenAITeamLLM.complete()` 구현을 그대로 태우는지(응답 조립·JSON 파싱·
  usage 추출·별도 트랜잭션 기록까지) 확인했다 — 껍데기 테스트가 아니다.
- `python -m pytest -q` → **304 passed**(기존 298 + 신규 6), 회귀 0.

## 3. Codex 자기보고와 실제가 달랐던 것

Codex 의 완료 메시지가 "변경 파일" 목록에서 `app/composition.py`,
`app/modules/customer_ops/{order_shipping,return_exchange}.py` 를
**빠뜨렸다** — `git diff` 로 직접 확인하지 않았다면 §5·§6 이 실제로
반영됐는지 몰랐을 것이다. 세 파일 모두 실제로는 계약대로 정확히
수정돼 있었다(§2 에서 확인). **자기보고 요약을 그대로 믿지 않는 이유가
다시 한번 실측으로 확인됐다.**

## 4. Claude 가 추가로 발견·직접 수정한 것 (Codex 범위 밖)

### 4-1. 신규 테스트가 공유 DB에 잔재를 남김

`test_same_version_with_different_content_fails` 가 `prompts` 테이블에
`prompt_key='order_shipping.answer', version='999'` 행을 만들고
파일시스템 정리만 하고 DB 행은 안 지웠다 — `prompts` 테이블은 tenant 로
격리되지 않는 전역 테이블이라 이 잔재가 그대로 남는다. `finally` 블록에
DB DELETE 를 추가해 고쳤다. 이미 남아 있던 잔재 1건도 수동으로 지웠다.

### 4-2. `register_prompts.py` 가 정상 배포에서도 항상 실패 종료했다

계약 자체의 설계 공백이었다 — "허용 목록 밖 파일이 있으면 종료 코드
0 이 아닌 값"이라고 명시했는데, `prompts/billing/`·`prompts/technical/`
(옛 도메인, 이번 결함 리포트의 "결정 보류 항목 2번")가 저장소에 남아 있는
한 **매번** 건너뛰기 대상으로 잡혀 종료 코드 2 를 낸다. 즉 정상 배포에서도
항상 "실패"로 보이는 배포 스크립트가 됐다.

보류돼 있던 결정 2번(옛 도메인 프롬프트 12개 파일 처리)을 가장 덜
침습적인 선택지로 풀었다 — 내용은 그대로 두고 `legacy/final_project_sample/prompts/`
로 이동(`git mv`, `RULE.md` §4.2 의 `legacy/<원본프로젝트명>/<원본경로>`
관례를 따름). 재실행 결과 `python -m scripts.register_prompts` 가
**exit 0** 으로 정상 종료함을 확인했다.

## 5. 실 LLM 종단 검증과 한계

`tests/live/test_feedback_classifier_live_e2e.py -m live` 를 재실행해
**통과**를 확인했다(라이브 프롬프트 미등록 상태였다면 이 테스트는
`OpenAITeamLLM` 의 fail-closed 로 인해 실패했을 것이다 — 이번 세션에서
`register_prompts` 를 먼저 실행해 뒀기 때문에 통과했다는 뜻이다).

★단, 이 테스트와 이어서 직접 실행한 수동 종단 확인(실 주문 데이터가 있는
데모 고객으로 실제 Controller 를 태움) **둘 다 `order_shipping.py` 의
결정론적 환불 제안 분기(`delivered and order` 일 때 LLM 을 거치지 않고
바로 `ActionProposal` 생성)를 탔다** — 즉 이번 세션의 실측만으로는
`_llm_answer()`(실제 `OpenAITeamLLM.complete()` 호출 경로)가 **실 OpenAI
호출로** 끝까지 도는 것까지는 확인하지 못했다. `llm_calls` 테이블을
직접 조회해 0건임을 확인하고 실측 대상 Case 는 정리했다.

이 경로 자체는 `tests/integration/llm/test_llm_call_audit_wiring.py::
test_complete_records_prompt_and_run` 이 **실제 `OpenAITeamLLM.complete()`
구현**(OpenAI 클라이언트와 DB connection 만 mock)을 태워 `prompt_id`/
`run_id`/tokens 가 정확히 기록되는지 검증한다 — 껍데기 mock 이 아니라
실코드 경로 검증이다. 하지만 **정책 근거가 부족해 LLM 이 실제로 판단해야
하는 시나리오**(예: 배송 미완료·정보 부족 등, `delivered` 분기를 안 타는
경우)로 실 OpenAI 호출까지 종단 확인하는 것은 이번 세션에서 하지 않았다.
다음에 이 경로를 직접 여는 실 시나리오가 필요하면 별도로 확인해야 한다.

## 6. 검증 로그

```
python -m scripts.register_prompts
등록: (4개 UUID)
활성 프롬프트 4개 검증 완료 (등록/재사용 4개)
exit: 0

python -m pytest tests/unit/tools/test_prompt_registration.py tests/integration/llm/test_llm_call_audit_wiring.py -v
6 passed in 1.36s (수정 후 재실행: 3 passed, 3 passed)

python -m pytest -q
304 passed, 2 deselected in ~22-24s (두 차례 재확인)

python -m pytest tests/live/test_feedback_classifier_live_e2e.py -m live -q
1 passed in 5.01s
```

## 7. 남은 위험

- §5 의 한계 그대로 — 실 OpenAI 호출을 실제로 타는 시나리오의 종단
  `llm_calls` 적재는 미확인이다. 배송 미완료 등 LLM 판단이 실제로
  필요한 실 시나리오로 다음에 한 번 더 확인하는 것을 권한다.
- `AuditWriteError` 발생 시 이미 받은 LLM 응답을 버리는 설계다(계약
  §3.2-5 의 "응답을 버리지 말라"는 문구와 "예외를 던지라"는 요구가
  내적으로 살짝 충돌했는데, Codex 가 fail-closed 쪽으로 풀었다 — 이
  판단에 동의해 그대로 뒀다. 근거 없는 답을 내느니 실패하는 게 이
  프로젝트의 일관된 태도다).
