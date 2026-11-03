---
type: report
title: 라우팅 감사 P1 — 감시·배달·되잡기 기동, 남은 Case·알림, 905 승인 자료(읽기 전용)
status: verified
domain: travel
---

# 라우팅 감사 P1 승인 자료 (2026-10-26 01:17~01:40 KST, 읽기 전용)

범위: 코드 수정 0 · 실행(기동) 0 · DB 쓰기 0(모든 조회 `SET TRANSACTION READ ONLY` + rollback, `guguroute_app` 비superuser) · 알림 0 · push 0 · 고객 원문/비밀 출력 0.
대상 DB: `127.0.0.1:5433/acop_cs`, system_identifier `7700321712607772424`. live API 8042 = PID 10756(v7a), ops 앱 8070 = PID 6896(별도 기동 중). **바깥함 일꾼·sweeper 프로세스는 없음**(Win32_Process 전수 확인).

## 결론 (승인 요청용)

1. **905는 이미 적용돼 있습니다.** 2026-10-25 11:59:49에 `schema-readiness-20261025`가 백업 후 정식 SQL 5개(062·232·905_claims·905_social·907)를 한 트랜잭션으로 적용했고, 지금 제약은 `llm_agent` 포함·validated=true, `llm_agent` claim 831행이 저장돼 있습니다. 감사의 「905 미적용 2건」은 **적용 전 실사용 접수 1건(11:57:00)** + **그 작업이 만든 합성 fixture 1건(12:03:37, `2cc73fbb…`)** 입니다. **적용할 것이 없습니다.** 추가 승인이 필요 없습니다.
2. **바깥함 일꾼을 띄워도 고객에게 나가는 알림은 0건입니다.** 대기 알림 6건은 모두 `demo` 테넌트 `trip.notice`인데, 고객별 외부 발송 스위치가 꺼져 있고(DB override 없음, guardrail `false`) 연결된 고객 채널도 0건입니다. 띄우면 6건이 `pending → skipped`(사유 「고객 외부 알림이 꺼져 있다」)로 바뀌고 끝납니다. 운영자 디스코드 웹훅은 설정돼 있지만 이 일꾼 경로에서는 호출되지 않습니다(아래 근거).
3. **routing 9건·running 7건은 sweeper를 띄워도 바뀌지 않습니다.** routing 9건은 모두 시험 테넌트(`test_api_*`·`eval_*`·`trip_api_*` 등)이고 sweeper는 `ACOP_TENANT_ID=demo`만 봅니다. running을 되잡는 sweeper는 없습니다. running 7건 중 4건은 `demo`의 옛 커머스(shipping, 09-07) Case입니다.
4. **전체 sweeper(`--only` 없음)는 이번 승인 범위에서 빼기를 권합니다.** 감시·재난 점검·새벽 식당(구글 장소, 유료)·관광공사 읽기·게스트 데이터 삭제(`web_guard`)·종료 여행 값 비우기·알림 예약이 함께 돕니다. 외부 호출, DB 삭제, E4B 호출이 섞입니다.

권장 승인안: **(A) 일꾼 1회 실행(`--tenant demo`) + routing/classifying sweeper 1회 실행.** 효과는 6행 skipped 하나뿐입니다. 상시 반복과 전체 감시 루프는 따로 결정합니다.

## ① 로컬 기동 방식

### 정본 실행 방식 (코드 확인)

| 정본 | 내용 | 로컬 적용 판단 |
|---|---|---|
| `deploy/worker.sh` (Docker `tripilot-worker`) | 60초 회차: `replay_operations_diagnostics --prune` → `run_sweepers --once` → 09:10 이후 `run_daily_feedback`. 배달은 별도 반복: `run_outbox_worker --once --drain` 후 `WORKER_DELIVERY_SLEEP`(10)초 대기. **일꾼은 하나만**(둘이면 이중 발송) | Linux/Docker용입니다. Windows git-bash에서는 `python`을 직접 불러 v7a 정책 가드를 우회하므로 쓰지 않습니다 |
| `scripts/ops/jobs.py` + `tick.py` + `install_services.py` | 로컬 Windows 정본: schtasks에 1분 tick(`sweepers`, `outbox`, `daily_feedback`)을 등록합니다. heartbeat는 `var/ops`에 남기고, 연속 실패하면 운영자 웹훅(`ops_alert_webhook_url` 또는 `discord_webhook_url`)으로 알립니다 | tick은 자식 프로세스를 따로 띄워 정책 가드를 우회하고, source 폴더에 씁니다. 이번에는 쓰지 않습니다 |
| `app/ops_entrypoint.py` | 운영 콘솔(루프백 전용, 기본 8070)입니다. **감시·배달 루프가 아닙니다** | 이미 PID 6896으로 떠 있습니다(admin-testmode). 이번 대상이 아닙니다 |
| wiki `operations/always-on.md`·`run.md` | always-on은 worker.sh와 공개 배포 점검을 설명합니다. run.md에는 일꾼 명령이 없습니다(SQL·지속 실행은 always-on으로 넘깁니다) | — |

### 준비한 실행기 (미실행)

`ops/launch-ops-jobs.py` (sha256 `e0506e46fbaa839a35410ba88ca761f5677e4d8881a0086d12fc7b66fc2e2890`, 구문 검사만 통과)

- v7a 실행기 `runtime-v7a-serving/launch-serving.py`와 같은 조건으로 실행합니다.
  - source: `source-v7a/final_project_cs`
  - SERVING_FREEZE·runtime-inputs 해시 검사
  - 비밀 설정: `.env`·`.env.apikeys`는 Settings env_file로 읽고, DB URL은 `C:/_proj/postgresql/run/private/app.env`에서 읽습니다
  - guardrails: `local-guardrails.yaml`
  - 모델: Ollama E4B, `num_ctx` 8192, failover off
- **정책 가드(policy.py)를 복사본으로 설치합니다.** 허용하는 외부 통신은 DB 5433과 모델 11434뿐입니다. 디스코드·텔레그램·공공 API는 막힙니다. counters는 live API와 따로 셉니다.
- 그 밖의 가드:
  - DB는 정확한 대상만 허용합니다
  - subprocess와 source/dataset 쓰기를 막습니다
  - phrasebook은 자기 폴더에 씁니다(`ACOP_NOTICE_PHRASEBOOK_PATH`)
  - 시작할 때 `tenant_id=='demo'`이고 `notice_per_customer_enabled is False`인지 확인합니다
- 모드는 `outbox`·`routing`·`classifying` 셋만 둡니다. 전체 sweeper 모드는 일부러 넣지 않았습니다.

### 정확한 명령 (부모, 승인 후)

```
PY=C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/api-runtime-20261025-014236/venv/Scripts/python.exe
L=C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/p1-approval-prep-20261026-011729-25130/ops/launch-ops-jobs.py
# 0) 사전: probe_main.py 재실행(읽기 전용)으로 pending 6 message_id·상태를 evidence에 보존
# 1) 1회 실행 (전경, 각 수십 초)
$PY -B $L outbox        # 기대 stdout {"handled": 6, ...}, exit 0
$PY -B $L routing       # 기대 {"routing":{"scanned":0,"started":0,"errored":0}}  (조립 실패 시 composition fatal 1, Case 변화 없음)
$PY -B $L classifying   # 기대 {"classifying":{"scanned":0,...}}
# 2) (선택, 별도 승인) 상시: terminal(background=True) 로 `$PY -B $L outbox --loop 10`, `$PY -B $L routing --loop 60`
```

- 포트: 새로 여는 포트는 없습니다(일꾼과 sweeper는 리스너가 없습니다). 기존 8042·8070·3100은 건드리지 않습니다.
- **종료:** 1회 모드는 저절로 끝납니다. 반복 모드는 `ops/ops-identity.json`의 PID를 확인한 뒤 그 PID 하나만 `process_manage kill`(필요하면 `taskkill /PID <pid> /F`, `/T` 없이)로 종료합니다. 배달 중에 죽이면 그 행이 `processing`으로 남고, `outbox_stale_processing_seconds`가 지나면 다음 실행 때 `unknown`으로 바뀝니다. 그러니 배달이 끝난 직후 sleep 중에 종료합니다.
- **되돌리기:** 프로세스 쪽은 종료만 하면 됩니다(설치·서비스 등록이 없습니다). DB 쪽은 6행이 skipped가 됩니다. 되돌리려면 사전에 보존한 message_id 6개를 `UPDATE outbox SET status='pending', last_error=NULL WHERE message_id = ANY(...) AND status='skipped'`로 바꿉니다. 이것도 DB 쓰기라 별도 승인이 필요합니다.

### 알림 채널 존재 여부 (값 비출력)

| 설정 | 위치 | 상태 |
|---|---|---|
| `ACOP_DISCORD_WEBHOOK_URL`(운영자 채널) | 원본 `.env.apikeys` | 설정됨 |
| `ACOP_OPS_ALERT_WEBHOOK_URL` | — | 없음(비면 운영자 디스코드를 씁니다. tick의 연속 실패 알림만 사용) |
| 텔레그램 봇 토큰 | `.env`·`.env.apikeys`·private | 없음 |
| `ACOP_TENANT_ID` | `.env` | `demo` |
| 고객 외부 발송 스위치 `travel.notice_per_customer_enabled` | runtime_limits override | **없음** → guardrail `false`(원본·local 동일) |
| 고객 연결 채널(`customer_profiles.notice_channel`) | DB | **0명** |

**판정: 고객에게 나가는 것은 0건입니다.** 근거는 다음과 같습니다.

- `CustomerNoticeRouter.__call__`(notice_routing.py:79~90)는 `trip.notice`·`customer.notice` 주제를 받으면, 스위치가 꺼져 있을 때 렌더링 전에 `NoticeSuppressed`를 냅니다. 이 행은 `skipped`가 되고 다시 집지 않으며, 모델 번역도 하지 않습니다.
- 다른 주제는 운영자 `DiscordWebhook`으로 가지만 `DiscordWebhook.TOPICS={"trip.notice"}`라서 fallback `publish`(no-op)로 끝나고 `delivered`가 됩니다. 운영자 웹훅으로 POST하지 않습니다. 현재 그런 행은 0건입니다.
- 이중 차단: 스위치가 켜지더라도 정책 가드가 외부 통신을 막습니다. 그때는 ConnectionError → `unknown`이 되므로, 실제로 발송하려면 정책을 바꾸는 별도 승인이 필요합니다.
- dry-run 옵션: 일꾼에는 dry-run 플래그가 없습니다. 대신 위 판정을 같은 조건의 읽기 전용 질의(`probe_main.py`)로 미리 재현했습니다.

## ② 남은 Case·알림 집계와 띄웠을 때의 결과

### routing 9건 (전부 agent_runs 0, 이벤트 `created > classified`에서 멈춤)

| 생성(KST) | 테넌트 | intent / issue_code | 생성 주체 | 시험/실고객 근거 |
|---|---|---|---|---|
| 09-14 12:54 | test_api_* | billing / payment_failed | key | 시험 테넌트 이름, 옛 커머스 어휘 |
| 09-28 11:16 | eval_* | incident_report / mobility_missed_or_disrupted | trip_watch | eval 테넌트·고객 |
| 09-28 16:28 | test_api_* | other / other | mcp | 시험 테넌트 |
| 09-30 18:04 | question_* | confirm_request / activity_other | case_engine | 시험 테넌트(case version day) |
| 09-30 18:04 | casever_* | incident_report / activity_weather_risk | trip_watch | 시험 테넌트 |
| 10-03 04:24 ×3 | trip_api_* | incident_report / activity_other | trip_watch | 시험 테넌트(같은 초에 3건) |
| 10-11 03:47 | resume_travel_* | incident_report / dining_delay | (빈 actor) | 「여행 재개 시험」 테넌트 |

→ **실고객 0/9 = 0%(테넌트 이름 기준 추정)**. sweeper(`tenant=demo`)가 집는 수는 0/9입니다. 띄워도 바뀌지 않습니다.

### running 7건

| 생성 | 테넌트 | intent / owner | run | 근거 |
|---|---|---|---|---|
| 09-07 01:19~01:38 ×4 | **demo** | shipping / fulfillment_logistics | failed(09-07 01:56) | 옛 커머스 Case, 고객 eval_*, routed by `probe` |
| 10-05 00:45 | trip_api_* | incident_report / activity | 0 | 시험(routed by `test`) |
| 10-11 03:36 | apprprop_* | incident_report / booking_handoff | active(미종료) | 시험 테넌트 |
| 10-11 03:37 | trip_api_* | adjust_reject / dining | active(미종료) | 시험 테넌트 |

→ 실고객 0/7(추정). running을 되잡는 sweeper는 없습니다. routing sweeper는 `status='routing' AND agent_runs 없음`만 봅니다. **띄워도 바뀌지 않습니다.**

### 대기 알림 6건 (`outbox` pending 6 · processing/unknown 0 · 전체 delivered 462 · skipped 75)

| available(KST) | 테넌트/주제 | 키 모양 | 여행 | 고객 | 채널 |
|---|---|---|---|---|---|
| 10-25 12:22 | demo / trip.notice | `<trip>:v1` | A, active, 11-01~11-02 | web 계정 | 없음 |
| 10-25 13:21 | 〃 | `<trip>:v1` | B, 〃 | web | 없음 |
| 10-25 13:46 | 〃 | `<trip>:v1` | C, 〃 | web | 없음 |
| 10-25 16:07 | 〃 | `<trip>:v2` | C | web | 없음 |
| 10-26 00:48 | 〃 | `<trip>:v3` | C | web | 없음 |
| 10-26 00:49 | 〃 | `<trip>:v4` | C | web | 없음 |

- 모두 attempts 0, simulation 없음, replay=false, locale ko입니다. v1은 「생성 포함」 변경 알림입니다(여행 3개 생성 시각과 같은 초).
- 실고객 여부는 **미확정**입니다. `demo` 운영 테넌트의 web 계정이며, 10-25 로컬 LAN 서비스 QA 시간대(12:22~16:07, v7a 교체 뒤 00:48~00:49)에 생성됐습니다. 원문을 보지 않았으므로 단정하지 않습니다.
- 일꾼을 띄우면 6/6 = 100%가 `skipped`가 됩니다. 외부 발송 0, 모델 호출 0이고, 앱 안 알림과 여행계획서 링크는 그대로입니다.

### 처리 선택지

| 대상 | 선택지 | 결과·위험 | 권장 |
|---|---|---|---|
| 알림 6 | (a) 일꾼 1회 → skipped | DB 6행 변경. 이후 스위치를 켜도 이 6건은 다시 나가지 않습니다(x600 기존 skipped 75건과 같은 처리) | **권장**(현행 정책과 같음) |
| | (b) 그대로 둠 | pending 적체 지표만 남습니다 | 스위치를 켤 계획이 있으면 이쪽 |
| | (c) 스위치 ON 후 일꾼 | 연결 채널이 0명이라 결국 skipped입니다. 정책 가드가 있으면 발송 시도도 막힙니다 | 비권장(효과 없음) |
| routing 9 · running 7 | (a) 그대로 둠 | 고객 영향 없음, 집계만 흐려집니다 | **권장(당장)** |
| | (b) `python -m scripts.cleanup_test_residue`(기본 dry-run 세기만) → `--apply`(백업 후 삭제, `--restore` 있음) | 시험 테넌트 잔재를 정리합니다. DB 삭제라 별도 승인이 필요합니다 | 발표 뒤 |
| | (c) 테넌트별 sweeper 강제 | 시험 fixture에 Controller와 E4B를 돌립니다 | 비권장 |
| demo 옛 커머스 running 4 | D-023 범위 정리(백업 후 닫기/삭제) | DB 쓰기, 별도 승인 | 결정 필요 |

### 전체 sweeper(`--only` 없음)를 띄우면 (참고, 권장 안 함)

- demo 활성 여행은 56건이고, 7일 안에 항목이 있는 여행은 8건입니다.
- `trip_cases`(3분 문, job_gates 마지막 10-15 11:52)와 재난 점검: 외부 기상·재난 API를 부릅니다. 정책 가드 아래에서는 막혀 D-018 fatal로 끝나고, 가드가 없으면 실호출 → Case 생성 → E4B → 일정 변경과 알림(skipped)까지 갑니다.
- `trip_dawn`·`catalog_hours`(03:00~08:00 창): 구글 장소(유료)와 관광공사(최대 600곳/밤)를 부릅니다.
- `web_guard`: 마지막 사용 168시간이 지난 **게스트의 여행·세션·키·사용자를 삭제**하고, 동의 기록 만료분도 삭제합니다. 회원 정리는 dry_run입니다. 삭제 건수는 산정하지 않았습니다.
- `trip_places`: 끝난 여행의 외부 값을 비웁니다. `trip_reminders`는 11-01부터 하루 시작·출발 안내를 outbox에 넣습니다.

## ③ 계획서 접수 fatal 7일 5/20 분리

| 접수(KST) | fatal_code | 원인 | 시험/실사용 | 지금도 재발하나 |
|---|---|---|---|---|
| 10-25 11:57:00 | reading_schema_not_ready | 905 적용 전(적용 11:59:49, 2분 49초 전) | web 계정 실사용(사용자 지적 `7a7a0e55`) | 아니요 — 제약이 지금 정상입니다. 기록은 fatal로 남고 재업로드가 필요합니다 |
| 10-25 12:03:37 | reading_schema_not_ready | **schema-readiness의 합성 fixture**(`2cc73fbb`, HANDOFF `synthetic_fatal_fixture_write:true`) | 시험 | 해당 없음 |
| 10-25 12:15:48 | reading_failed | `PermissionError: unapproved_egress` — 당시 V10 serving 정책 가드가 읽기 중 외부 조회를 막았습니다 | web | 정책 가드가 있는 한 같은 외부 조회 경로에서 재발할 수 있습니다 |
| 10-25 19:23:57 | reading_model_failed | v7 서빙 중 모델 측 실패(로컬과 유료 모두 답 없음 → `IntakeRejected`) | web | 미확정 |
| 10-25 23:25:21 | reading_model_failed | 위와 같습니다. v7 `policy-counters.json` 갱신 시각 23:25가 일치하고, `model-terminal.jsonl` 마지막 완료가 22:06이라 **완료 전에 거절·실패**한 것으로 보입니다. 정확한 거절 사유는 기록되지 않았습니다 | web | 미확정 |

- 합성 fixture를 빼면 실사용 fatal은 **4/19 = 21.1%** 입니다(schema 1 · egress 1 · model 2). 「905 미적용」으로 볼 것은 0건입니다.

### 905가 무엇인가

- 같은 번호의 정식 파일이 두 개 있습니다(`app/infrastructure/db/migrations/`).
  - `905_intake_claims_llm_agent.sql`(sha256 `10adc5a8…`): `intake_claims_method_check`를 DROP/ADD합니다. 허용값은 `rule, llm_span, lookup, customer, trip, llm_agent`입니다(D-025 이해 에이전트 저장). 코드 관문 `_require_reader_schema`(pipeline.py:199)가 이 정확한 정의와 `convalidated=true`를 확인합니다.
  - `905_intake_social_links.sql`(sha256 `9594c1fa…`): `intake_dining_links` 표와 `intake_dining_links_tenant_idx`를 만듭니다.
- 「905claims/905social」은 이 두 파일을 말합니다. 10-24 보고서들의 `pending/905_…`은 그 전 단계의 초안입니다(그때는 DB에 적용하지 않음).
- **현재 DB 상태(읽기 전용 확인):**
  - 제약 정의가 위 6개 값과 정확히 같고 validated=true입니다.
  - `intake_dining_links`와 그 인덱스가 있습니다.
  - 062 `trip_archives`·`trip_archive_marks`, 232 `reopen_trip_id`, 907 `screened`·`survey_plan`이 모두 있고, 906 `intake_backups`도 있습니다.
  - app role의 SELECT와 INSERT 권한이 모두 true입니다.
  - claim 분포: llm_agent 831 · rule 570 · lookup 319 · trip 212 · customer 75 · llm_span 69.
- 미적용 객체: **0개**입니다. 그래서 적용 절차가 필요 없습니다.
- 다른 DB에 다시 적용해야 할 때는 `schema-readiness-20261025`의 실제 절차를 따릅니다.
  1. identity 확인: host·port·db·`pg_control_system().system_identifier`, data_directory는 superuser가 확인
  2. `pg_dump -Fc` 전체 덤프와 schema-only 덤프를 만들고, sha256 manifest를 만들고, `pg_restore --list`로 파싱되는지 확인
  3. 정식 파일을 원문 그대로 한 트랜잭션으로 적용하고, 새 표에만 GRANT
  4. 기존 표의 행수와 열 multiset 해시를 트랜잭션 안과 commit 뒤 새 연결에서 비교
  5. reader 관문 질의와 새 접수 GET으로 확인
  - 되돌리기는 덤프로 복원하는 것이고, 별도 승인이 필요합니다.

## 산출물

- `probe_main.py`(sha256 `98a2020c…`), `p1-aggregates.json`(`c343de4f…`): 읽기 전용 집계(enum·시각·건수만)
- `probe_cols.py`, `probe_flags.py`: 열과 테넌트 목록 확인
- `ops/launch-ops-jobs.py`: 미실행 실행기 초안

## 한계

- 일꾼과 sweeper를 실제로 실행하지 않았습니다. routing 모드의 `composition.build_controller`와 `wire_optional_features`가 정책 가드 아래에서 성공하는지는 검증하지 않았습니다(실패해도 Case 변화는 없고 fatal 1로 끝납니다).
- 알림 6건과 접수 fatal의 실고객 여부는 테넌트, 계정 종류, 시각으로만 추정했습니다.
- model_failed 2건의 정확한 거절 사유는 기록이 없어 확정하지 못했습니다. 재현에는 제품 모델 호출이 필요합니다.
- web_guard 삭제 대상 건수는 산정하지 않았습니다.
- wiki index 17행의 「shared schema905/archives 별도 남음」(10-25 V10 기록)은 그 뒤 적용으로 해소됐습니다. 원본 wiki index는 고치지 않았습니다.
