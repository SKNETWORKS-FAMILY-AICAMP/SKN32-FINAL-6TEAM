---
type: concept
title: 지표와 산식
description: 평가 지표 15종의 정의. 근거 관련 4종이 이 프로젝트의 주장을 직접 떠받친다
status: draft
tags: [evaluation]
owners: [human:미배정]
size_exempt: true
size_exempt_reason: 지표 카탈로그. 산식을 찾을 때 한 파일에서 검색하는 게 빠르다
---

# 지표와 산식

## 기본 지표

| 지표 | 산식 |
|---|---|
| task success | 성공 Case 수 / 전체 Case 수 |
| intent accuracy | 정확한 intent 수 / 분류 가능 Case 수 |
| issue macro-F1 | issue별 F1 평균 |
| groundedness | 근거 있는 핵심 주장 수 / 전체 핵심 주장 수 |
| resolution rate | resolved 수 / 전체 수 |
| intervention | 승인·수동 handoff 수 / 전체 수 |
| p95 latency | Case 완료 시간의 95 percentile |
| cost/case | LLM 비용 합 / Case 수 |
| VOC precision | 유효 alert 수 / 검토 alert 수 |

## ★ 근거 지표 — 이 프로젝트의 핵심

일반적인 RAG 평가에 없는 것들이다. **"잘못 자동화하지 않는다"는 주장을 이 넷이 증명한다.**

| 지표 | 산식 | 무엇을 잡나 |
|---|---|---|
| **근거 정합률** | Context/DB에 실재·일치한 proposal 필드 수 / 모델 proposal 필드 수 | 답이 실제 데이터에 붙어 있는가 |
| **근거 초과율** | Context/DB에 없는 proposal 주장 수 / 전체 proposal 주장 수 | **할루시네이션** |
| **적절한 기권율** | 근거 부족·불일치에서 escalate한 수 / 해당 fixture 수 | 모를 때 모른다고 하는가 |
| **과잉 기권율** | 근거 충분한데 escalate한 수 / 근거 충분 fixture 수 | 알 수 있는데 넘기는가 |
| 스키마 준수율 | 파싱·계약 검증 통과 출력 수 / 전체 모델 출력 수 | 계약을 지키는가 |

### 기권 두 지표가 균형이다

```
적절한 기권율 ↑  →  안전하다
과잉 기권율   ↑  →  쓸모없다
```

**둘 다 봐야 의미가 있다.** 적절한 기권율만 보면 "전부 escalate"가 만점이 된다. 과잉 기권율만 보면 "전부 자동 응답"이 만점이 된다.

이 균형점이 [../product/personas.md](../product/personas.md)의 정미라가 사는 것이다 — **어디까지 자동화해도 안전한지**의 답.

### 근거 지표가 못 잡는 것

**결정론적 코드의 계산 오류는 못 잡는다.** 근거 대조는 "모델이 주장한 값이 Context에 있는가"를 보는데, Context 자체가 틀리면 통과한다.

실례가 [../decisions/D-001-payment-ownership.md](../decisions/D-001-payment-ownership.md)의 환불 계산식이다. `total_cents × 수량 ÷ item_count`는 근거 대조를 통과하지만 답이 틀렸다.

**이건 지표의 한계이고 별도 조치가 필요하다.**

## 페르소나 연결

| 페르소나 | 지표 |
|---|---|
| 박선영 (고객) | `groundedness`, `근거 정합률` |
| 김도현 (상담원) | `p95 latency`, `intervention` |
| 정미라 (운영 책임자) | `적절한 기권율`, `과잉 기권율`, `근거 초과율` |

## 목표치

`[미확보]` 대부분 정하지 않았다.

| 지표 | 현재 | 목표 |
|---|---|---|
| cost/case | 3.03원 `[실측]` | `[미확보]` |
| p95 latency | 32.2초 `[실측]` | `[미확보]` — 채팅 지원하려면 대폭 개선 필요 |
| 근거 초과율 | `[미확보]` | 0에 가까울수록 |
| 과잉 기권율 | `[미확보]` | `[미확보]` |

**목표치를 정하려면 실제 분포를 먼저 봐야 한다.** 임의 숫자를 넣지 않는다.

## 관계

- [golden-set.md](golden-set.md) — 이 지표를 재는 데이터
- [protocol.md](protocol.md) — 측정 절차
- [judge.md](judge.md) — 일부 지표는 Judge가 판정한다
- [../business/unit-economics.md](../business/unit-economics.md) — 오류율이 돈이 되는 경로
