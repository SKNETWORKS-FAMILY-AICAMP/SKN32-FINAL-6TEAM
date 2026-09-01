---
type: guide
title: Operations
description: 로컬에서 돌리는 법과 자주 막히는 곳
status: draft
---

# Operations

## 각 문서

| 문서 | 답하는 질문 |
|---|---|
| [local-setup.md](local-setup.md) | 처음 어떻게 셋업하는가 |
| [run.md](run.md) | 무엇을 어떻게 실행하는가 |
| [troubleshooting.md](troubleshooting.md) | 막히면 어디를 보는가 |

## 자주 쓰는 명령

**테스트**

```bash
pytest tests/architecture
```

```bash
pytest tests/contract tests/security
```

**평가**

```bash
python -m eval.run --arm Proposed
```

## 환경

**Docker는 로컬 개발 환경에 없다.** 컨테이너화는 실제 배포 단계(Phase 2)에서 한다.

## 알려진 함정

`[실측]` 실제로 팀을 막았던 것들.

### Windows WDDM의 느린 실패

GPU 메모리가 초과되면 Linux는 즉시 OOM으로 죽는데 **Windows는 shared GPU memory(시스템 RAM, PCIe 경유)로 넘겨 극도로 느리게 처리하다 죽는다.**

`[실측]` 25분 걸려 실패한 사례가 있다.

**빠른 실패가 아니라 느린 실패라 장애 판정이 늦어진다.** 자체호스팅을 제품으로 만들면 Linux를 전제해야 한다.

### 12GB VRAM 한계

`[실측]` x600 (RTX 4070 SUPER 12GB)에서 `Qwen2.5-3B` 학습이 3번 막혔다.

| 시도 | max_length | 결과 |
|---|---|---|
| v4 | 11,264 | CUDA OOM (배치=1에서도) |
| v5 | 2,560 | OOM, 25분 소요 |
| v6 | 1,024 | 완주 |

우회는 `device_map="auto"`와 4-bit 양자화를 **모두 버리고** bf16으로 CPU에 올린 뒤 `.to("cuda")`로 옮기는 것이다. 재현 스크립트는 `eval/finetune/diag_3b.py`.

상세는 [../../../program/wiki/business/infrastructure-cost.md](../../../wiki/business/infrastructure-cost.md).

### Context Broker 우회

데이터 수확 스크립트가 `ContextBroker.build()`를 안 거치면 evidence가 중복돼 토큰이 폭증한다.

**Broker 우회 경로를 만들지 않는다.** → [../context/index.md](../context/index.md)

## 인접 영역

- [../quality/eval-harness.md](../quality/eval-harness.md) — 평가 실행
- [../data/migrations.md](../data/migrations.md) — DB 준비
