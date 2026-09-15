# S-DOCKER-STAGE1 — 로컬 컨테이너화 1단계 (AWS 는 이번 스코프 아님)

## 배경 (읽지 않아도 되는 맥락)

배포에 Docker·AWS 를 쓰기로 한 결정이 있었는데 이 저장소 계획에 반영이 안 돼
있던 걸 뒤늦게 등록했다 — `wiki/records/plans/2026-08-17_Docker_AWS_배포_모듈화_계획.md`.
그 문서 §2 에 AWS 컴퓨트·매니지드 서비스 교체·비밀 관리·CI/CD 는 **아직 사용자
확답 전**이라 이번 스코프에서 뺀다고 적어뒀다. 이번엔 그 문서 §3 의 **1단계
(최소 범위)만** 한다.

★이 저장소(`final_project_sample`)는 "basement" — 어디로든 이식 가능한
기반이어야 한다. 그래서 컨테이너화가 **애플리케이션 코드에 어떤 가정도
강요하면 안 된다** — 이미 `app/core/settings.py` 가 전부 환경변수로 설정을
읽으므로(★하드코딩 금지, RULE.md §3.1) 그 관례를 그대로 쓰면 된다.

## 반드시 읽을 파일 (이 목록 밖은 읽지 않아도 된다)

1. `.env.example` — 필요한 환경변수 전체 목록
2. `requirements.txt`
3. `app/presentation/api/app.py` — ASGI 진입점(`app = create_app()`), 포트는 없음
4. `.claude/launch.json` — 로컬 개발 서버가 `uvicorn app.presentation.api.app:app --port 8071`
   로 뜨는 걸 참고만 한다 (compose 도 같은 진입점을 쓰되 포트는 환경변수로 바꿀 수 있게)
5. `config/guardrails.yaml` 의 맨 위 20줄만 — `rag.embedding_dim: 1536` 확인용
   (Postgres 이미지가 pgvector 확장을 지원해야 한다는 근거)
6. `wiki/records/plans/2026-08-17_Docker_AWS_배포_모듈화_계획.md`

## 만들 것 (딱 이 세 가지, 그 이상 만들지 않는다)

### 1. `Dockerfile` (저장소 루트)
- `python:3.12-slim` 베이스, `requirements.txt` 설치, `app/` 복사
- `CMD` 는 `uvicorn app.presentation.api.app:app --host 0.0.0.0 --port 8000`
  (포트는 하드코딩해도 된다 — 컨테이너 **내부** 포트는 관례상 고정하고,
  **호스트에 매핑하는 포트**를 compose 에서 환경변수로 뺀다)
- 비밀 값(`ACOP_OPENAI_API_KEY`, `ACOP_SECRET_KEY` 등)을 이미지에 **절대 굽지 않는다**
  — `.env.example` 에 있는 키는 전부 런타임에 주입한다

### 2. `docker/compose.yml`
- `app` 서비스: 위 Dockerfile 빌드, `.env` 파일에서 환경변수 로드
- `db` 서비스: pgvector 확장이 포함된 Postgres 이미지(`pgvector/pgvector:pg16` 계열),
  `vector`·`pgcrypto` extension 을 초기화 스크립트로 켠다
- ★**로컬 conda env `pgv` 경로를 대체하지 않는다.** 이건 병행 옵션이다 —
  개발자가 원하면 conda 로, 원하면 이 compose 로 뜨는 것뿐이다. 기존 문서
  (`wiki/records/manuals/`, `CLAUDE.md`) 의 conda 안내를 지우거나 바꾸지 않는다
- 호스트 포트는 `.env` 의 변수로 뺀다 (하드코딩 금지, RULE.md §3.1)

### 3. `wiki/records/handoff/14_배포_계약.md`
`wiki/records/handoff/12_introspection_계약.md` 와 같은 형식으로 짧게 쓴다:
- 배포 타깃(로컬 프로세스 / 컨테이너 / 향후 AWS)이 애플리케이션 코드에 강요하는
  가정이 없다는 계약을 명시 — "설정은 환경변수로만 주입한다. 특정 클라우드
  SDK 를 `app/**` 코드에 직접 import 하지 않는다" 등
- 지금 컨테이너 이미지가 무엇을 전제하는지(포트·환경변수 목록)
- ★"AWS 컴퓨트·매니지드 서비스 교체·비밀 관리·CI/CD 는 아직 미정 —
  `wiki/records/plans/2026-08-17_Docker_AWS_배포_모듈화_계획.md` §2 확답 후 2단계"
  라고 명시한다 — 이 문서가 이미 다 정해진 것처럼 읽히면 안 된다

## 하지 않을 것 (범위 밖 — 손대면 반려한다)

- AWS IaC(Terraform/CDK/CloudFormation), ECS/Fargate/App Runner 설정
- Secrets Manager/Parameter Store 연동
- CI/CD 파이프라인(GitHub Actions 등)
- `app/**` 코드 수정 — 이미 환경변수로 설정을 읽으므로 코드는 안 바꿔도 된다.
  만약 컨테이너화하다가 코드를 고쳐야 할 게 생기면 **고치지 말고 리포트에
  이유를 적어라** — 범위 밖 판단은 Claude 가 한다

## 검증에 관해 — ★정직하게 적을 것

이 개발 환경에는 **Docker 가 설치돼 있지 않다** (`docker --version` → command not found,
2026-08-17 확인). 그러니 `docker build`/`docker compose up` 을 **실행할 수 없다.**
"실행해서 확인했다"고 쓰지 마라 — 실행 못 했으면 못 했다고 적는다. 대신:

- Dockerfile·compose.yml 문법이 올바른지 (들여쓰기, YAML 파싱 가능 여부)만 확인한다
- `python -m pytest -q` 로 기존 스위트가 그대로 초록인지 확인한다 (이 작업은
  애플리케이션 코드를 안 건드리므로 실패하면 그 자체가 범위 위반 신호다)
- 리포트에 "Docker 미설치로 build/run 미검증 — 사용자가 Docker 있는 환경에서
  직접 검증 필요"라고 명시한다

## 완료 기준

```powershell
python -m pytest -q   # 전체 스위트 그대로 초록 (2026-08-17 기준 321 passed)
```

`wiki/records/reports/` 에 짧은 리포트를 남긴다: 만든 파일 목록, 문법 검증 방법과 결과,
"Docker 미검증" 명시, 다음 사람이 실제로 `docker compose up` 을 돌려볼 때 확인할
체크리스트.
