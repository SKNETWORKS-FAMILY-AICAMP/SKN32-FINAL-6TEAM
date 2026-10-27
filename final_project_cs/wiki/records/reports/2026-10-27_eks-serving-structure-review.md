# 2026-10-27 AWS EKS 배포 구조 점검 · 빠른 서빙 · 무중단 배포 설계

- 작성: 2026-10-27 14:20~15:10 KST, Claude Opus 하위 작업자(「I 쿠버네티스 EKS 구조·성능 점검」).
- 기준: 팀 저장소 `main` `b4c2847ec`(AWS 배포 코드는 main 에만 있다 — develop 에는 `aws_cd.py`·`cd-aws.yml` 이 없다).
- 근거로 쓴 것: 저장소 파일, GitHub Actions 실행 기록(`gh`), Actions 변수(`CD_AWS_REGION=ap-northeast-2`, `CD_K8S_NAMESPACE=tripilot`).
- **하지 않은 것**: AWS·EKS·x600 접속(이 PC 의 AWS 자격증명 무효 · 14:30 전 금지 지시), 클러스터 읽기·변경, 공개 주소 호출(AWS 공개 주소는 저장소 비밀값 `CD_PUBLIC_URL` 이라 모른다), 푸시. 아래 「클러스터 값」은 **저장소 코드에서 추정**한 것이고 실측이 아니다.

## 결론

1. 지금 배포는 push 부터 교체 완료까지 **30~35분**(실측 5회). 이 중 **배포 자체는 9~10분**이고, 나머지는 CI (web) 브라우저 시험 4묶음(18.5~24.9분)을 기다리는 시간이다. 묶음 1 이 1,100초로 가장 짧은 묶음(632초)의 1.7배라 그 묶음이 전체를 붙잡는다.
2. EKS 교체는 **단일 작은 노드**(코드 주석) 위에서 worker 를 0개로 내리고 api → worker → web → admin 을 차례로 바꾼다. 클러스터 매니페스트(Deployment·Service·Ingress·HPA)는 **저장소에 없다**(손으로 만든 기존 객체를 이미지만 바꾼다) — 노드 크기·requests/limits·probe·교체 방식은 확인 불가.
3. 가장 큰 위험은 **DB 변경이 고객 API 가 도는 중에 잠금 대기 제한 없이 돈다**는 것(P0). 매 배포마다 모든 SQL 을 다시 적용하므로 `ALTER TABLE … IF NOT EXISTS` 도 표 전체 잠금을 잡는다. 긴 쿼리 하나 뒤에 서면 그 표의 모든 API 요청이 최대 600초 줄을 선다.
4. 저장소 안에서 할 수 있는 개선 3건을 **후보 커밋**으로 만들었다(푸시 전): ① DB 변경 잠금 5초·문장 5분 제한 + 결과 기록, ② 실패 단계·원인·단계별 시간 기록, ③ 이미지 게시를 웹 검사 대기와 겹치기 + CI (web) 8묶음. 예상: **30~35분 → 약 20분**(추정 — 다음 실제 배포에서 `timings` 로 잰다). 10분 이내는 클러스터·파이프라인 결정(아래 3·4단계)이 필요하다.

## 진행 표

| 할 일 | 상태 | 진행 |
|---|---|---|
| 규칙·스킬·저장소 읽기 | 끝 | 루트·cs AGENTS/CLAUDE/RULE, wiki index, `guguroute-project-integration` |
| EKS 토폴로지 복원(저장소 근거) | 끝 · 클러스터 값 미확인 | 8/14 항목 = 57% 확인(아래 표의 「확인」 행 수) |
| 문제 목록 | 끝 | 14건(P0 2 · P1 5 · P2 5 · P3 2) |
| 개선 설계 | 끝 | 15건(저장소 후보 3 · 저장소 다음 단계 4 · 파이프라인 결정 2 · 클러스터/비용 6) |
| 후보 구현·시험 | 끝 | `test_aws_cd.py` 40/40 = 100% 통과(기존 25 + 새 15), ruff 0.16.8 통과, actionlint 1.7.12 통과 |
| 푸시 · 실제 배포 측정 | 안 함 | 부모 조율 뒤 |

## 1. 지금 구조

### 1-1. 배포 흐름(실측 시각은 `b4c2847ec`, 2026-10-26 KST 13:41 push)

```
(시작) main push 13:41:09
   ├─ CI (main)   13:41 → 13:50  9.2분  [전체 pytest 7.5분 · Docker 빌드 · ruff]
   └─ CI (web)    13:41 → 14:01 20.2분  [check 2분 · live 4묶음 20.1 / 19.1 / 16.8 / 12.1분]
CD (AWS) 시작 13:50 (CI (main) 끝난 직후)
   gate 작업        13:50 → 14:01 11.1분  ← CI (web) 끝나기를 10초마다 확인하며 기다림
   deploy 작업      14:01 → 14:11  9.8분
     publish        14:02 → 14:07  5.4분  [api·web·admin 순서대로 빌드(캐시 없음) → ECR push 3개]
     deploy         14:07 → 14:11  3.7분  [RDS 복구 시각 확인 → 마이그레이션 Job → worker 0개
                                            → api → worker → web → admin 차례 교체 → 검증 → 30초 뒤 재검증]
(끝) 14:11:18 결과 산출물 업로드 — push 부터 30.2분
```

같은 모양 5회 실측(`gh run list` · 실행 id 40271109330 · 40266644824 · 40239967442 · 40190213453 · 40182858336): CD 실행 18.6~24.1분, push→완료 29.5~35.2분. publish 4.2~5.6분, deploy 3.7~4.3분.

### 1-2. EKS 토폴로지(저장소 근거 · 추정 표시)

```
            GitHub Actions (OIDC 단기 역할)
               │ docker push (git-<sha>)        │ kubectl patch (이미지 digest만)
               ▼                                ▼
   ECR: tripilot-api · tripilot-web · tripilot-admin     EKS (ap-northeast-2), ns tripilot
                                                ┌──────────── 노드 1대(추정: "single small node") ─────────────┐
   공개 주소(비밀값) ── [진입: 미확인 Ingress/LB] ─▶│ tripilot-web  (Next.js next start :3000)                    │
                         /v1/* → api(추정)       │ tripilot-api  (uvicorn :8043, /health)                      │
                                                │ tripilot-worker (api 와 같은 이미지, worker.sh)               │
                                                │ tripilot-admin (api 이미지 + node, admin_runner :3300/:8070)  │
                                                │ 마이그레이션 Job (api 이미지, 배포 때만)                         │
                                                └───────────────────────┬──────────────────────────────────────┘
                                                                        ▼
                                                          RDS PostgreSQL(이름 비밀값, 7일 백업 확인)
   모델 호출: 경로 local / ssh / api 중 무엇인지 미확인(아래 1-3)
```

| 항목 | 지금 값 | 근거 | 확인 |
|---|---|---|---|
| 리전·네임스페이스 | ap-northeast-2 · tripilot | Actions 변수 | 확인 |
| 앱 | Deployment 4개(api·worker·web·admin), 각 컨테이너 1개 | `aws_cd.py APPS` · 사이드카 거부 | 확인 |
| 이미지 | ECR, `git-<sha>` 태그 → digest 로 배포, worker=api digest | `publish()` | 확인 |
| 런타임 자료 | `/srv/datasets` · 알림 문구를 **직전 운영 이미지에서 복사**(지문 비교) | `deploy/aws/Dockerfile.api` | 확인 |
| DB | RDS, 7일 보존 · 20분 안 복구 시각 요구, 마이그레이션은 매번 전체 SQL 한 트랜잭션 | `check_database_backup` · `migrate.py` | 확인 |
| 교체 순서 | worker 0개 → api → worker 복원 → web → admin, 앱마다 420초 대기 | `deploy()` | 확인 |
| 실패 복구 | 직전 template·replicas 로 되돌림, DB 는 앞으로만 | `deploy()` | 확인 |
| 완료 판정 | digest·준비·재시작 0 + 공개 `/health`·`/` 200, 30초 뒤 재확인 | `verify` · `public_health` | 확인 |
| 노드 수·크기 | 1대·작음(인스턴스 종류 모름) | 코드 주석 | 추정 |
| replicas | 기존 값 유지(api 1 추정 — 「API 두 개를 못 올린다」) | 주석 · wiki | 추정 |
| requests/limits | 모름(시험 표본의 api limit 1536Mi 는 가짜 값). x600 compose 는 api 1g · worker 2g/2cpu · web 1g/1cpu · admin 768m/1cpu | `docker-compose.yml` | 미확인 |
| 교체 방식·probe | 모름(시험 표본은 `Recreate` · readinessProbe `/health`) | 시험 표본 | 미확인 |
| Ingress/LB·TLS·CDN | 모름 | 저장소에 없음 | 미확인 |
| HPA·PDB | 없을 가능성 높음(저장소에 없음, 단일 노드) | — | 미확인 |

클러스터 담당자가 읽기만으로 채울 명령(이 세션은 실행하지 않았다):
`kubectl -n tripilot get deploy -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.replicas}{" "}{.spec.strategy}{" "}{.spec.template.spec.containers[0].resources}{" "}{.spec.template.spec.containers[0].readinessProbe}{"\n"}{end}'`,
`kubectl get nodes -L node.kubernetes.io/instance-type`, `kubectl -n tripilot get ingress,svc,hpa,pdb`, `kubectl -n tripilot top pods`.

### 1-3. 모델 호출 경로

저장소의 모델 경로는 `local`(그 기계의 Ollama E4B) · `ssh`(터널 너머 RunPod/다른 기계 Ollama) · `api`(유료, 채팅만) 셋이고 운영 설정 → 환경 파일 → `local` 순서로 고른다([모델 경로 계약](../../external/llm-model-route.md)). **EKS 에 GPU 노드가 있다는 근거는 저장소에 없고**, 단일 작은 노드에서 E4B 를 CPU 로 돌리는 구성도 없다. 그러므로 AWS 의 채팅·계획 읽기는 ① 다른 곳 Ollama(x600·RunPod)를 부르거나 ② 넘김 장치로 유료 API 로 가거나 ③ 실패 중일 수 있다 — **어느 것인지 미확인**. 확인 방법(읽기만): api 파드의 `ACOP_OLLAMA_BASE_URL`·`ACOP_OLLAMA_SSH_BASE_URL`·`ACOP_MODEL_ROUTE_*`·`ACOP_LLM_FAILOVER*` **이름 존재 여부**와 관리 콘솔 「모델 경로」 설명 줄의 「준비됨」 표시. 일정 짚기·공지 확인은 API 경로가 없어 모델을 못 부르면 규칙으로 돌아간다(계약).

## 2. 문제 목록

| # | 등급 | 문제 | 근거 | 영향 |
|---|---|---|---|---|
| 1 | P0 | DB 변경이 고객 API 가 도는 중에 **잠금 대기 제한 없이** 실행. 전체 SQL 을 매번 다시 적용해 no-op `ALTER` 도 표 잠금을 잡는다. worker 는 마이그레이션 **뒤에** 멈추므로 worker 의 긴 트랜잭션과도 겹친다 | `migration_job` · `migrate.apply_all` · `deploy()` 순서 | 긴 쿼리 뒤에 DDL 이 서면 그 표의 모든 요청이 Job 제한 600초까지 대기 → 사실상 장애 |
| 2 | P0 | 단일 노드 · api 1개 · worker 강제 정지 — 노드 장애·노드 교체·OOM 이면 전 서비스 중지, 배포마다 worker(알림 배달·감시) 3~4분 정지 | 주석 · `pause_worker` | 고가용 불가, 배포 중 알림 지연 |
| 3 | P1 | 실패 원인이 남지 않는다. 10-24 실패(실행 40060147442)는 「Deployment and image recovery failed」 한 줄뿐 — 어느 앱·단계인지 로그에 없음 | 실행 로그 | 복구 판단이 클러스터 접속자에게만 가능 |
| 4 | P1 | 실패·불확실 Job 이 하나 남으면 다음 배포 전부가 멈추는데, 그 Job 이 롤백된 것인지(재시도 안전) 커밋 여부를 모르는 것인지 구분이 없다 | `require_clean_jobs` | 교착 — 사람이 Job 을 지우기 전까지 배포 불가, 판단 근거 없음 |
| 5 | P1 | CI (web) live 4묶음 불균형(1,100 / 851 / 910 / 632초)이 배포를 11분 붙잡는다 | 실행 40270328504 파일별 집계 | push→배포 30~35분 |
| 6 | P1 | 이미지 게시(5.4분)가 웹 검사 대기 **뒤에** 순서대로 돈다 | `cd-aws.yml` | 배포 5분 지연 |
| 7 | P1 | 교체 중 끊김 가능: 단일 replica 에서 preStop·graceful 종료 설정이 저장소에 없고, 채팅·계획 읽기 SSE 는 수 초~수십 초 열린다. (교체 방식이 Recreate 면 매번 수십 초 중단) | 매니페스트 부재 · 시험 표본 `Recreate` | 교체 순간 진행 중 요청 끊김 · 502 |
| 8 | P2 | CD 빌드에 캐시가 없다(`docker build` 직접, 매번 pip 38초 · npm ci · Next 빌드). CI (main) 이 같은 Dockerfile 을 gha 캐시로 빌드하지만 CD 는 그 캐시를 안 쓴다 | 로그 · `ci-main.yml` | publish 5분 |
| 9 | P2 | admin 이미지가 api 이미지 전체 위에 node·admin 을 얹고, 다른 ECR 저장소라 같은 층을 다시 올린다(로그상 api 층 17개 재-Pushed) | `Dockerfile.admin` · 로그 05:06:43~07:29 | push 2.5분 · 노드 디스크·메모리 |
| 10 | P2 | 웹 이미지가 Next standalone 이 아닌 `/app` 전체(node_modules 포함) + `npx next start` | `Dockerfile.web` | 이미지 크기 · 기동 시간 |
| 11 | P2 | 런타임 자료(`/srv/datasets`)를 직전 운영 이미지에서 이어 복사 — Git 으로 다시 만들 수 없다 | `deploy/aws/Dockerfile.api` | ECR 이미지가 사라지면 복구 불가 |
| 12 | P2 | 클러스터 매니페스트가 저장소에 없다(requests/limits·probe·교체 방식 검토·재현 불가) | 저장소 검색 0건 | 구조 변경 검토 불가 · 사람 손 변경 추적 불가 |
| 13 | P3 | 공개 상태 확인이 `/health`·`/` 두 개뿐 — 모델 경로·DB 쓰기 경로는 확인 안 함 | `public_health` | 「배포 성공」인데 채팅 실패 가능 |
| 14 | P3 | 모델 경로가 AWS 에서 무엇인지 기록이 없다(1-3) | — | 지연·비용·실패 원인 불명 |

## 3. 서빙 속도 · 무중단 설계

### 3-1. 배포 시간 목표(단계별)

| 단계 | 내용 | 누가·무엇이 필요 | push→완료 목표 |
|---|---|---|---|
| 0 (지금) | — | — | 30~35분(실측) |
| 1 (이번 후보) | 게시를 웹 대기와 겹치기 · CI (web) 8묶음 · 잠금 제한 · 원인/시간 기록 | 저장소 푸시만 | **약 20분**(추정: max(CI main 9 + 게시 6, CI web 12~13) + 배포 4~5) |
| 2 | CD 빌드에 BuildKit 캐시(gha, CI (main) 과 같은 범위) · 세 이미지 동시 빌드(`buildx bake`) · admin 을 api 이미지와 분리 또는 같은 저장소 층 공유 · Next standalone | 저장소, 시험용 배포 1회 | 약 16~17분(게시 6 → 2~3분, 추정) |
| 3 | 파이프라인 결정: ① main 으로 오는 PR 에서 이미 통과한 **같은 트리**의 CI (web) 결과를 push 때 재사용, 또는 ② 바뀐 부분만 배포(api 만 바뀌면 웹 검사를 기다리지 않음) · CI (main) pytest 를 2~3 작업으로 나누기 | **사용자 결정**(검사 정책) | **약 10분 이내**(CI main 5~6 + 배포 4) |
| 4 | 클러스터: 노드 여유(2대 또는 한 단계 큰 1대) · api replicas 2 + PDB · `maxSurge 1 / maxUnavailable 0` · preStop · readiness/startup probe → worker 정지 없이 교체, 배포 단계 2분대 | **사용자 결정 · 비용 · 클러스터 권한** | 배포 단계 4 → 2~3분, **교체 중 끊김 0 목표** |

### 3-2. 무중단 롤링(클러스터 변경 — 제안만, 실행 안 함)

- api·web·admin: `strategy: RollingUpdate, maxSurge: 1, maxUnavailable: 0`, readinessProbe(api `/health` · web `/` · admin 8070 `/health`), startupProbe(기동 40~60초 — Dockerfile HEALTHCHECK 값과 맞춤).
- 종료: `preStop: sleep 10`(엔드포인트 제거가 퍼질 시간) + uvicorn `--timeout-graceful-shutdown`, `terminationGracePeriodSeconds` 는 가장 긴 SSE(채팅 맨 위 상한 15초 · 계획 읽기 상한)보다 길게. 값은 가드레일·실측으로 정하고 하드코딩하지 않는다.
- api `replicas: 2` + `PodDisruptionBudget minAvailable: 1` — 노드 1대로는 메모리가 모자라 worker 정지가 필요했던 것이 원인이므로 **노드 용량이 먼저**다.
- worker: 단일 소유(되잡기·배달 중복 방지 규칙)이므로 replicas 1 유지, `Recreate` 가 맞다. 배포 중 정지 시간은 api 교체 시간만큼 남는다.
- HPA: 시연 부하에서는 의미가 작다(노드 1~2대). 노드 늘린 뒤 api CPU 기준 2~3개 정도만 제안.

### 3-3. 노드·파드 용량 선택지(가격은 AWS 공개 가격표로 다시 확인 필요 — 이 세션은 조회하지 않았다)

| 선택 | 무엇 | 장점 | 위험·비용 |
|---|---|---|---|
| A 지금 유지 | 작은 노드 1대 | 비용 그대로 | P0-2 그대로, 교체 중 worker 정지 |
| B 노드 한 단계 키우기 | 같은 1대, 메모리 2배 | api 2개 동시 → 무중단 롤링, worker 정지 불필요 | 노드 장애 시 전체 중지는 그대로. 비용 약 2배(인스턴스분) |
| C 노드 2대(작은 것) | 노드 그룹 min 2 | 노드 장애 견딤 + PDB | 비용 약 2배, RDS·LB 비용은 같음 |

### 3-4. 정적 캐시 · API 응답 캐시

- 웹 `/_next/static/*` 는 내용 지문 이름이라 1년 캐시 가능 — 앞단(CloudFront 또는 Ingress)에 두면 노드 부하·첫 화면 지연이 준다. CloudFront 는 유료 서비스 추가라 **사용자 결정**.
- API 응답 캐시: 고객 여행 상태는 정본이 링크(늘 최신)라 캐시하면 「링크가 늘 최신」 DoD 와 충돌한다. 캐시 후보는 공공 조회(장소 목록·운영시간·날씨)처럼 이미 앱 안 캐시가 있는 것뿐 — 새 공용 캐시는 제안하지 않는다.

### 3-5. 모델 서빙 위치

| 선택 | 지연 | 비용 | 위험 |
|---|---|---|---|
| ① x600 Ollama 를 터널/VPN 으로 호출(지금 x600 과 같은 모델) | 망 왕복은 수 ms~수십 ms, 생성 시간이 대부분 | 추가 없음 | 집 회선·x600 가동에 묶임, 터널 끊김 |
| ② RunPod GPU(SSH 경로, 이미 있음) | ①과 비슷 | 켠 시간만큼 | 포드 재생성 때 주소 변경 |
| ③ EKS 안 GPU 노드(같은 VPC) | 망 지연 최소 | GPU 인스턴스 상시 요금(가장 큼) · 스팟 가능 | NVIDIA 플러그인·모델 이미지 관리, 단일 노드 구조 변경 |
| ④ 유료 API(채팅만) | 공급자 지연 | 토큰 비용 | 학습 E4B 가 아님, 일정 짚기·공지 확인은 규칙으로만 |

권고: 먼저 AWS 의 실제 경로를 확인한다(1-3). 시연 지연의 대부분은 망이 아니라 생성 시간이므로 **망 위치를 바꾸는 ③은 실측 근거 없이 권하지 않는다**. 측정 방법: 같은 질문 10회를 ①·②·④ 로 보내 첫 조각 시간·전체 시간 중앙값 비교(비용·부하가 드니 사용자 승인 뒤).

## 4. 이번 후보(저장소 안 · 푸시 전)

| 후보 | 파일 | 내용 | 시험 |
|---|---|---|---|
| A 잠금 대기 제한 + 결과 기록 | `deploy/aws_cd.py` | 마이그레이션 Job 이 `lock_timeout 5s` · `statement_timeout 5min` 을 걸고 서버 값(`current_setting`)으로 받아들여졌는지 확인한 뒤에만 적용. 실패하면 `failed_before_commit`(오류 종류·SQLSTATE), 커밋 중 끊기면 `commit_unknown` 을 종료 기록에 남긴다. 다음 배포를 막을 때 그 결과를 오류 문장에 적는다(막는 규칙 자체는 그대로) | 새 8건 |
| B 실패 단계·시간 기록 | `deploy/aws_cd.py` · `cd-aws.yml` | 성공 기록에 단계별 초(`timings`), 실패 때 `aws-deploy-failure.json`(단계 · 우리 오류 문장 또는 예외 종류 이름만 · DB 변경 결과 · 복구 결과) 산출물 | 새 4건 |
| C 게시 겹치기 · CI (web) 8묶음 | `cd-aws.yml` · `aws_cd.py gate --main-only` · `ci-web.yml` | 한 작업에서 CI (main) 성공 확인 → 게시 → 전체 검사 대기 → 자격 갱신 → 배포. 이미 실패한 검사가 있으면 게시도 안 함. 웹 live 묶음 4→8(시험 내용·workers 1 그대로) | 새 3건 · actionlint 통과 |

- 실행: `python -m unittest tests/unit/deploy/test_aws_cd.py` → **40/40 = 100%**(기존 25 그대로 통과, 새 15). 처음(RED) 실행(워크플로 시험 추가 전 39개)은 18개 실패 — 새 시험 14개 전부와, 바꾼 배포 시험 도우미(새 함수 `job_outcome` 을 가로챔)를 쓰는 기존 4개. 워크플로 순서 시험은 옛 `cd-aws.yml` 에 대해 따로 실패를 확인했다. ruff 0.16.8(CI 와 같은 판) 통과, actionlint 1.7.12(CI 와 같은 판, windows_arm64 체크섬 일치) 통과.
- 이 PC 는 Python 3.14 로 돌렸다(CI 는 3.12). 실제 Postgres·EKS·GitHub 실행으로는 확인하지 않았다 — `lock_timeout` 동작·종료 기록 읽기·8묶음 시간은 다음 실제 실행에서 확인해야 한다.
- 계약 문서 [aws-main-cd.md](../../operations/aws-main-cd.md) 에 `[2026-10-27 후보]` 세 줄을 먼저 더했다.

## 5. 필요한 사용자 결정 · 권한

1. 잠금 대기 `5s` 가 적절한가(짧으면 배포가 자주 멈추고, 길면 그만큼 API 가 줄 선다). 지금 값은 이 보고서의 제안이다.
2. 3단계 파이프라인 정책: PR 에서 통과한 같은 트리 결과 재사용 또는 바뀐 부분만 배포 — 「풀 테스트는 main 만」(10-19 결정)과 겹치므로 결정 필요.
3. 4단계 클러스터 비용(노드 B/C), CloudFront 추가 여부, 모델 경로(①~④).
4. 권한: 클러스터 **읽기**(1-2 의 미확인 6항목 · 1-3 모델 경로), 유효한 AWS 자격증명. 클러스터 매니페스트를 저장소로 가져오는 일(문제 12)은 읽기 권한만으로 시작할 수 있다.

## 남은 일

- 후보 푸시(부모 조율) → main 반영 뒤 첫 CD 실행의 `timings`·CI (web) 8묶음 시간 실측으로 이 보고서의 추정을 바꾼다.
- 클러스터 읽기 권한이 생기면 1-2 표의 「미확인」을 채우고 3-2 의 값(probe·grace)을 실측으로 정한다.
- 근거 파일: 실행 로그 사본·묶음 집계 스크립트는 작업자 스크래치 `eks-serving-20261027/evidence/` 에 있다(저장소 밖).
