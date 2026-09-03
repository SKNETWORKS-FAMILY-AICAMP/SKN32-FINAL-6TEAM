---
type: report
title: 우리 GPU 로 무엇이 되고 무엇이 안 되나
description: 4070 SUPER 12GB 의 실제 한계. 카탈로그 12GB 와 쓸 수 있는 양이 다르다
status: draft
tags: [gpu, cost]
---

# 우리 GPU 로 무엇이 되고 무엇이 안 되나

`[실측]` 원본은 [infrastructure-cost.md](infrastructure-cost.md) §3 에 있었다. **분량이 넘쳐 떼어 냈다.**

## 장비

일반 시세로 4090을 가정하면 안 된다. 팀 최고 사양은 x600 머신의 **RTX 4070 SUPER 12GB(Windows)**이고, 이 제약이 이미 여러 번 막았다.

`[실측:S2]`

| 시도 | 설정 | 결과 |
|---|---|---|
| v4 | `max_length=11264` | **CUDA OOM** — 배치=1에서도 안 들어감 |
| v5 | `max_length=2560` | **여전히 OOM.** 25분 걸려 실패 — Windows WDDM이 초과분을 shared memory로 넘겨 느리게 끌다 죽음 |
| v6 | `max_length=1024` + evidence 400자 | 겨우 완주 (스텝당 7초) |

```
프로덕션 입력 중앙값 : 10,670 토큰
12GB에서 학습 가능   :  1,024 토큰
                       약 10배 부족
```

**자체호스팅 차별점이 지금 팀 장비에서 학습 기준으로는 성립하지 않는다.**

Windows WDDM의 "느린 실패"도 문제다. Linux는 즉시 OOM인데 Windows는 25분을 끈다. **자체호스팅 제품이면 Linux를 전제해야 한다.**

### 추론은 되는가 `[추정]`

위는 전부 **학습**이다. 추론은 활성값·옵티마이저가 없어 훨씬 가볍다.

```
Qwen2.5-3B (36층, KV헤드 2, head_dim 128, bf16)
KV 캐시 = 2 × 36 × 2 × 128 × 2바이트 = 36 KB / 토큰

건당 10,334 토큰 → 372 MB / 시퀀스
가중치 bf16 6.18 GB + WDDM 예약 1 GB

12 − 6.18 − 1 − 0.5 ≈ 4.3 GB → 동시 약 10 시퀀스
4-bit 양자화 시 → 동시 약 20 시퀀스
```

**계산상 된다. 하지만 측정이 아니다.** §6 참조.

## ★ [2026-09-03] x600 실측

`[실측]` SSH 로 x600 에 붙어 `nvidia-smi` 를 직접 읽었다.

```
NVIDIA GeForce RTX 4070 SUPER   WDDM
5831MiB / 12282MiB              0% 사용률
```

**GPU 는 놀고 있는데 메모리 5,831 MiB 가 이미 잡혀 있다.**

| 프로세스 | |
|---|---|
| `dwm.exe` | Windows 데스크톱 창 관리자 |
| `explorer.exe` | 탐색기 |

> **Windows 데스크톱이 절반을 먹는다.**

### 그래서 §3 의 계산이 낙관적이다

| | 값 |
|---|---|
| 카탈로그상 VRAM | 12,282 MiB |
| **데스크톱이 상시 점유** | **5,831 MiB (47%)** |
| **실제 쓸 수 있는 것** | **약 6,451 MiB** |

`[실측]` **3B 모델 bf16 이 약 6GB 다.** 가중치만으로 가용량을 거의 다 쓴다. KV 캐시가 들어갈 자리가 없다.

**§3 의 "12GB 에서 학습 가능 1,024 토큰" 도 이 절반 위에서 나온 값일 수 있다.**

### ★ 그런데 반대 증거가 있다 — 이 수치를 단정하면 안 된다

`[실측]` **DoD-28 파인튜닝이 이 기계에서 376/376 스텝을 완료했다.**

```
Qwen2.5-3B-Instruct   bf16   양자화 없음
가중치만    3.09B × 2바이트 ≈ 6.2GB
오늘 측정한 Free       6.17GB
```

**가중치가 여유분보다 크다. 그런데 돌았다.**

| 가능한 설명 | |
|---|---|
| **WDDM 이 데스크톱 메모리를 축출한다** | CUDA 가 요구하면 Windows 가 밀어낸다 |
| 학습 때는 데스크톱이 안 떠 있었다 | 원격 세션 끊긴 상태 |
| 내 가중치 추정이 틀렸다 | |

`[미확보]` **셋 중 무엇인지 확인 못 했다.** `diag_3b.py` 가 `get_memory_footprint()` 를 찍지만 **그 값이 문서에 안 남아 있다.**

> **그래서 "가용 6.4GB" 를 탈락 기준으로 쓰면 안 된다.** 축출이 된다면 12GB 에 가깝다.

**확인 방법은 하나다** — 실제로 로드해서 `nvidia-smi` 를 같이 보는 것. torch 설치가 선행된다.

`[실측]` **다만 확실한 것 하나는 있다.** 이 기계는 **한계에서 돌았다** — 같은 문서가 `CUDA OOM` 을 만나 gradient checkpointing 과 `PYTORCH_CUDA_ALLOC_CONF` 로 겨우 풀었다고 적고 있다.

### 이건 자체호스팅 논거를 강화한다

**"Windows 를 전제하면 안 된다"가 숫자로 나왔다.**

| | 가용 VRAM |
|---|---|
| Windows + 데스크톱 | **6.4GB** |
| 헤드리스 Linux `[추정]` | 12GB |

**같은 카드에서 두 배 차이다.** → [../decisions/D-004-self-hosting-rationale.md](../decisions/D-004-self-hosting-rationale.md)

## 관계

- [infrastructure-cost.md](infrastructure-cost.md) — 원가 전체
- [../evaluation/model-selection.md](../evaluation/model-selection.md) — 이 한계가 후보를 거른다
- [../decisions/D-004-self-hosting-rationale.md](../decisions/D-004-self-hosting-rationale.md) — 자체호스팅 논거
