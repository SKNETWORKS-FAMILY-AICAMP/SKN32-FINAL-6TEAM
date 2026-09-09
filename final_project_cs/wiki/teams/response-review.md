---
type: concept
title: Response Generation & Review Team
description: 응답을 생성하고 스스로 검토한다. accepted_case_types가 비어 있는 유일한 Team이다
status: draft
tags: [agent, customer-operations]
owners: [human:미배정]
domain: commerce
domain_note: v10 §0-2 가 MVP 경로에서 제외한 커머스 Team 이다. 코드에는 아직 등록돼 있다
---

# Response Generation & Review Team

`app/modules/customer_ops/response_review.py` · `response_review_policy.py`

**CS Pack. 10주 착수 확정.**

## manifest

`[실측]`

```python
capabilities        = ["response.generate_review"]
accepted_case_types = []                    ← 비어 있다
required_context    = ["case_state", "policy", "db_facts", "history"]
allowed_tools       = ["read.policy"]
knowledge_scope     = ["response_review"]
max_steps           = 4
```

## ★ `accepted_case_types`가 비어 있다

**Case를 직접 받지 않는다.** 다른 Team이 만든 답변을 검토하는 자리다.

```
다른 Team → 초안
              ↓
Response Review → 생성·검토
              ↓
           최종 응답
```

`max_steps=4`로 다른 Team(6)보다 짧다. **검토는 조회가 아니라 판단이라 단계가 적다.**

## 권한이 가장 좁다

```python
allowed_tools   = ["read.policy"]
knowledge_scope = ["response_review"]
```

**주문·배송·반품을 못 본다.** 사실 확인은 앞 Team이 이미 했고, 이 Team은 **표현과 정책 준수**를 본다.

**권한을 좁게 준 게 설계 의도다.** 검토자가 원본 데이터를 다시 뒤지기 시작하면 앞 Team과 판단이 갈린다.

## 정책이 분리돼 있다

```
response_review.py          실행
response_review_policy.py   판정 기준
```

**정책을 코드에서 분리한 것은 이 Team뿐이다.** 검토 기준이 자주 바뀔 것을 예상한 구조다.

## DoD-29

`[실측]` **DoD 29번이 이 Team의 검증이다.** v8에서 신설됐고 **2026-09-01 완료됐다**
(`final_project_cs/wiki/records/evidence/DoD-29_ResponseGenerationReview.md`) — GEN→REV
두 호출 흐름이 실제로 실행되는지 증명하는 테스트가 빠져 있던 것을 발견해
채웠다(기존 테스트는 전부 `tone_ok`를 미리 박아 두 번째 호출을 건너뛰고 있었다).
재시도 상한·PII 차단은 그전부터 실제 테스트로 덮여 있었다.

1~29 전부 평가됐다 — evidence 29/29, 통과 26 · 부분통과 3(judge agreement·RC
선언·파인튜닝). `response_review.enabled`는 여전히 기본 `false`다 — 검증은
끝났지만 운영에서는 아직 안 켰다.

→ [../../../wiki/delivery/dod.md](../../../wiki/delivery/dod.md)

## ★ 실제로 죽어 있었다

`[실측]` 이 저장소에서 가장 뼈아픈 결함 중 하나다.

2026-08-19 레거시 Team 정리가 `ALLOWED_PROMPT_KEYS`를 **완전히 비운 채 CS Pack 신규 키로 채우지 않고 방치**했다.

그 결과 이 Team이 production DB-감사 경로로 호출될 때마다 이렇게 죽었다.

```
RuntimeError: no active prompt registered
```

**발견이 늦은 이유가 중요하다.** 이 Team의 유일한 실 LLM 테스트가 `connection_factory` 없이 LLM을 만들어 **그 경로 자체를 건너뛰었다.**

2026-08-30에 DB 직접 조회로 발견해 고쳤다. 프롬프트 2종을 새로 쓰고 allowlist를 갱신하고 회귀 테스트 3건을 추가했다.

`[실측 2026-09-06]` **같은 자리에 반대 방향의 구멍이 하나 더 있었다** — 커밋 `1dcfdae`(코드 담당 세션). `register_prompts.py`가 허용 목록 **안쪽만** 봤다("`response.generate`가 active 1개인가"). 목록 **밖**에 active가 남아 있는지는 아무도 안 봤고, 08-19에 `legacy/`로 옮겨진 `order_shipping`·`return_exchange`의 프롬프트 행 넷이 DB에 그대로 남아 **셋이 `active=true`**였다. 동작에 해는 없었지만(코드가 그 키를 요청하지 않고 `llm_calls` 참조 0건) "배포 중인 프롬프트가 몇 개인가"를 세면 2가 아니라 5로 보였다. 검사를 목록 밖까지 넓히자마자 셋을 잡았고(exit 3), **지우지 않고 `active=false`로 내렸다** — `prompts`는 "덮어쓰지 않고 공존시킨다"는 버전 기록이라 지우면 그때 무엇을 썼는지가 사라진다. active 5 → 2(`response.generate` v2 · `response.review_tone` v1). 회귀 `tests/contract/test_active_prompts_are_the_deployed_set.py`.

**교훈 — 테스트가 실제 경로를 안 타면 통과해도 의미가 없다.**

```
tests/integration/controller/test_response_review_wiring.py
tests/live/test_response_review_live_smoke.py
```

## 프롬프트

`[실측]`

```
prompts/response/generate.v1.md
prompts/response/review_tone.v1.md
```

`prompts` 테이블에 `(prompt_key, version)` UNIQUE + sha256 immutable로 등록된다. **활성 프롬프트가 없으면 fail-closed다.**

→ [../quality/eval-harness.md](../quality/eval-harness.md)

## 관계

- [team-contract.md](team-contract/index.md) — 계약
- [voc-store-manager.md](voc-store-manager.md) — 같은 CS Pack
- [../../../wiki/delivery/dod.md](../../../wiki/delivery/dod.md) — DoD-29
- [../../../wiki/evaluation/judge.md](../../../wiki/evaluation/judge.md) — 검토 품질 평가
