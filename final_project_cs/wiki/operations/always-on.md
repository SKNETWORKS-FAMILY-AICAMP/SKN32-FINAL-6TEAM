---
type: runbook
title: 상시 실행 배치
description: 무엇이 늘 돌아야 하고, 죽으면 무엇으로 아는가. 지금은 전부 콘솔 창에 매달려 있다
status: draft
tags: [architecture, governance]
owners: [human:미배정]
domain: neutral
domain_note: 상시 실행 얼개는 도메인 무관이다. 「무엇이 돌아야 하나」 표가 지금 도메인의 작업 이름(감시·안내)을 든다
---

# 상시 실행 배치

**결론부터 — 지금 이 제품의 상시 실행은 전부 개발자 PC 의 콘솔 창에 매달려 있고,
「안 돌고 있었다」를 알아차릴 방법이 없다.** DB 는 셸이 띄운 자식 프로세스라 그 셸이
사라지면 종료 기록도 없이 함께 꺼지고(`[실측]` 13개 인스턴스 중 **정상 종료 기록은
2026-08-13 이후 0건** — [운영_로컬DB_기동과_비정상종료.md](../records/manuals/운영_로컬DB_기동과_비정상종료.md) §2-B),
되잡기 작업·배달 일꾼은 사람이 손으로 띄우는 콘솔이다.

이 문서는 **무엇이 상시로 돌아야 하는가**와 **죽으면 무엇으로 아는가**를 적는다.
옮기는 방법(서비스화 · 서버 이전)은 [move-to-server.md](move-to-server.md)다.

## 상시로 돌아야 하는 것 다섯

| 대상 | 주기 | 왜 상시인가 | 죽으면 무엇으로 아나 | 기록이 남는 곳 |
|---|---|---|---|---|
| **DB** PostgreSQL 16.14 · 5433 | 항상 | 나머지 넷이 전부 이것 위에 선다 | 5433 이 안 열린다 → 점검 `db` | `server_5433.log` (데이터 디렉터리) |
| **되잡기 작업** `scripts.run_sweepers` | **1분마다** 한 회차 | 접수·분류·실행을 나눈 대가. 안 돌면 `classifying`·`routing` 잔류 Case 가 영원히 남고 **일정 안내가 때를 놓친다** | 임계값 넘긴 Case 가 쌓인다 → 점검 `stuck_cases` | `var/ops/logs/sweepers-<날짜>.log` |
| **안내(리마인더)** 되잡기 안에 있다 | 위와 같다 | v11 §6-B ②하루 시작 ③항목 출발. `--only` 없이 돌면 `trip_reminders` 가 함께 돈다 | 나간 안내가 없다 → 점검 `notice` (★아래 한계) | 위와 같다 |
| **바깥함 일꾼** `scripts.run_outbox_worker` | **1분마다** 한 회차 | 통지는 `outbox` 에 **쌓이기만 한다.** 일꾼이 안 돌면 고객에게 아무것도 안 나가는데 **어디에도 오류가 안 뜬다** | `pending` 이 오래 남는다 → 점검 `outbox_pending` | `var/ops/logs/outbox-<날짜>.log` |
| **앱** uvicorn | 항상 | 접점 둘(에이전트 API · **여행계획서 링크**)이 같은 프로세스다. **상태의 정본이 링크**라(v11 §9-C) 앱이 꺼지면 고객이 맞는 것을 볼 데가 없다 | `/health` 가 안 열린다 → 점검 `app` | `var/ops/logs/app-<날짜>.log` |

여기에 하루 한 번짜리가 하나 더 있다 — **일일 피드백 집계**(`scripts.run_daily_feedback`,
가드레일 `feedback_analytics.batch_time_utc: 00:10` = KST 09:10).

★**주기는 안전이 아니라 복구 지연을 정한다.** 안전은 임계값이 정한다 —
`config/guardrails.yaml` 의 `reliability.classification_stuck_after_seconds`(300) ·
`routing_stuck_after_seconds`(600). 임계값을 넘겨야 후보가 되므로 주기를 짧게 해도
정상 처리 중인 Case 를 건드리지 않는다.

## 지금 상태 vs 가야 할 상태

`[실측 2026-09-22 16:19]` 점검 12항목 중 **OK 5 · 경고 1 · 실패 1 · 못확인 5**
(`python -m scripts.ops.healthcheck`).

| | **지금** `[실측]` | **가야 할 상태** |
|---|---|---|
| DB | 셸이 띄운 자식. 부모 사슬이 `bash.exe → cmd.exe → postgres.exe` 였다. 재부팅하면 안 뜬다 | 서비스. 기계가 켜지면 자동, **정상 종료 경로가 있다** |
| 되잡기 작업 | 손으로 띄우는 콘솔. **지금 이 기계에 걸려 있는 것 0개** | 1분마다 창 없이 도는 작업 + 실패가 기록으로 남는다 |
| 바깥함 일꾼 | 동 | 동 |
| 앱 | **에이전트 도구가 띄운 자식**이었다(`python.exe → claude.exe`). 포트 8043 | 늘 떠 있고, 죽으면 다시 뜬다(길 ② 기준) |
| 일일 집계 | 안 걸려 있다 | 하루 한 번 |
| 「안 돌고 있었다」를 아나 | **모른다** | 점검 한 줄로 본다 |
| 로그 | 콘솔 창. 창이 닫히면 사라진다 | `var/ops/` 에 남는다 |

### ★`[실측 2026-09-22 16:22]` 「안 돌고 있었다」의 증거 — 통지 8건이 8시간 묵어 있었다

이 문서를 쓰면서 배달 일꾼을 **한 회차** 돌렸더니 `handled=237` 이 나왔고, 그중
`trip.notice` 가 **8건**이었다(여행 4건 × 하루시작·변경). 그 8건은 **전부
`attempts=1`** 이다 — 즉 **그때까지 한 번도 시도된 적이 없다.** 만들어진 시각은
같은 날 08:24~08:29 이고 나간 시각은 16:22 다. **약 8시간을 바깥함에서 잤다.**

나머지 229건은 시험 잔재(`test.tenant.guard`·`same.topic` 등)라 바깥으로 안 나간다
(디스코드로 가는 것은 `trip.notice` 뿐이다 — `app/infrastructure/notify/discord.py:123`).

★**숫자는 움직인다** — 시나리오 세션이 돌고 있으면 그 세션이 자기 통지를 만들고 스스로
배달한다(같은 시각 `pending` 7건이 30초 만에 사라지는 것을 봤다). 그래서 증거로 쓰는 것은
**`attempts=1` 인 채 8시간 묵은 8건**이지 그때그때의 `pending` 수가 아니다.

★**이 8건은 그동안 어느 화면에도 「밀렸다」고 뜨지 않았다.** 고객 쪽에서 보면
안내가 오지 않은 것이고, 우리 쪽에서 보면 아무 일도 없는 것처럼 보였다.
**이것이 이 문서가 필요한 이유 전부다.**

★`[실측 2026-09-22]` **고친 것이 아니라 찾은 것 하나** — 앱은 **8043** 에서 돌고 있는데
설정 `ACOP_PUBLIC_BASE_URL` 은 **8042** 다. 이 주소가 **고객에게 나가는 여행계획서 링크에
박히는 주소**라, 앱이 살아 있어도 **링크는 죽은 주소를 가리킨다.** 점검의 `app` 줄이 이것을
실패로 잡는다. 고치는 것은 이 작업의 범위 밖이라 **안 고쳤다.**

## 죽었는지 어떻게 보나

```bash
python -m scripts.ops.healthcheck          # 읽기만 한다. 아무것도 띄우지 않는다
python -m scripts.ops.healthcheck --json
python -m scripts.ops.healthcheck --strict # 경고도 실패로 센다(exit 1)
```

판정은 넷이고 **「못확인」이 따로 있다.**

| 판정 | 뜻 |
|---|---|
| `OK` | 확인했고 정상이다 |
| `경고` | 확인했고 수상하다 — 사람이 본다 |
| `실패` | 확인했고 고장이다 — **exit 1** |
| ★`못확인` | **확인 자체를 못 했다.** 정상이라는 뜻이 아니다 |

### 점검이 **못 하는 것** (먼저 적는다)

- **알림을 고객이 읽었는지** — 디스코드·텔레그램·메일 어느 것도 읽음을 안 준다(v11 §6-A).
  잴 수 있는 것은 계획서 링크 열람이고 그건 DoD-25 가 본다.
- ★**통지가 언제 배달됐는지** — `outbox` 에 **배달 시각 칸이 없다**(`available_at` 은
  「보낼 수 있게 된 시각」이다). 점검은 그 근사치만 보여 주고 근사치라고 적는다.
- **일일 피드백 배치가 실제로 결과를 남겼는지** — heartbeat 는 보지만
  `feedback_analytics_reports` 에 어제 행이 있는지는 **아직 안 센다.**
- **DB 가 언제 죽었는지** — 서비스가 아니면 종료 기록이 안 남는다. 지금 안 떠 있다는 것만 안다.
- **바깥 소스(기상·교통·관광)가 지금 답하는지** — 부르면 한도를 쓴다. 감시 한 회차의
  `fatal` 수로 간접으로만 본다.
- **다른 기계에서 도는 것** — 이 점검은 이 기계와 설정된 DB 만 본다.

### 두 가지를 함께 본다 — 「돌았나」와 「됐나」

| 보는 것 | 답하는 질문 | 한계 |
|---|---|---|
| heartbeat (`var/ops/heartbeat/<작업>.json`) | **돌았나.** 마지막 회차 시각과 exit code | `scripts.ops.tick` 으로 돈 것만 남는다. 손으로 돌린 것은 안 남는다 |
| DB 의 결과 (`stuck_cases` · `outbox_pending`) | **됐나.** 걸어 뒀어도 매번 실패하면 여기가 쌓인다 | 되잡을 것이 없으면 아무 흔적도 안 남는다 |

★`sweeper_흔적`(마지막으로 Case 를 건드린 때)은 **실행 여부의 증거가 아니다.**
할 일이 없으면 아무것도 안 남는다 — 「오래됐다」가 「안 돌았다」를 뜻하지 않는다.

## 로그는 어디로 가나

```
var/ops/heartbeat/<작업>.json      마지막 회차 — 시각 · exit code · stdout/stderr 꼬리
var/ops/logs/<작업>-<날짜>.log      회차마다 한 줄(+stderr 줄)
<데이터디렉터리>/server_5433.log    DB. ★로그 파일이 둘이다 — 조사할 땐 `server.log` 도 함께 본다
```

`var/` 는 `.gitignore` 에 있다 — 운영 기록이지 소스가 아니다.

★**콘솔에 찍고 창을 닫으면 끝나는 지금 방식이 「안 돌고 있었다」를 못 알아챈 이유다.**
그래서 스케줄러가 원래 스크립트를 직접 부르지 않고 `scripts.ops.tick` 을 거친다 —
성공이든 실패든 **파일에 먼저 남기고** 자식의 exit code 를 그대로 돌려준다.

## 이 저장소의 운영 도구

| 명령 | 하는 일 |
|---|---|
| `python -m scripts.ops.install_services` | 무엇을 걸지 **보여만 준다**(기본). `--apply` 를 줘야 실제로 건다 |
| `python -m scripts.ops.install_services --status` | 지금 걸려 있나 |
| `python -m scripts.ops.install_services --remove --only <작업>` | 뗀다 |
| `python -m scripts.ops.tick <작업> --show` | 스케줄러가 부를 명령을 보여만 준다 |
| `python -m scripts.ops.tick <작업>` | 한 회차 돌리고 기록을 남긴다 |
| `python -m scripts.ops.healthcheck` | 위 점검 |

상시 실행 목록의 정본은 **`scripts/ops/jobs.py` 한 곳**이다 — 등록·실행·점검이 같은 표를 읽는다.

★**등록은 이 기계에 남는 설정이다.** 2026-09-14 에 묻지 않고 등록한 작업이 5분마다
검은 창을 띄워 일주일 뒤 지워야 했다([운영_멈춘Case_되잡기.md](../records/manuals/운영_멈춘Case_되잡기.md)
§「작업 스케줄러에 거는 방식 — 폐기됨」). 그래서 지금 도구는 **기본이 미리보기**이고,
창을 안 띄우며(`pythonw` + `CREATE_NO_WINDOW`), 떼는 법을 먼저 찍는다.

## 관계

- [move-to-server.md](move-to-server.md) — 두 가지 길(이 PC 서비스화 · 서버 이전)과 되돌리는 법
- [local-setup.md](local-setup.md) — 기동 명령·환경 값의 정본
- [troubleshooting.md](troubleshooting.md) — 막히면
- [../records/manuals/운영_로컬DB_기동과_비정상종료.md](../records/manuals/운영_로컬DB_기동과_비정상종료.md) — DB 가 왜 꺼졌나(조사)
- [../records/manuals/운영_멈춘Case_되잡기.md](../records/manuals/운영_멈춘Case_되잡기.md) — 되잡기 출력 읽는 법
