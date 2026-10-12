# 작업 — final_project_sample 의 남은 문서 4건을 쓴다

## 배경

`final_project_cs` 가 릴리스로 나가더라도 `final_project_sample` 은 **혼자 정확히
굴러가야 한다.** 그래서 sample 의 내부 구현 설명이 필요하다.

이미 22건을 썼고 4건이 남았다.

## ★ 절대 하지 말 것

1. **`final_project_cs/` 아래 파일을 열지 마라.** 경로만 바꾼 사본이 나온다.
2. **`program/` 아래 wiki 문서도 열지 마라.** 단 아래 "이미 쓴 문서" 는 예외다 —
   중복을 피하려면 봐야 한다.
3. **없는 것을 있다고 쓰지 마라.** 디렉터리를 언급하기 전에 `ls` 로 확인한다.
4. **테스트를 돌렸다고 쓰지 마라.** 실제로 돌리지 않았으면 적지 않는다.
   (전에 codex 가 "테스트 10개를 실행했다" 고 썼는데 실행 흔적이 없었다)
5. `build/`·`dist/`·`__pycache__` 는 읽지 마라.

## 이미 쓴 문서 (중복 피하려고 본다)

```
final_project_sample/wiki/runtime/     case-lifecycle · shared-state
                                               conflict-retry · idempotency · context-pack
final_project_sample/wiki/teams/       team-contract · team-boundary · team-registry
final_project_sample/wiki/composer/    write-channel · auth-scope · ui-boundary · design-gap
final_project_sample/wiki/quality/     architecture-tests · domain-free
                                               another-domain · verification
```

## 만들 문서 4건

| 파일 | 답해야 할 질문 | 읽을 것 |
|---|---|---|
| `runtime/agentic-controller.md` | Controller 가 Case 를 어떻게 굴리나. 무엇을 언제 부르나 | `acop_basement/application/controller.py`, `tests/integration/controller/` |
| `runtime/message-broker.md` | 메시지를 어떻게 보내고 받나. 실패하면 | `acop_basement/core/case_runtime/messaging/`, `scripts/run_outbox_worker.py`, 관련 테스트 |
| `quality/invariants.md` | sample 이 깨면 안 되는 규칙 목록 | `tests/architecture/`, `tests/contract/`, `tests/contracts/` |
| `teams/example-teams.md` | 예시 Team 이 무엇을 보여주려고 있나 | `acop_basement/teams/`, `app/modules/`, `examples/` |

### `quality/invariants.md` 는 형식이 정해져 있다

각 불변식에 ID 를 붙인다. **`INV-SAMPLE-<영역>-<번호>`** 형식이다.

```markdown
### `INV-SAMPLE-ARCH-001` — basement 는 도메인 어휘를 쓰지 않는다

`[실측]` `tests/architecture/test_basement_is_domain_free.py`

무엇을 막나: ...
```

영역은 `ARCH`(구조) · `RUN`(런타임) · `TEAM`(Team 계약) · `SEC`(보안) 중에서 고른다.
**테스트가 실제로 강제하는 것만 적는다.** 강제 안 되는 규칙은 적지 않는다.

### `teams/example-teams.md` 에 반드시 넣을 것

★sample 의 예시 Team 은 **"계약이 성립한다는 증거"** 이지 제품이 아니다.
  이걸 `final_project_cs` 의 릴리스 완료로 착각하면 안 된다는 경고를 넣어라.

## 형식

```yaml
---
type: concept
title: <한 줄 제목>
description: <한 문장>
status: draft
tags: [<아래에서만>]
---
```

`tags`: `architecture`, `state`, `contract`, `api`, `testing`, `security`, `data`, `agent`

- 한국어. 각 문서 **300줄 이하.** 결론 먼저. 부제·훈계조 금지.
- 코드에서 확인한 값에는 [실측], 확인 못 한 것은 [미확보].
- 파일과 줄 번호를 근거로 댄다. 예: `core/registry.py:88`
- 마지막에 `## 관계` 절, 형제 문서를 상대경로로 링크.

## 출력 형식

```
===== FILE: runtime/agentic-controller.md =====
<내용>

===== FILE: runtime/message-broker.md =====
<내용>
```

다른 설명은 붙이지 마라.
