---
type: concept
title: 예시 Team 이 무엇을 보여주나
description: 계약이 성립한다는 증거다. 제품이 아니다. 코드 없이 Team 을 늘리는 경로가 여기 있다
status: draft
tags: [architecture, contract, security]
---

# 예시 Team 이 무엇을 보여주나

## ★ 먼저 — 이걸 릴리스 완료로 보면 안 된다

> **sample 의 예시 Team 은 "계약이 성립한다는 증거"이지 제품이 아니다.**

sample 에 Team 이 구현돼 있고 Core 격리 위반이 0이다. **그건 Team-플러그인 구조가 동작한다는 증거일 뿐** `final_project_cs` 의 착수 목록이 아니다.

**이걸 혼동하면 "다 됐다"고 착각한다.** → [../index.md](../index.md)

| | 무엇을 증명하나 |
|---|---|
| **sample** | **계약이 성립한다** |
| **cs** | **그 계약 위에서 도메인이 돈다** |

## 무엇이 있나

`[실측]` `config/project.yaml` 에 활성 Team 은 **하나**다.

```yaml
- team_id: feedback_analytics
  implementation_ref: app.modules.customer_ops.feedback_team:FeedbackAnalyticsTeam
```

코드 쪽에는 더 있다.

```
app/modules/customer_ops/
  feedback_team.py · response_review.py · verification_policy.py
  team_modules/  local_team_a · local_team_b · remote_team_demo
```

`[실측]` **`team_modules/` 셋은 이름이 곧 목적이다** — 로컬 둘과 원격 하나. **Team 이 어디에 있든 같은 계약으로 붙는다**를 보이려고 있다. → [../runtime/agentic-controller.md](../runtime/agentic-controller.md)

## ★ 코드 없이 Team 을 늘리는 경로

`[실측]` `acop_basement/teams/declarative.py` — **선언형 Team 범용 실행기.**

> 지금까지 새 Agent Team 을 하나 늘리려면 **Python 을 새로 써서 배포**해야 했다.
> 이 실행기를 **한 번** 배포해 두면, 이후 새 Team 은 **코드 없이 선언만으로** 만든다.

선언은 `config/project.yaml` 의 `teams[].parameters` 다.

### 그런데 읽기 전용이다

`[실측]` 설계 경계가 코드에 적혀 있다.

> **`ActionProposal` 을 만들지 않는다.** 조회·정리·초안까지다.

**이유가 핵심이다.**

> side effect 가 필요하면 코드형 Team 을 써야 한다 — **선언(프롬프트)은 신뢰 경계 밖의 입력**이라, 거기서 결제·환불 제안이 나오게 두면 **프롬프트 인젝션이 곧 업무 조작이 된다.**

**선언으로 편해지는 만큼 권한을 좁혔다.** 편의와 권한을 같이 늘리지 않는다. → [../../wiki/decisions/D-005-write-gate.md](../../../wiki/decisions/D-005-write-gate.md)

### 권한 상한은 로드할 때 걸린다

`[실측]` `allowed_tools` 가 읽기 전용 접두사 밖이면 **`load_project_config()` 가 거부한다.**

> **grant ceiling 은 로드 시점에 이미 걸렸다.**

**실행 중에 검사하는 게 아니라 설정을 읽을 때 막는다.** 잘못된 선언은 기동조차 안 된다.

## 무엇을 배우려고 보나

| 보고 싶은 것 | 어디 |
|---|---|
| Team 이 받고 돌려주는 모양 | [team-contract.md](team-contract.md) |
| Team 이 하면 안 되는 것 | [team-boundary.md](team-boundary.md) |
| capability 로 찾는 법 | [team-registry.md](team-registry.md) |
| **코드 없이 늘리는 법** | 이 문서의 선언형 절 |

## 확인하지 못한 것

`[미확보]`

```
declarative.py 로 만든 Team 을 실제로 돌려 보지 않았다
team_modules/ 셋이 지금도 등록되는지 확인 안 했다
   (project.yaml 에는 feedback_analytics 하나뿐이다)
```

## 관계

- [index.md](index.md) — Team 영역
- [../quality/invariants.md](../quality/invariants.md) — 무엇이 강제되나
- [../composer/write-channel.md](../composer/write-channel.md) — 선언을 바꾸는 경로
