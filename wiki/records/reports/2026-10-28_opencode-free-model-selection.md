# OpenCode 무료 모델 선정·설정 검증 (2026-10-28)

범위: 비민감 경량 작업용 OpenCode CLI 기본 모델. 대상 설정은 `C:\Users\kcxsz\.config\opencode\opencode.jsonc` 하나(백업 `opencode.jsonc.bak-20261028`). Hermes 프로필 설정·다른 프로필은 건드리지 않음. 과금 0(`opencode stats` Total Cost $0.00).

## 결론

- **기본 모델 유지: `opencode/deepseek-v4.1-flash-free`, 추론 단계 `max`로 올림.**
- 근거가 가장 강한 무료 모델이다. 같은 OpenCode 하네스 기준 독립 리더보드(aicodingdaily, 10-27 갱신)에서 무료 제공 모델 중 최고 점수다. 다만 점수 측정에 쓴 것은 `Deepseek-V4.1-Flash-1017`로, 무료판(카탈로그 출시일 2026-09-10)과 판이 같은지는 확인하지 못했다 → **불확실**.
- 개인정보 조건도 가장 낫다. Zen 문서 기준 제공사가 데이터를 보관하지 않고(zero-retention) 학습에도 쓰지 않는다. MiMo·Big Pickle·Flint·Nemotron 계열은 수집 데이터를 모델 개선에 쓸 수 있거나 기록된다.

## 비교 (CLI 1.19.4, `opencode models --verbose` + 공식 Zen 문서 + 실측)

| 모델 | 실측 가용 (10-28) | 독립 코딩 점수 (aicodingdaily, OpenCode, /70) | 개인정보 (Zen 문서) |
|---|---|---|---|
| deepseek-v4.1-flash-free | 됨 (27s) | 60.97 (Max) / 55.21 (High), 1017판 | 보관 안 함, 학습 안 함 |
| mimo-v2.6-flash-free | 됨 | 53.29 (High) | 개선에 사용 가능 |
| glm-5.3-flash-free | 됨 | 47.51 (Max) | 보관 안 함 |
| beam-free | 됨 | 42.36 (Max) | 30일 보관, 학습 안 함 |
| nemotron-3.5-super-vl-free | 됨 | 38.61 (High) | NVIDIA 체험판, 기록됨 |
| flint-40b-free | 됨 | 측정값 없음 (제조사 자체 발표만 있고 활성 파라미터 2.5B) | 30일 보관, 개선에 사용 |
| big-pickle | 됨 | 측정값 없음 (비공개 모델) | 개선에 사용 가능 |
| nemotron-3.5-lightning-free | 됨 | 측정값 없음 | NVIDIA 체험판 |
| nemotron-3-ultra-free | **안 됨**: `Model is unavailable` | AA Terminal-Bench 4.0 1% | NVIDIA 체험판 |

참고: Artificial Analysis의 Terminal-Bench 4.0 점수는 DeepSeek V4.1 Flash 27%, GLM-5.3-Flash 33%다. 이 지표에서는 GLM이 앞서지만, 종합 코딩 리더보드에서는 DeepSeek가 크게 앞선다. 무료 모델은 모두 「한시적」이라 언제든 바뀔 수 있다.

## 설정 변경

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "opencode/deepseek-v4.1-flash-free",
  "small_model": "opencode/deepseek-v4.1-flash-free",
  "shell": "cmd.exe",
  "agent": {
    "build": { "model": "opencode/deepseek-v4.1-flash-free", "variant": "max" },
    "plan":  { "model": "opencode/deepseek-v4.1-flash-free", "variant": "max" }
  }
}
```

- `small_model`: 이 값이 없으면 제목 생성 에이전트가 유료 `opencode/gpt-5.4-nano`를 불렀다. 계정 잔액이 없어 `Insufficient account funds`로 실패했고, 과금은 없었다. 유료 경로로 요청이 나가지 않도록 무료 모델로 고정했다.
- `shell`: OpenCode가 Hermes 패키지 안의 bash.exe(WindowsApps 경로)를 실행하지 못하고 `EPERM: uv_spawn`으로 실패했다. 그래서 셸 도구가 전혀 동작하지 않았다. `cmd.exe`로 바꿔 해결했다. 전체 경로(`C:\\Windows\\...`)를 쓰면 설정 파싱 오류가 났고, `C:/Windows/...`를 쓰면 인자가 잘못 전달됐다.

## 검증 (모델 지정 없이 실행)

- 작업: `add.py`와 3개 단위시험 작성 후 셸로 실행. 출력 `> build · deepseek-v4.1-flash-free`, `Ran 3 tests ... OK`. 별도로 `python -m unittest`를 돌려 재확인했다.
- `opencode export`로 세션을 확인했다: `modelID: deepseek-v4.1-flash-free`, `variant: max`, 제목 에이전트도 무료 모델을 사용했다.
- 앞선 비교 작업(slugify 구현과 시험)은 deepseek max/high, mimo high가 모두 정답을 냈고, 독립 검증도 통과했다. 이 과제만으로는 세 모델의 차이가 드러나지 않았다.
- 시험 파일은 Hermes 프로필 scratch(`cache/scratch/octest`)에만 만들었다. 프로젝트 원본은 건드리지 않았다.

## 남은 위험

- 무료 풀은 공용이라 사용량이 몰리면 429가 날 수 있다. 무료 목록이 바뀔 때마다 다시 확인해야 한다.
- `max`는 High보다 느릴 수 있다. 리더보드 평균은 7:09, High는 3:13이었다. 경량 작업에서 속도가 문제가 되면 `--variant high`를 쓴다.
- `C:/_proj/final_workspace`에서 `opencode models`를 실행하면 `EPERM uv_spawn 'git'`이 났다. 같은 실행 파일 문제로 보이며, 이번에는 고치지 않았다.
