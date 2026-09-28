# S-DOCKER-STAGE2-AWS-DRAFT — AWS IaC 초안 (가정 명시, 확정 아님)

## 배경 (읽지 않아도 되는 맥락)

`wiki/records/plans/2026-08-17_Docker_AWS_배포_모듈화_계획.md` §2 가 확답을 요구했던
5가지(컨테이너 범위·AWS 컴퓨트·매니지드 서비스 교체·비밀 관리·CI/CD)를
사용자가 아직 구체적으로 답하지 않았다. 계속 기다리지 말고 **가장 흔한 선택을
가정으로 명시해서** 초안을 만들고, 사용자가 나중에 가정을 뒤집으면 그 부분만
고치는 방식으로 간다. ★**이 산출물은 "확정된 아키텍처"가 아니라 "논의용 초안"
이다.** 그렇게 리포트에 못박는다.

## 가정 (이 문서 안에서만 유효 — 사용자가 다음에 확정하면 바뀔 수 있다)

- 컴퓨트: **ECS Fargate** (서버 관리 없음, 컨테이너 그대로 배포 — 가장 흔한 시작점)
- DB: **RDS for PostgreSQL** + `pgvector` 확장(RDS PostgreSQL 15.2+ 부터 지원)
- 비밀 관리: **AWS Secrets Manager** (`ACOP_OPENAI_API_KEY`, `ACOP_SECRET_KEY`,
  DB 접속정보)
- CI/CD: **GitHub Actions** — 이미지 빌드 → ECR push → ECS 서비스 업데이트
- 네트워크: 퍼블릭 서브넷의 ALB → 프라이빗 서브넷의 Fargate 태스크 (가장 보편적인
  최소 구성. VPC peering·on-prem 연동 등은 다루지 않는다)

## 반드시 읽을 파일

1. `wiki/records/plans/2026-08-17_Docker_AWS_배포_모듈화_계획.md`
2. `wiki/records/handoff/14_배포_계약.md` — Stage 1 계약. 이 문서가 정한 "배포 타깃이
   코드에 가정을 강요하지 않는다"를 그대로 지킨다
3. `Dockerfile`, `docker/compose.yml` — Stage 1 산출물. 이미지 빌드 방식을 그대로 재사용
4. `.env.example` — 필요한 환경변수 전체 목록 (Secrets Manager 로 옮길 대상)

## 만들 것

`infra/aws/` 디렉터리 아래:

1. `infra/aws/README.md` — 위 "가정" 섹션을 그대로 옮겨 적고, **왜 초안 단계인지**,
   사용자가 다음에 확정해야 바뀔 수 있는 지점을 명시한다
2. `infra/aws/main.tf` (+ 필요하면 `variables.tf`, `outputs.tf`) — Terraform 로
   ECS Fargate 서비스 + RDS PostgreSQL + Secrets Manager + ECR 리포지토리의
   **최소 골격.** ★실제로 `terraform apply` 해서 리소스를 만들지 않는다 —
   여기서 만드는 건 코드일 뿐이다. AWS 자격증명도 없고 배포도 안 한다
3. `.github/workflows/deploy.yml` — 이미지 빌드 → ECR push → ECS 서비스 업데이트
   워크플로 골격. 실제 AWS 계정 정보(account id, region 등)는 GitHub Secrets 참조로
   플레이스홀더만 넣는다

## 하지 않을 것

- **`terraform apply`/`terraform plan`을 실제로 돌리지 않는다** — 계정도 없고
  돌려서도 안 된다. `terraform validate`(구문 검사)까지만, 그것도 Terraform 이
  이 환경에 없으면 안 돼도 된다 — 없으면 없다고 리포트에 적는다
- `app/**` 코드를 건드리지 않는다
- 위 "가정"을 **사실인 것처럼** 문서 밖에 적지 않는다 — `CLAUDE.md`, `wiki/records/handoff/14`
  같은 이미 확정된 문서를 이 가정으로 덮어쓰지 않는다. 전부 `infra/aws/` 안에만 둔다
- 실제 AWS 계정 ID·리전·도메인 이름 같은 값을 지어내지 않는다. 전부 변수/플레이스홀더로 둔다

## 완료 기준

```powershell
python -m pytest -q   # 전체 스위트 그대로 초록 (2026-08-17 기준 326 passed) — infra 는 pytest 대상 아님
```

`wiki/records/reports/`에 리포트: 만든 파일 목록, 가정 목록을 다시 한번 명시, "이건 초안이고
사용자 확답 후 바뀔 수 있다"는 문장을 그대로 포함, terraform validate 결과(돌릴 수
있었으면 원문, 없었으면 "Terraform 미설치"라고 명시).
