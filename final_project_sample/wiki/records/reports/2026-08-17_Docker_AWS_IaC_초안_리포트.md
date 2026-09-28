# Docker·AWS IaC 초안 작업 리포트

## 상태

이건 초안이고 사용자 확답 후 바뀔 수 있다. 확정된 아키텍처가 아니라 논의용 초안이다.

## 만든 파일

- `infra/aws/README.md`
- `infra/aws/main.tf`
- `infra/aws/variables.tf`
- `infra/aws/outputs.tf`
- `.github/workflows/deploy.yml`

## 이 문서에서만 둔 가정

- 컴퓨트: ECS Fargate
- DB: RDS for PostgreSQL + `pgvector` 확장(RDS PostgreSQL 15.2+부터 지원)
- 비밀 관리: AWS Secrets Manager (`ACOP_OPENAI_API_KEY`, `ACOP_SECRET_KEY`, DB 접속정보)
- CI/CD: GitHub Actions — 이미지 빌드 → ECR push → ECS 서비스 업데이트
- 네트워크: 퍼블릭 서브넷의 ALB → 프라이빗 서브넷의 Fargate 태스크

실제 AWS 계정 ID·리전·도메인 이름은 만들지 않았고, Terraform 변수와 GitHub Secrets 참조로 남겼다. `Dockerfile`의 Stage 1 이미지/포트/ASGI 진입점을 그대로 재사용했으며 `app/**`는 수정하지 않았다.

## 검증

- `python -m pytest -q`: `323 passed, 3 failed, 1 deselected`.
  실패 3건은 새 IaC와 무관한 RAG 통합 테스트가 `api.openai.com`에 연결하는 과정에서 환경 네트워크 권한 오류(`WinError 10013`)로 실패한 것이다. infra는 pytest 대상이 아니다.
- `terraform validate`: Terraform 미설치. 따라서 Terraform 구문 검증은 이 환경에서 실행하지 못했다.
- `terraform apply` 및 `terraform plan`: 실행하지 않았다. AWS 자격증명 없이 리소스를 만들거나 계획하지 않는 요청을 준수했다.

## 다음 확정 필요 사항

Fargate/EC2 등 컴퓨트, RDS와 `pgvector` 유지 여부, Secrets Manager/다른 비밀 저장소, GitHub Actions와 승인 정책, 실제 리전/AZ·도메인/TLS·state 백엔드, RDS 백업·암호화·삭제 보호를 사용자가 확정하면 해당 초안만 갱신한다.
