# S-COMPOSER-DEPLOY-STAGE2-LOCAL 리포트

실행일: 2026-08-19

## 결과

로컬 Docker 배포 경계 분리를 구현했다. customer-runtime과
composer-control을 이제 각각 별도 이미지로 빌드하고, 별도 Compose
서비스로 띄울 수 있다.

## 설계 선택

Dockerfile 두 개로 나누는 방식(이중 Dockerfile)을 선택했다:

- `Dockerfile` — 관리용 이미지. `acop_composer/`를 COPY하고
  `app.entrypoint:app`으로 기동한다.
- `Dockerfile.customer` — 고객용 이미지. `app/`·`acop_basement/`·
  `config/`만 COPY하고 `acop_composer/`는 COPY하지 않으며
  `acop_basement.presentation.api.app:app`으로 기동한다.

multi-stage build 대신 이 방식을 고른 이유: 고객 이미지가
`acop_composer/`를 담은 스테이지를 아예 상속하지 않는다는 게 기계적으로
명백해진다(어떤 COPY 줄에도 `acop_composer`가 없다). 기존 관리용
Dockerfile 경로도 그대로 유지되고, 나중에 공유 스테이지 내용이 실수로
넓어져 고객 이미지에 새어 들어갈 위험도 없다.

## 고친 파일

- `Dockerfile` — 관리용 이미지 계약을 명확히 함.
- `Dockerfile.customer`(신규) — Composer 없는 고객용 이미지.
- `docker/compose.yml` — `app-customer`(호스트 포트 8000)·
  `app-admin`(호스트 포트 8001) 두 서비스 추가, `db` 서비스 공유.
- `docs/handoff/14_배포_계약.md` — 이미지 물리 분리 사실과, 런타임
  reload가 여전히 미정의라는 한계를 함께 기록.
- `docs/reports/2026-08-19_S-COMPOSER-DEPLOY-STAGE2-LOCAL_리포트.md` —
  이 리포트.

`infra/aws/**`와 `docs/plans/2026-08-18_Composer_배포_경계_분리_계획.md`는
건드리지 않았다.

## 검증

- Docker build·`docker compose up`은 실행하지 않았다. 이 기계엔 Docker가
  설치돼 있지 않아 **이미지 빌드 자체는 검증하지 못했다.**
- Dockerfile 정적 확인 — 모든 `COPY` 소스 경로가 실제로 존재하고,
  `Dockerfile.customer`엔 `acop_composer/` COPY가 없으며, 두 이미지
  커맨드 모두 `--workers 1`을 쓴다는 것까지 확인.
- `docker/compose.yml`을 PyYAML로 파싱해 문법 통과.
- Windows 기본 temp 디렉터리 권한 거부 문제로
  `--basetemp=.pytest-tmp/stage2`를 줘서 전체 테스트를 실행 — 원 스트림
  결과는 `355 passed, 1 deselected` (Codex 실행 시점 기준).

★**Claude 검수(2026-08-19) 추가 사항** — 이 스트림과 동시에 진행된
버그헌팅 라운드9가 `acop_basement/presentation/api/app.py`의 실제 결함
(basement 단독 설치 시 `create_app()`이 controller·classifier를 둘 다
주입받아도 `app.composition` import를 요구하던 것)과
`setup.py`가 `pyproject.toml`의 패키징 include/exclude를 조용히
무시하고 `tests`/`examples`/`scripts`까지 wheel에 포함시키던 것을
발견해 Claude가 직접 수정했다(별도 커밋). 그 수정을 반영해 재실행한
결과는 `python -m pytest tests/architecture -q` 72 passed,
`python -m pytest -q --ignore=tests/integration/rag` 355 passed,
1 deselected — 이 스트림이 만든 Dockerfile/compose 변경과는 무관하게
전체 결과가 그대로 유지됨을 확인했다.

## 후속 경계

이번 변경은 로컬 Docker에서 이미지를 물리적으로 분리하는 것까지다.
Composer `apply` 성공 후 그 설정이 customer-runtime에 어떻게 반영
(reload)되는지는 정의하지 않았고, AWS 배포 분리도 주장하지 않는다.
둘 다 운영 경험을 바탕으로 결정해야 할 후속 과제로 남는다.
