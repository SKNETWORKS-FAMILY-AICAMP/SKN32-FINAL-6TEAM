---
type: guide
title: Evaluation
description: 무엇으로 증명하는가. 지표·프로토콜·골든셋·Judge 루브릭
status: draft
---

# Evaluation

**주장을 숫자로 바꾸는 영역이다.**

[../product/positioning.md](../product/positioning.md)에서 "자동화율을 앞세우지 않고 잘못 자동화하지 않는 지점을 제시한다"고 했다. 그 약속을 지키는 게 여기다.

## 읽기 순서

1. [metrics.md](metrics.md) — 무엇을 재는가
2. [golden-set.md](golden-set.md) — 무엇으로 재는가
3. [protocol.md](protocol.md) — 어떻게 재는가
4. [judge.md](judge.md) — 사람 없이 어떻게 판정하는가

## 각 문서

| 문서 | 답하는 질문 |
|---|---|
| [metrics.md](metrics.md) | 지표 15종의 정의와 산식 |
| [golden-set.md](golden-set.md) | 72건이 어떻게 구성돼 있는가 |
| [protocol.md](protocol.md) | A/B/Proposed, 60+20, 통계 처리 |
| [judge.md](judge.md) | LLM-as-Judge 루브릭과 사람 라벨 일치도 |

## 핵심 지표 넷

전체 15종 중 이 프로젝트의 주장을 직접 떠받치는 것들.

| 지표 | 무엇을 증명하나 | 누구를 위한 것 |
|---|---|---|
| `근거 정합률` | 답변이 실재 데이터에 근거하는가 | 박선영 (고객) |
| `근거 초과율` | 없는 걸 지어내는가 | 박선영 |
| `적절한 기권율` | 모를 때 모른다고 하는가 | 정미라 (운영 책임자) |
| `과잉 기권율` | 알 수 있는데 넘기는가 | 정미라 |

**뒤의 둘이 균형이다.** 기권이 0이면 안전장치가 없는 것이고, 너무 많으면 자동화 이득이 사라진다. 이 균형점이 제품의 실체다.

페르소나 연결은 [../product/personas.md](../product/personas.md).

## 실측 현황

`[실측]` 새 도메인(쇼핑몰) 측정본만. golden 216건, 2026-08-28

| | Baseline A | Baseline B | Proposed |
|---|---|---|---|
| 건당 비용 | `[미확보]` | `[미확보]` | **3.03원** |
| p50 지연 | `[미확보]` | `[미확보]` | 20.0초 |
| p95 지연 | `[미확보]` | `[미확보]` | 32.2초 |

### ★ Baseline이 비어 있다

**2026-08-17 도메인 교체로 이전 측정이 전부 무효가 됐다.** Proposed는 재측정했지만 **Baseline A·B는 아직 안 했다.**

그래서 **"A-COP이 단순 LLM보다 낫다"를 지금은 수치로 말할 수 없다.** 비교군이 없으면 평가 설계 자체가 반쪽이다.

**중간발표 전에 재측정해야 한다.** 명령은 [protocol.md](protocol.md).

**지연은 여전히 약점이다.** 상세는 [../business/infrastructure-cost.md](../business/infrastructure-cost.md).

## 미확보

| 항목 | 필요한 것 |
|---|---|
| 3B 자체호스팅 모델의 정확도 | 골든셋 72건 재평가 |
| 4-bit 양자화 후 정확도 | AWQ/GPTQ 적용 후 재평가 |
| 사람 라벨 일치도 | 20건 사람 라벨 필요 |

## 인접 영역

- [../product/personas.md](../product/personas.md) — 지표가 누구의 개선을 증명하는가
- [../business/unit-economics.md](../business/unit-economics.md) — 오류율이 돈으로 환산된다
- [`quality/eval-harness.md`](../../final_project_cs/wiki/quality/eval-harness.md) — 실행 방법
