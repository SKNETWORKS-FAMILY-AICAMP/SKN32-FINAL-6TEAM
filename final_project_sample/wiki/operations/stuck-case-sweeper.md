---
type: guide
title: 멈춘 Case 되잡기 (sweeper)
description: 접수·분류·실행을 나눈 대가로 생긴 잔류 Case를 주기적으로 다시 처리한다
status: draft
tags: [release]
domain: neutral
---

# 멈춘 Case 되잡기 (sweeper)

## 왜 필요한가

접수·분류·실행을 한 트랜잭션에서 나누면 **그 사이에 죽은 Case 가 중간 상태에 남는다.**

```
접수(저장·커밋) ──▶ 분류 ──▶ 응답 ──▶ (뒤에서) 에이전트 실행
                 ▲                    ▲
        여기서 죽으면            여기서 죽으면
        `classifying` 잔류       `routing` 잔류
```

전에는 셋이 한 트랜잭션이라 하나가 실패하면 통째로 없던 일이 됐다. 그게 더 나빴다 —
LLM 이 느리면 접수까지 막히고, 타임아웃이면 **고객이 보낸 문의가 사라졌다.**
그래서 나눴고, 나눈 대가로 이 절차가 생겼다.

## 돌리는 법

```powershell
python -m scripts.run_sweepers --once            # 한 번 (cron·스케줄러용, 기본)
python -m scripts.run_sweepers --interval 60     # 상주
python -m scripts.run_sweepers --only routing    # 한쪽만
```

임계값은 `config/guardrails.yaml` 의 `reliability.*_stuck_after_seconds` 다.
**주기는 안전이 아니라 복구 지연을 정한다** — 안전은 임계값이 정한다. 임계값을
넘겨야 후보가 되므로 주기를 짧게 해도 정상 처리 중인 Case 를 안 건드린다.

## 출력을 어떻게 읽나

한 회차마다 JSON 한 줄.

| 칸 | 뜻 | 봐야 하나 |
|---|---|---|
| `scanned` | 멈춘 것으로 골라낸 수 | 계속 0 이 아니면 왜 자꾸 멈추는지 본다 |
| `classified` · `started` | 다시 처리해 성공 | — |
| `failed` | 분류는 실패했지만 **기록은 됐다.** Case 는 `escalated` 로 나아간다 | 급증하면 provider 를 본다 |
| `conflicted` | 그 사이 다른 경로가 처리했다. 정상 경합 | — |
| ★`errored` | **아무것도 기록하지 못했다.** Case 는 그대로 남아 다음 회차에 또 걸린다 | ★**0 이 아니면 사람이 본다** |

★`failed` 와 `errored` 를 헷갈리지 않는다. 앞은 "실패했지만 처리는 됐다", 뒤는
"아무 일도 못 했다" 이고 **할 일이 다르다.**

## `errored` 가 나오면 어떻게 알게 되나

세는 것과 알리는 것은 다르다. 2026-09-07 이전에는 세어서 찍기만 하고 **exit 0**
이었다 — cron 에 걸어 두면 실패가 로그 속에만 남아 아무도 안 봤다.

| 모드 | 신호 |
|---|---|
| `--once` | **exit 1.** 스케줄러가 실패로 기록한다 |
| `--interval` | **stderr** 한 줄. ★**죽지 않는다** |

★상주 모드가 첫 실패에 멈추면 **되잡기 자체가 멈춘다.** 멈춘 Case 를 되잡는
장치가 멈추는 것이 더 나쁘므로, 알리고 계속 돈다.

★사유는 stderr 로만 간다. stdout 이 JSON 한 줄이라는 계약을 지켜야 파이프로
받아 쓰는 쪽이 안 깨진다.

## 주기 실행에 거는 법

★**이 기계에 있는 스케줄러는 `schtasks` 하나뿐이다**(2026-09-07 실측).
`docker`·`systemctl`·`cron`·`crontab` 은 전부 없다.

```powershell
python -m scripts.install_sweeper_task            # 무엇을 걸지 보여만 준다(기본)
python -m scripts.install_sweeper_task --apply    # 실제로 등록
python -m scripts.install_sweeper_task --status / --remove
```

작업 이름은 `A-COP sample sweeper` 다 — ★cs 와 **다르게** 둔다. 한 기계에 두
대상이 걸릴 수 있고, 이름이 겹치면 한쪽이 다른 쪽을 덮어쓴다.

### 왜 `--once` 를 반복해서 거는가 (상주가 아니라)

1. 프로세스가 죽어도 다음 회차가 돈다 — 상주 루프는 그냥 멈춘다
2. **실패가 밖으로 나간다** — `errored` 면 exit 1, 스케줄러가 실패로 기록. 상주
   모드에는 볼 exit code 가 없다
3. "언제 도는지" 가 코드가 아니라 스케줄러에 적힌다

### 실측 (cs 에서, 2026-09-07)

```
스케줄러가 sweeper 를 실행   → 마지막 결과 0
exit 1 을 내는 작업          → 마지막 결과 1     ← 실패로 기록된다
exit 0 을 내는 작업          → 마지막 결과 0
```

`errored` → exit 1 → 스케줄러 실패 기록까지 고리가 이어진다.

## 아직 없는 것

- **컨테이너·systemd 배선.** 없는 것에 대고 설정 파일을 미리 쓰지 않는다 — 이
  저장소는 Docker·Terraform 에서 이미 그렇게 했다가 "전부 미검증" 을 적어야 했다.
  배포 형태가 정해지고 실제로 돌려 볼 수 있을 때 붙인다(v9 §12·§28, Phase 2 — [2026-09-10] v9 는 쇼핑몰 판 계획서다. 현재 기준선 v11 은 이 배선을 따로 정하지 않는다)
- **전용 알림 경로**(Slack·PagerDuty 등). 지금은 스케줄러의 실패 기록까지다
