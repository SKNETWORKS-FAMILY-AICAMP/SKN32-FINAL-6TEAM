---
type: guide
title: Research
description: 외부 조사와 비교 분석. 결정이 끝난 것은 여기 없고 decisions/에 있다
status: draft
---

# Research

**알아본 것**을 두는 곳이다. **정한 것**은 [../decisions/index.md](../decisions/index.md)에 있다.

결정 문서가 여기 문서를 `sources`로 참조한다. 조사가 결정의 재료다.

## 왜 나누는가

둘을 섞으면 두 가지가 나빠진다.

1. **결정을 찾으려는 사람이 조사 자료를 헤맨다**
2. **조사를 업데이트할 때 결정까지 흔들린 것처럼 보인다**

조사는 계속 쌓이고 결정은 드물게 바뀐다. 변경 주기가 다르면 다른 문서다. → [../governance/structure-guide.md](../governance/structure-guide.md)

## 목록

| 문서 | 주제 | 결정으로 이어졌나 |
|---|---|---|
| [graphrag.md](graphrag.md) | GraphRAG와 Graph Store 비교 | → [D-002](../decisions/D-002-graph-store-gate.md) |
| [a2a-adoption.md](a2a-adoption.md) | A2A 채택 현황과 개인 AI 경로 | 부분 |
| [mt-benchmark.md](mt-benchmark.md) | 번역 모델 비교 | `[미확보]` |

## 조사 문서에 반드시 있어야 할 것

| 항목 | 왜 |
|---|---|
| 조사 시점 | 외부 정보는 낡는다 |
| 출처 링크 | 재확인 가능해야 한다 |
| **1차 출처 확인 여부** | 인용의 인용인지 밝힌다 |
| 우리 환경 측정치가 아니라는 명시 | 외부 벤치마크를 우리 결과로 오해하면 안 된다 |

**마지막 줄이 중요하다.** 외부 리서치 수치를 우리 측정치처럼 쓰면 심사에서 무너진다.

```markdown
[외부] Vector RAG 대비 3~5배 비용.
이 수치는 외부 리서치 인용이며 우리 환경 측정치가 아니다.
```

## 인접 영역

- [../decisions/index.md](../decisions/index.md) — 조사가 결정이 되는 곳
- [../business/market.md](../business/market.md) — 시장 조사는 business에 있다
- [../governance/evidence-grades.md](../governance/evidence-grades.md) — `[외부]` 표기 규칙
