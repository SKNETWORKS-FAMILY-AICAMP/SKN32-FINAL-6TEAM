---
type: report
title: 폰에서 Gemma 4 를 돌려 봤다
description: Adreno 825 로 E4B 8.98 tok/s. 4070 SUPER 를 못 재는 동안 얻은 첫 자체 추론 실측
status: draft
tags: [gpu, cost, evaluation]
domain: neutral
---

# 폰에서 Gemma 4 를 돌려 봤다

`[실측]` 2026-09-03. **POCO F7 (Snapdragon, Adreno 825)** 에서 측정했다.

## 왜 폰인가

`[실측]` **x600 의 4070 SUPER 를 SSH(세션 0)로는 못 잰다.** 2.25GB 로 막힌다. **세션 1 로는 12GB 전부 확인했다** — [gpu-limits.md](gpu-limits.md). 이 문서는 그 사이에 잴 수 있는 데서 먼저 잰 기록이다.

## 결과

| 모델 | 크기 | 파라미터 | 백엔드 | **prefill** | **생성** |
|---|---:|---:|---|---:|---:|
| **Gemma 4 E4B** Q4_0 | 4.79 GiB | 7.46B | **Adreno 825** | **121.36 t/s** | **8.98 t/s** |
| Gemma 4 E4B Q4_0 | 4.79 GiB | 7.46B | CPU | 63.78 | 7.06 |
| **Gemma 4 E2B** Q4_0 | 2.63 GiB | 4.63B | Adreno 825 | **221.32** | **15.18** |

`[실측]` `llama-bench -p 128 -n 32 -r 1` · build `e4b9af007`

### GPU 가 CPU 보다 1.9배 빠르다

```
prefill   63.78  →  121.36 t/s     1.9배
생성       7.06  →    8.98 t/s     1.3배
```

**prefill 에서 차이가 크고 생성에서는 작다.** 생성은 메모리 대역폭에 묶인다.

`[실측]` **우리 워크로드는 prefill 이 무겁다** — 입력 중앙 8,909 토큰 / 출력 1,876. → [unit-economics.md](unit-economics.md)

**그래서 GPU 가 유리한 쪽이다.**

## ★ E4B 가 실제로 들어간다

`[실측]` Adreno 825 의 가용 메모리.

```
GPUOpenCL: QUALCOMM Adreno(TM) 825 (5616 MiB, 4592 MiB free)
```

**E4B Q4_0 이 4.79 GiB 라 4,592 MiB 에 겨우 들어간다.** E2B 는 여유가 있다.

**폰에서 4B 급이 돈다는 게 [model-selection](../evaluation/model-selection.md) 의 메모리 기준에 직접 걸린다** — 12GB 카드에서 못 돌 이유가 없다.

## 우리 응답 시간으로 환산하면

`[실측]` 실측 토큰 수를 이 속도에 넣어 본다.

| | 계산 | 값 |
|---|---|---|
| prefill | 8,909 ÷ 121.36 | **73초** |
| 생성 | 1,876 ÷ 8.98 | **209초** |
| **합계** | | **약 4분 40초** |

**API 는 p50 20.0초다.** → [infrastructure-cost.md](infrastructure-cost.md)

> **폰으로는 14배 느리다. 실사용이 안 된다.**

`[추정]` **E2B 로 바꿔도 약 2분 30초다.** 여전히 못 쓴다.

**다만 이건 폰이다.** 4070 SUPER 는 메모리 대역폭이 한 자릿수 배 이상 높다.

## Hexagon NPU 는 못 썼다

`[실측]`

```
HTP0: Hexagon (0 MiB, 0 MiB free)
ggml-hex: HTP0 failed to open session : error 0x80000406
```

**세션이 안 열린다.** `Hexagon Arch version v73` 이고 빌드는 `v75` 미만이면 `ndev` 를 1로 강제한다.

`[미확보]` **원인을 안 팠다.** NPU 가 되면 숫자가 크게 달라질 수 있다.

## 무엇을 알았나

| | |
|---|---|
| **4B 급이 5GB 안에 들어간다** | Gemma 4 E4B Q4_0 = 4.79 GiB |
| **GPU 가 prefill 에서 1.9배** | 우리 워크로드가 prefill 이 무겁다 |
| **폰으로는 실사용 불가** | 4분 40초 vs API 20초 |

`[실측]` **4070 SUPER 는 세션 1 에서 12GB(11.75 GiB) 확보를 확인했다.** → [gpu-limits.md](gpu-limits.md). **처리량(tok/s) 실측은 아직 없다** — 이 문서의 폰 실측이 방향을 보여줄 뿐이다.

## 관계

- [gpu-limits.md](gpu-limits.md) — 왜 x600 을 못 쟀나
- [../evaluation/model-selection.md](../evaluation/model-selection.md) — 후보 기준
- [infrastructure-cost.md](infrastructure-cost.md) — API 쪽 실측
