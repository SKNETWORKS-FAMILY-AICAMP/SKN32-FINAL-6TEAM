---
type: report
title: EKS 릴리스 2026-10-28 독립 검증 — 배포 성공 · 실측 재계산 · CD 1차 실패 시각 분해 · 남은 병목 프로파일링 · 측정 접수 26건 처리
description: R 보고서(2026-10-28_eks-release-deploy-and-before-after-latency)를 GitHub 기록·증거 원본으로 다시 확인하고, 격리 PG 로컬 복제로 접수 읽기 병목을 프로파일링했다. CD 진단 개선 후보 1커밋(미반영)
status: draft
domain: travel
impl_scope: cs — 검증 · 진단. 운영 DB · EKS · 원격 push 0. scratch clone 후보 커밋 72ba5ff48(deploy/aws_cd.py + 시험)만
---

# EKS 릴리스 2026-10-28 독립 검증 (23:15~00:20 KST, V 세션)

## 결론

| 질문 | 답 | 근거 |
|---|---|---|
| EKS 배포 성공 | **확인.** CD (AWS) `40699378486` success(main `20c296e77`, workflow_dispatch). 결과 파일의 4앱 digest · ready · 공개 `/health` · `/` 200 일치. 00시 현재 `/health` 200 (Cloudflare 경유) | `gh run list/view`, `cd_art2/aws-deploy-result.json` |
| R 의 전후 수치 | **재현됨.** 원본 json 26행(전 13 · 후 13, 모두 `result`, id 앞 8자리 26개 서로 다름)에서 p50 · 순열 검정 p 를 다시 냈다: 끝까지 45.59→32.14초(p≈0.20) · GET 끝 52.75→33.65(p≈0.19) · 읽기 뒤 GET 3.73→1.22(p≈0.06) · SSE 최대 간격 4.05→3.01(p<0.001). 결론(간격만 개선 확정, 속도는 미확정)도 같다 | `before*.json` · `after_*.json` |
| CD 1차 실패 원인 | **반만 확인.** 실패는 verify 의 **첫 공개 확인**에서 났다. 기록된 verify 153.4초는 실패 시간이 아니라 **되돌리기 시간이 섞인 값**이다(아래 시각표). 오류 형식은 `URLError` = 연결 단계(DNS · 연결 · TLS) 실패이고 HTTP 응답 오류(HTTPError)나 읽기 시간 초과(TimeoutError)가 아니다. 어느 쪽인지는 실패 기록이 이유를 지워 **알 수 없다** | `cd1_full.log` 시각 · `aws_cd.py` |
| 남은 병목 | 운영의 확인 단계(`checking`→`review`)가 **최소 19.3초**로 빠른 회차에서도 전체의 약 70%다. 로컬 격리 복제(같은 글 · 같은 측정 스크립트 · 바깥 연결 차단)에서 같은 구간은 데워진 뒤 1.3~2.8초 → 나머지 약 17초는 **운영에만 있는 바깥 조회 · RDS 왕복 · 모델 호출**로 보인다. 운영 단계 로그(`intake stage timing`)가 코드에 있으나 AWS 자격증명이 없어 못 읽었다 — **운영 귀속은 미확정** | 로컬 프로파일 · 아래 표 |
| 반영 | **성능 코드 반영 0.** 근거 없이 바꿀 만한 확정 후보가 없다(아래 후보 3개는 측정 근거 · 위험 기록). CD 진단 개선 1커밋은 시험 통과했으나 **push 안 함** — S2 가 role-manager 통합 중이고 main 반영은 PR · CD 를 다시 돌린다 | 협업 알림 |
| 측정 접수 26건 | **수동 삭제 불필요 · 불가.** 운영 일꾼의 게스트 정리(마지막 사용 + 168시간, 기본 켜짐)가 약 **2026-11-04 21:2x~23:1x KST** 이후 회차에 지운다. 단 지우기 직전 `intake_backups` 에 통째로 백업되고 보관 기간 기본값이 **0 = 영구**라, 합성 측정 26건이 「계획 읽기 골든셋 재료」 백업에 영구히 섞인다 | `guest_cleanup.py` · `backup.py` · `guardrails.yaml` |

## 1. CD 1차(run 40697290826) 시각 분해

배포 단계 시작 13:38:19.5Z, 단계 시간을 차례로 더하면:

| 단계 | 끝난 시각(UTC) |
|---|---|
| preflight 8.8 · migration 30.5 · worker-pause 4.2 | 13:39:03 |
| api 80.2 · worker 8.4 · web 33.8 · admin 16.9 | **13:41:22** (verify 시작) |
| 되돌리기의 `pause_worker` 가 남긴 `pod/tripilot-worker… condition met` | **13:41:45.7** |
| 실패 기록 출력(되돌리기 끝) | 13:43:55.7 |

- 되돌리기는 예외 직후 시작하므로 실패는 13:41:22~13:41:45 사이, 즉 verify 진입 후 **약 23초 안**이다. 성공 회차의 verify 53.3초 = 30초 쉼 + 두 번의 (k8s 확인 + 공개 확인) → 1회 약 11.6초. 첫 공개 확인이 통과했다면 30초 쉼 때문에 13:41:45 전에 실패할 수 없으므로, **첫 공개 확인(/health 또는 /)이 실패**했다.
- 153.4초 중 약 130초는 되돌리기(4앱 원복 대기)다. R 보고서의 「공개 확인 15초 제한 초과 추정」은 시각상 가능하지만(연결 시간 초과도 `URLError(timeout)`), DNS · 연결 거절 · TLS 실패와 구별할 근거가 없다. 공개 경로는 Cloudflare(`server: cloudflare`, A 2 · AAAA 2) 뒤다.
- 후보 커밋 `72ba5ff48`(scratch `eks-verify-20261028/repo`, 패치 sha256 앞 `b82c761681b42509`): ① 공개 확인의 연결 단계 실패(`URLError`, `HTTPError` 제외)만 5초 쉬고 최대 3회 ② 실패 기록 `error` 를 `URLError(TimeoutError)` 처럼 **이유의 형식 이름만** 덧붙임(본문 · 주소는 안 남김) ③ 실패 단계 시간과 `recovery` 시간을 따로 기록. RED 4 → GREEN, `test_aws_cd.py` + `test_migration_lock_policy.py` 80/80, ruff 통과. 재시도는 일시 장애를 가릴 수 있으므로 반영 여부는 사용자/부모 판단.

## 2. 운영 실측의 단계 분해(R 원본 26행 · SSE 이벤트 첫 시각)

| 구간(초) | 전 p50 (최소~최대) | 후 p50 (최소~최대) |
|---|---|---|
| 접수 → `accepted` | 0.66 (0.40~12.77) | 0.42 (0.38~10.95) |
| 읽기(`accepted`→`checking`) | 6.56 (5.38~23.07) | 7.09 (4.56~21.10) |
| **확인(`checking`→`review`)** | **19.74 (19.30~47.84)** | **20.57 (19.39~55.56)** |
| `review`→`done` | 1.12 (0.81~22.33) | 1.09 (0.79~10.39) |
| 읽기 끝 뒤 GET | 3.73 (0.62~29.48) | 1.22 (0.60~21.16) |

- `checking` 단계에는 첫 검사(운영시간 · 위험 · 이동)와 **먼저 채우기 · 해석 답 반영**이 함께 든다(`pipeline.process` — 채우는 동안 stage 가 `checking` 에 머문다).
- 6회는 접수 POST 자체가 5.5~6.8초였다(평소 0.2초). 고정값에 가까운 지연이라 시간 초과형 대기로 보이나 **원인 미확인**(서버 로그 없음).
- 후 첫 회 `after_a-1`(배포 확인 뒤 약 1분)은 끝 72.5초 · GET 21.2초 — 아래 3-②의 막 뜬 pod 데우기와 맞는 모양이다.

## 3. 로컬 격리 복제 프로파일링 (main `20c296e77` 트리, PG16 55591 자체 클러스터, 이동 자료 `datasets/mobility/processed` 읽기만, LLM mock, 바깥 연결 차단)

같은 계획 글 · 같은 `probe_intake.py`(주소만 환경 변수)로 uvicorn 서버에 9회 + cProfile 3회.

| 관찰 | 값 | 뜻 |
|---|---|---|
| 데워진 뒤 | 끝 8.4~8.6초 · 읽기 2.8~4.3 · 확인 1.3~2.8 · GET 2.7초 | 운영 확인 19.3초 중 로컬 CPU 몫은 작다 → 운영 차이는 바깥 조회 · DB 왕복 · 모델 쪽(미측정) |
| 막 뜬 서버 | 끝 53.1초 · `check_s` 43.6 · **GET 34.7초**(다른 회 31.8) | 기동 때 도는 이동 그래프 데우기 스레드(`mobility-router-warm`, `car.py` 그래프 적재)가 GIL 을 잡아 같은 프로세스의 확인 · 조회가 굶는다. 0.2초 표본기가 36초 동안 19회만 깨어났다(정상 약 180회) |
| DB 연결 | 접수 1건(SSE · GET 포함)당 **새 연결 약 142회**(풀 없음 — `session.get_connection` 이 매번 `psycopg.connect`). 많은 곳: `prepared.py` 54/건 · 위험 캐시 `cache.get` 24/건 · 진행 쓰기 8/건 | 운영에서는 매번 RDS 이름 풀이 + TCP + TLS + 인증이다. 로컬 Windows PG 의 연결 1회 158ms 는 프로세스 생성 비용이라 운영값으로 쓰지 않는다 |
| 확인 단계 CPU(프로파일) | 이동 판정(버스 후보 `verify_leg_bus` 2,401회 · `bus_profile.walk`) · 대안 미리 준비 `candidates.assess` 114회 | 공개 뒤(대안 · 요식 판정)도 API pod 의 백그라운드 작업으로 돈다(`BackgroundTasks`) |

### 반영하지 않은 개선 후보 (근거 · 위험)

1. **DB 연결 재사용(풀).** 접수당 연결 ~142회를 줄인다. 위험: psycopg 자동 prepare · 세션 설정(`set_config(...,false)`) · 권고 잠금이 연결을 넘어 샐 수 있어 초기화 설계가 필요하고, EKS 이미지는 기존 런타임을 유지해 새 패키지(`psycopg_pool`)가 설치되지 않는다(`deploy/aws/Dockerfile.api`). 운영 연결 1회 비용을 재지 않으면 효과를 말할 수 없다.
2. **데우기 끝난 뒤에만 준비 상태.** 배포 직후 첫 고객이 데우기와 겹치지 않게. 위험: `/health` 의미 변경이 CD verify · x600 compose 에 걸리고, 준비 확인 설정은 클러스터 쪽이라 저장소에 없다.
3. **공개 뒤 무거운 작업을 API 밖(일꾼)으로.** 10-28 80초 인계의 후보 2와 같다 — 사용자 결정 사항.

## 4. 측정 접수 26건

- 접수 취소 API 의 409 는 정상이다 — `cancel` 은 **다시 연 수정 접수 전용**이라 보통 접수에는 `intake_not_reopened` 를 낸다(`reopen.cancel`). 손님이 보통 접수를 지우는 API 는 없다.
- 자동 처리: EKS 일꾼(`deploy/worker.sh` → `scripts/run_sweepers.py` `_run_web_guard`)의 `cleanup_guests` 가 소셜 연결 없는 `web:` 고객 중 마지막 사용 + `web.guest_idle_hours`(168) 지난 고객을 사용자마다 한 트랜잭션으로 지운다(`member_cleanup.erase_customer`). 측정 손님은 여행 0건이라 일정 유예가 없다. 관리 콘솔에서 값이 바뀌었는지는 **확인 못 함**.
- 남는 것: 지우기 직전 `intake_backups` 로 접수 · 원문 · 값 · 검사가 백업되고 `retention.intake_backup_days: 0`(지우지 않음)이다. 합성 측정 26건이 골든셋 재료 백업에 **영구히** 남는다.
- 지금 직접 지우는 것은 권하지 않는다: 운영 DB 쓰기 권한이 없고(AWS 자격증명 없음), 앱에 손님 접수 삭제 API 가 없어 SQL 직접 삭제가 되는데 접수 · 원본 · 값 · 검사 · 진행 · 손님 · 세션 · 키에 걸친다. 안전한 길은 ① 자동 정리에 맡기고 ② 골든셋을 뽑을 때 `reason='guest_cleanup'` · `received_at` 2026-10-28 21:23~23:09 KST · 원문 일치(6일정 고정 글)로 제외하는 것이다. 식별: R scratch `summary.json` 의 id 앞 8자리 26개(전체 id 는 저장 안 됨).
- 사용자 결정 필요: 백업에서 26건을 지울지 · 표시만 할지. 지운다면 운영 읽기/쓰기 권한 확보 뒤 대상 26행을 먼저 읽기 전용으로 대조(시각 · 원문 해시 · 앞 8자리)하고 한 트랜잭션으로 처리한다.

## 5. 지킨 것 · 막힌 것 · 증거

- 운영 쓰기 · 새 운영 접수 · 유료 호출 · 고객 정보 조회 0(이번 세션은 운영에 `/health` GET 과 DNS 조회만). 원본 작업 폴더 코드 0, 원격 push 0.
- 막힘: AWS 읽기 자격증명 없음 → pod 로그(`intake stage timing` · `intake prefill timing`) · CPU · RDS 연결 지표 · 배포 설정(replicas · readinessProbe · 전략) 미확인. 임의 비밀은 쓰지 않았다.
- 증거: Hermes scratch `eks-verify-20261028/` — `cd1_full.log` · `cd2_full.log`(gh run log) · `aws_cd.py`(main 원본) · `prof/`(`base_runs.json` · `a_runs.json` · `conn_*.jsonl` · `sample_a.jsonl` · `base_post_*.prof`) · `probe_local.py` · `serve_counted.py` · `prof_intake.py` · `red.txt` · `green.txt` · `0001-*.patch`. 로컬 PG 는 멈췄다(`pgdata/` 그대로).
