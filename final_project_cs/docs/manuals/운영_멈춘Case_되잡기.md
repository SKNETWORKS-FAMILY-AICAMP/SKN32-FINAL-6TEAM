# 운영 절차 — 멈춘 Case 되잡기 (sweeper)

## 무엇을 하는 것인가

접수·분류·실행을 나누면서 **그 사이에 죽으면 Case 가 중간 상태에 남는다.**

```
접수(저장·커밋) ──▶ 분류 ──▶ 201 응답 ──▶ (뒤에서) 에이전트 실행
                 ▲                      ▲
                 │                      │
        여기서 죽으면              여기서 죽으면
        `classifying` 잔류         `routing` 잔류
```

전에는 이 셋이 한 트랜잭션이라 하나가 실패하면 통째로 없던 일이 됐다. 그게 더
나빴다 — LLM 이 느리면 접수까지 막히고, 타임아웃이면 **고객이 보낸 문의가
사라졌다.** 그래서 나눴고, 나눈 대가로 이 절차가 필요해졌다.

sweeper 는 그렇게 남은 Case 를 주기적으로 훑어 **다시 처리한다.**

## 어떻게 돌리나

```bash
python -m scripts.run_sweepers --interval 60
```

| 옵션 | 언제 |
|---|---|
| `--interval 60` | 상주 실행. **이게 기본 운영 방식이다** |
| `--once` | 한 번만. cron 이나 수동 확인용 |
| `--only classifying` / `--only routing` | 한쪽만 |

수치는 `config/guardrails.yaml` 의 `reliability.*` 에 있다. 계약 문서는
`docs/handoff/06_가드레일_수치.md` §4-A.

## 출력을 어떻게 읽나

한 회차마다 JSON 한 줄이 나온다.

```json
{"classifying": {"scanned": 2, "classified": 1, "failed": 1, "conflicted": 0, "errored": 0},
 "routing": {"scanned": 0, "started": 0, "errored": 0}}
```

| 칸 | 뜻 | 봐야 하나 |
|---|---|---|
| `scanned` | 멈춘 것으로 골라낸 수 | 계속 0 이 아니면 왜 자꾸 멈추는지 본다 |
| `classified` | 다시 분류해 성공 | — |
| `failed` | 분류는 실패했지만 **기록은 됐다.** Case 는 `escalated` 로 나아간다 | 급증하면 provider 상태를 본다 |
| `conflicted` | 그 사이 다른 경로가 처리했다. 정상 경합 | — |
| `started` | 실행을 다시 걸어 끝났다 | — |
| ★`errored` | **아무것도 기록하지 못했다.** Case 는 그대로 남아 다음 회차에 또 걸린다 | ★**0 이 아니면 사람이 본다** |

★`failed` 와 `errored` 를 헷갈리지 않는다. 앞은 "실패했지만 처리는 됐다",
뒤는 "아무 일도 못 했다" 이고 **할 일이 다르다.** `errored` 는 로그에
스택까지 남는다(`logger.exception`).

## `errored` 가 나오면 어떻게 알게 되나 (2026-09-07)

JSON 을 사람이 읽어야만 알 수 있던 상태였다. 이제 **밖으로 나간다.**

| 모드 | 신호 |
|---|---|
| `--once` | **exit 1.** cron 이 실패로 보고 메일·알림을 낸다 |
| `--interval` | **stderr** 한 줄. ★**죽지 않는다** |

```
★classifying sweeper: errored=2 · scanned=5 — 아무것도 기록하지 못했다. 다음 회차에 또 걸린다
```

★상주 모드가 첫 실패에 멈추면 **되잡기 자체가 멈춘다.** 멈춘 Case 를 되잡는
장치가 멈추는 것이 더 나쁘므로, 알리고 계속 돈다.

★사유는 **stderr** 로만 간다. stdout 은 JSON 한 줄이라는 계약을 지켜야
파이프로 받아 쓰는 쪽이 안 깨진다.

## 주기 실행에 거는 법 (2026-09-07)

★**이 기계에 있는 스케줄러는 `schtasks` 하나뿐이다**(실측). `docker`·`systemctl`·
`cron`·`crontab` 은 전부 없다 — 위 「환경 기동 절차」가 적어 둔 그대로다.

```powershell
python -m scripts.install_sweeper_task            # 무엇을 걸지 보여만 준다(기본)
python -m scripts.install_sweeper_task --apply    # 실제로 등록 (1분마다)
python -m scripts.install_sweeper_task --status   # 지금 걸려 있나
python -m scripts.install_sweeper_task --remove   # 뗀다
```

### 왜 `--once` 를 반복해서 거는가 (상주 `--interval` 이 아니라)

| 이유 | |
|---|---|
| 죽어도 다음 회차가 돈다 | 상주 루프는 프로세스가 죽으면 그냥 멈춘다 |
| **실패가 밖으로 나간다** | `--once` 는 `errored` 면 exit 1 → 스케줄러가 실패로 기록. 상주 모드에는 볼 exit code 가 없다 |
| 주기가 코드 밖에 있다 | "언제 도는지" 가 스케줄러에 적힌다 |

### 실측 (2026-09-07) — 신호가 끝까지 닿는가

임시 작업으로 등록해 실제로 돌리고 뗐다.

```
스케줄러가 sweeper 를 실행       → 마지막 결과 0
exit 1 을 내는 작업              → 마지막 결과 1     ← 실패로 기록된다
exit 0 을 내는 작업              → 마지막 결과 0
```

즉 `errored` → **exit 1** → **스케줄러 실패 기록** 까지 고리가 이어진다.

★한 번은 이 측정을 잘못 읽을 뻔했다. `schtasks` 는 **CP949** 로 출력하는데
UTF-8 로 읽어 한글 키(`마지막 결과`)를 못 찾고 `None` 이 나왔다. **"못 읽었다" 와
"값이 0 이다" 는 다르다** — 인코딩을 맞춰 다시 쟀다.

### 컨테이너·systemd 배선은 아직 안 한다

없는 것에 대고 설정 파일을 미리 써 두지 않는다. 이 저장소는 Docker·Terraform 에서
이미 그렇게 했다가 "build/run/validate/apply 전부 미검증" 을 문서에 적어야 했다
(`CLAUDE.md` §5). 배포 형태가 정해지고 **실제로 돌려 볼 수 있을 때** 붙인다
(v9 §12·§28, Phase 2).

리눅스로 갈 때의 형태만 적어 둔다 — 검증된 것이 아니다:

```cron
*/1 * * * * cd /path/to/final_project_cs && python -m scripts.run_sweepers --once
```

## 자주 묻는 것

**Q. 정상 처리 중인 Case 를 되잡지 않나?**
임계값이 막는다 — 분류 5분, 실행 10분을 **넘겨야** 후보가 된다. 실행은 원래
수십 초 걸리므로(p50 20~34초) 10분은 넉넉하다. 그래도 겹치면 `expected_version`
낙관적 동시성이 하나만 통과시키고 나머지는 `conflicted` 로 센다.

**Q. 주기를 더 짧게 해도 되나?**
된다. **주기는 안전이 아니라 복구 지연을 정한다.** 안전은 임계값이 정한다.
다만 60초보다 짧게 할 실익이 없다 — 어차피 임계값을 넘어야 잡힌다.

**Q. 여러 개 띄워도 되나?**
동작은 한다(위 낙관적 동시성). 굳이 그럴 이유는 없다.

**Q. DB 부하는?**
부분 인덱스 `cases_stuck_sweep_idx`(마이그레이션 009)를 탄다 — 진행 중인 두
상태만 색인해 아주 작다. 인덱스를 넣기 전에는 테넌트의 Case 를 **매분 전부**
읽었다(EXPLAIN 으로 확인).

## 아직 없는 것

- ~~**스케줄러 배선.**~~ → **2026-09-07 해결(이 기계 한정).**
  `scripts/install_sweeper_task.py` 가 Windows 작업 스케줄러에 건다.
  **컨테이너·systemd 배선은 여전히 없다** — 배포 형태가 정해지면 붙인다(Phase 2)
- ~~**`errored` 알림.** 로그에만 남는다~~ → **2026-09-07 해결.** exit code +
  stderr. 전용 알림 시스템(Slack·PagerDuty 등)에 붙이는 것은 그 경로가 생길 때다
