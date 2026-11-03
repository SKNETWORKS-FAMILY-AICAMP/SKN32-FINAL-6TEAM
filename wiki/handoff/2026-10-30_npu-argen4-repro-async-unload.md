# NPU argen4 재현·비동기 unload A/B 인계 2026-10-30 20:40 KST

- 실제 NPU(cuDLA) 전체 모델 단일 프로세스로 실행했다. 조건은 48토큰 H16 prefill, 16단계 greedy decode, 2회 반복이다. ABA 3개 arm 모두 argen2 full1과 로짓 33/33행, 토큰, prefill hidden이 비트 동일했다.
- 정확도 게이트:
  - A1–A5 통과(FP32 대비 17/17 토큰, prefill RMS 0.0064, FP16 대비 최대 0.078).
  - 원래 Q4 GPU 기준 게이트는 RMS 0.1571 > 0.1로 실패했고, 완화하지 않았다. 이 값은 Q4 자체의 FP32 대비 오차와 같다.
- 시간 측정은 경합 상태에서 이뤄졌다.
  - 다른 소유자의 Hermes llama-server(PID 3364, Qwen3.8-27B)가 GPU를 84–96% 사용했다. GPU 앵커는 pp512 약 161, tg128 약 3.4로 정상치보다 20–27배 낮았다.
  - 측정값은 prefill 2.10–2.57 tok/s, decode 0.066–0.115 tok/s로 대표 속도가 아니다. 비경합 기준은 기존 full1의 prefill 5.38, decode 0.158/0.200 tok/s다.
- decode 단계의 설명되지 않던 시간은 `cudlaModuleUnload`(단계당 73개 모듈)였다. 백그라운드 unload 후보를 실측했다. 결과는 비트 동일했지만 load 시간이 같은 만큼 늘었다(cuDLA 전역 락). 인접 대조 2개를 모두 넘지 못해 기각했다.
- prompt-lookup 추측 디코딩은 이 프롬프트를 오프라인으로 평가한 결과 수락 0/16이어서 기각했다.
- 메모리:
  - 커널 nonpaged pool은 13.4GB로 일정했으므로 NPU 모듈 메모리가 아니다. 무엇이 쓰는지는 밝히지 못했다.
  - 모듈 메모리는 Windows 쪽 32GB의 commit으로 잡힌다. commit 여유는 최저 1.96GB까지 떨어졌다.
- 다른 작업 중단 0건, 설정 변경 0건, 삭제는 자기 resume 체크포인트뿐이다. 순증 디스크는 141MB다.
- 상세: `C:/Users/kcxsz/frog-npu-dev/experiments/npu-full/argen4/REPORT.md`, 프로젝트 인계: `C:/Users/kcxsz/frog-npu-dev/HANDOFF-20261030-npu-argen4.md`.
