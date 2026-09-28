# AWS 배포 IaC 초안

> 이 문서는 **확정된 아키텍처가 아니라 논의용 초안**이다. 아래 선택은 사용자의 확답을 받기 전까지 이 디렉터리 안에서만 유효하다.

## 가정

- 컴퓨트: **ECS Fargate** (서버 관리 없음, 컨테이너 그대로 배포 — 가장 흔한 시작점)
- DB: **RDS for PostgreSQL** + `pgvector` 확장(RDS PostgreSQL 15.2+ 부터 지원)
- 비밀 관리: **AWS Secrets Manager** (`ACOP_OPENAI_API_KEY`, `ACOP_SECRET_KEY`, DB 접속정보)
- CI/CD: **GitHub Actions** — 이미지 빌드 → ECR push → ECS 서비스 업데이트
- 네트워크: 퍼블릭 서브넷의 ALB → 프라이빗 서브넷의 Fargate 태스크 (가장 보편적인 최소 구성. VPC peering·on-prem 연동 등은 다루지 않는다)

## 왜 초안인가

계획 문서 §2의 컨테이너 범위, AWS 컴퓨트, 매니지드 서비스 교체 범위, 비밀 관리, CI/CD에 대해 아직 사용자가 확정하지 않았다. 따라서 이 코드는 토론을 시작하기 위한 최소 골격이며, 실제 계정에 적용하기 전 보안·비용·가용성·운영 요구사항 검토가 필요하다.

다음 확정 결과에 따라 `infra/aws/`의 해당 부분만 바뀔 수 있다.

- Fargate 대신 EC2, App Runner 또는 다른 컴퓨트를 선택하는 경우
- RDS 대신 다른 DB/벡터 저장소를 선택하거나 `pgvector` 지원 범위를 바꾸는 경우
- Secrets Manager 대신 Parameter Store 등으로 비밀 관리를 바꾸는 경우
- GitHub Actions 대신 다른 CI/CD와 배포 승인 정책을 선택하는 경우
- ALB, 서브넷, NAT, 도메인/TLS, VPC 연결 요구사항을 구체화하는 경우

## Stage 1 계약 준수

`Dockerfile`의 `python:3.12-slim`, `app.presentation.api.app:app`, 컨테이너 포트 `8000`을 그대로 사용한다. 배포 타깃이 `app/**` 코드에 AWS SDK나 특정 AWS 서비스 import를 강요하지 않으며, 환경변수로만 설정을 주입한다. Compose의 로컬 `pgvector` 컨테이너는 개발용으로 유지하고, 이 초안에서만 RDS를 배포 대상으로 가정한다.

## 사용 전 주의

`terraform apply`를 실행하기 전에 백엔드(state), 실제 리전/AZ, IAM 권한, 비밀값, RDS 백업·암호화·삭제 보호, ALB TLS와 도메인을 별도로 결정해야 한다. 이 디렉터리는 리소스 생성 명령을 실행하지 않는다.
