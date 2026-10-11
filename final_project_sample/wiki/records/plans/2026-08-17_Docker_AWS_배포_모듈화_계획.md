# Docker · AWS 배포 모듈화 계획 (초안, 미착수)

> ★이 문서는 계획 누락을 되짚어 만든 것이다. 사용자가 "Docker·AWS를 배포에 쓴다"고
> 이전에 정했다고 알려왔는데, 이 저장소의 git 히스토리·`docs/`·`config/project.yaml`
> 어디에도 반영돼 있지 않았다. 지금 계획으로 등록하고, 실제 구현은 범위를 확정한
> 뒤 진행한다. 관련 확인 사실은 `A-COP_구현계획서_v7.md`(읽기 전용) §13 — 그 문서는
> Docker 를 "Phase 2" 로 미뤄뒀는데, 사유는 **로컬 개발 기계에 Docker 가 없다**였다.
> 그건 로컬 dev 환경 얘기지 배포 타깃을 부정한 게 아니다.

## 0. 지금 상태 (사실관계, 2026-08-17)

- 로컬 개발 기계: Docker **미설치** (`docker --version` 실패 확인). conda env `pgv` 로
  Postgres 를 돌린다. 이건 안 바뀐다 — 로컬 dev 트랙은 그대로 유지한다.
- 배포 타깃: **아직 코드에 없다.** `docker/` 디렉터리가 존재하지 않고, Dockerfile ·
  docker-compose · AWS 관련 IaC(Terraform/CDK/CloudFormation) 아무것도 없다.
- `config/project.yaml` 의 모듈·Port 목록에 "배포 타깃"이라는 축 자체가 없다.

## 1. basement 원칙과의 정합성

이 저장소(`final_project_sample`)는 **어디든 이식 가능한 basement**다. Docker·AWS
배포는 도메인 특정 로직이 아니라 **인프라 모듈화** 대상이므로 이 원칙과 충돌하지
않는다. 기존에 이미 있는 Port 패턴 — `team_executor`(local/a2a), `message_broker`
(outbox/…), `graph_store`(sql/…) — 과 같은 방식으로 다뤄야 정합적이다:

- 배포 타깃 자체를 "코드가 아는 것"으로 만들지 않는다. 애플리케이션 코드는
  로컬이든 컨테이너든 AWS 위든 **똑같이** 동작해야 한다 — 그래야 basement 다.
- 컨테이너화·배포는 애플리케이션 바깥의 관심사다: `Dockerfile`, `docker-compose.yml`
  (로컬 재현용), 배포 스크립트/IaC 는 **환경 설정**이지 **모듈**이 아닐 가능성이 크다.
  다만 "메시지 브로커를 SQS 로 바꾼다" 같은 AWS 매니지드 서비스 교체는 기존
  Port 패턴에 자연스럽게 들어간다 (`message_broker: outbox` → `message_broker: sqs`
  같은 식).

## 2. 확인이 먼저 필요한 것 (사용자 확답 없이 구현 시작하지 않는다)

- **컨테이너 범위**: 애플리케이션만 컨테이너화하나, DB(pgvector)도 컨테이너로
  가나 아니면 RDS(+ pgvector 확장 지원 확인 필요)로 가나?
- **AWS 컴퓨트**: ECS Fargate / EC2 / App Runner / Lambda 중 어느 쪽을 목표로 하나?
- **AWS 매니지드 서비스 교체 범위**: 지금 Outbox(In-Process/DB 기반)를 SQS 로,
  로컬 파일 시스템을 S3 로 바꾸는 것까지 이번 스코프에 넣나, 아니면 1단계는
  "컨테이너 이미지 하나를 ECS 에 올리는 것"까지만인가?
- **비밀 관리**: `.env` 로컬 방식에서 AWS Secrets Manager/Parameter Store 로
  바꾸는 시점 — 이번 스코프인가?
- **CI/CD**: 이미지 빌드·푸시·배포 파이프라인(GitHub Actions 등)까지 이번
  스코프에 포함하나?

## 3. 제안하는 1단계 (최소 범위)

확답 전이라도 리스크가 낮고 되돌리기 쉬운 범위:

1. `Dockerfile` 작성 — 애플리케이션 이미지 하나. 로컬에서 `docker build`/`docker run`
   으로 검증(단, 이 기계엔 Docker 가 없으므로 **사용자 기계 또는 CI 에서 검증** 필요).
2. `docker/compose.yml` — 앱 + Postgres(pgvector) 로컬 재현용. **conda env `pgv`
   경로를 대체하지 않는다** — 병행이다.
3. `wiki/records/handoff/14_배포_계약.md` (가칭) — 배포 타깃이 애플리케이션 코드에 어떤
   가정도 강요하지 않는다는 계약을 명시 (환경변수로만 설정 주입, 특정 클라우드
   SDK 를 애플리케이션 코드에 직접 import 하지 않는다 등).

AWS 리소스 프로비저닝(IaC)·매니지드 서비스 교체는 §2 확답 이후 2단계로 미룬다.

## 4. 상태

**미착수.** `CLAUDE.md` 상태표에 이 항목을 반영해 둔다.

★2026-08-17: 사용자 확인 — 오늘은 이 계획 문서 등록까지만, 구현은 다음 세션으로
미룬다. 다음 세션에서 작업을 시작하려면 §2 의 확인 항목(컨테이너 범위 · AWS
컴퓨트 · 매니지드 서비스 교체 범위 · 비밀 관리 · CI/CD 포함 여부)부터 확정한다.
