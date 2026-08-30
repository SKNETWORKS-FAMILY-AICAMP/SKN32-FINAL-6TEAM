# S-PROMPT-KEY-REGISTRATION-GAP — Response Generation & Review 팀이 운영 경로에서 항상 죽고 있었다

## 발견 경위

DoD-28 파인튜닝 모델의 RAG 통합 경로를 설계하던 중(`docs/plans/2026-08-30_DoD28-FT-RAG통합_설계.md`),
그 설계의 전제조건인 "`response.generate` 프롬프트가 DB에 등록돼 있는가"를
직접 조회로 확인하다가 발견했다.

## 결함

`app/tools/read_tools.py:167` `ALLOWED_PROMPT_KEYS = frozenset()` — 2026-08-19
레거시 격리 작업(order_shipping/return_exchange 프롬프트 제거, `docs/handoff/_prompts/S-LEGACY-ISOLATE-ORDER-RETURN-TEAMS.md`)
이후 **완전히 비어있는 채로 방치**돼 있었다. `prompts` DB(`acop_cs`)를 직접
조회하니 `response.generate`/`response.review_tone` 행이 **아예 존재하지
않았다**(0 rows) — 애초에 이 두 prompt_key용 템플릿 파일 자체가 저장소에
없었다(`prompts/` 아래엔 judge 프롬프트뿐).

`app/infrastructure/llm/openai.py:47-48`:
```python
if len(rows) == 0:
    raise RuntimeError(f"no active prompt registered for {prompt_key}")
```

`app/composition.py:179`의 production 배선(`OpenAITeamLLM(connection_factory=get_connection)`)은
항상 이 DB 조회 경로를 탄다. 즉 **v8 CS Pack 확정 팀 2개 중 하나인
"Response Generation & Review" 팀이 실제 REST API로 들어오는 모든 요청에서
`RuntimeError`로 죽고 있었다** — 코드 배포 이후 단 한 번도 정상 동작한
적이 없었을 가능성이 높다.

### 왜 테스트가 못 잡았나

`tests/live/test_response_review_live_smoke.py`(이 팀의 유일한 실 LLM
테스트)가 `OpenAITeamLLM()`을 **`connection_factory` 없이** 생성한다 —
이 경우 `openai.py:39`의 `if self.connection_factory is not None:` 분기를
타지 않고 DB 조회 자체를 건너뛴 채 하드코딩된 fallback instructions로
바로 OpenAI를 호출한다. 그래서 이 테스트는 production이 절대 쓰지 않는
경로만 검증하고 있었다 — "302 passed"가 이 결함을 숨긴 이유다.

★기존 `tests/unit/tools/test_prompt_registration.py::test_prompt_registration_allowlist_is_empty`가
"허용목록은 비어있다"를 그대로 assert하고 있어서, 이 결함이 회귀 테스트
스위트 안에서 오히려 "정상"으로 잠겨 있었다 — 결함이 아니라 **의도된 스냅샷을
영구 규칙으로 착각**한 경우다.

## 재현

```python
llm = OpenAITeamLLM(connection_factory=get_connection)
await ResponseGenerationReviewTeam(llm).execute(task)
# RuntimeError: no active prompt registered for response.generate
```

## 수정

1. `prompts/response/generate.v1.md`, `prompts/response/review_tone.v1.md` 신규 작성 —
   `response_review.py`가 실제로 기대하는 출력 스키마(`final_response_text`,
   `claims`, `escalation` / `tone_ok`)에 맞춰 evidence 근거·PII 금지·
   claims 검증 가능성을 명시.
2. `ALLOWED_PROMPT_KEYS`에 `"response.generate"`, `"response.review_tone"` 추가.
3. `python -m scripts.register_prompts` 실행 — DB에 두 prompt_key 모두
   `active=true`로 등록 확인(직접 조회).
4. 재현 스크립트로 실제 OpenAI 호출까지 성공 확인 — evidence에 근거한
   답변(`배송 예정일은 2026-08-31입니다...`)이 정상 생성됨.
5. 회귀 테스트 추가:
   - `tests/unit/test_prompt_key_registration.py` — Team이 실제로 부르는
     prompt_key가 항상 `ALLOWED_PROMPT_KEYS`에 있는지, 그 키에 대응하는
     템플릿 파일이 디스크에 있는지 강제(`feedback.INTENTS ⊇ accepted_case_types`
     불변조건 테스트와 같은 패턴).
   - `tests/live/test_response_review_live_smoke.py`에
     `test_response_generation_review_team_with_db_audited_llm` 추가 —
     production과 동일하게 `connection_factory=get_connection`으로 생성한
     LLM으로 실제 실행, 이번에 놓쳤던 경로를 앞으로는 확실히 덮는다.
   - `test_prompt_registration_allowlist_is_empty` → `test_prompt_registration_allowlist_matches_cs_pack_teams`로
     의도 변경 — "영원히 비어있다"가 아니라 "지금 CS Pack이 쓰는 키와
     일치한다"로.
6. `scripts/register_prompts.py`의 하드코딩된 "활성 프롬프트 4개" 메시지를
   `len(ALLOWED_PROMPT_KEYS)` 동적 계산으로 수정(레거시 4개에서 지금 2개로
   바뀌었는데 메시지가 안 바뀌어 있었다).

## 검증

`python -m pytest -q -m "not live"` → 406 passed(기존 404 + 신규 2개).
`python -m pytest -q -m live` (response_review 관련) → 2 passed, DB-audited
경로 포함.

## 영향 범위

- `order_shipping.answer`/`order_shipping.answer.repair`/`return_exchange.answer`/`return_exchange.answer.repair`
  4개 레거시 prompt_key는 DB에 그대로 남아있지만(과거 등록분, active 상태
  다양) 어떤 활성 Team도 더 이상 그 prompt_key를 호출하지 않으므로 무해한
  잔존 데이터다 — 이번 수정 범위 밖, 정리하지 않았다.
- 이 결함은 DoD-28 RAG 통합 설계와 무관하게 **그 자체로 CS Pack 릴리스를
  막는 결함**이었다. RAG 통합 작업의 전제조건 확인 과정에서 우연히
  발견됐을 뿐이다.
