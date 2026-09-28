# S-DOCKER-STAGE1 구현 리포트

## 변경 사항

- `Dockerfile`: Python 3.12 slim 기반 애플리케이션 이미지와 Uvicorn 실행 명령을 추가했다.
- `docker/compose.yml`: 앱과 `pgvector/pgvector:pg16` DB를 구성했다. 앱은 `.env`를
  런타임에 주입받고, DB는 `vector`·`pgcrypto`를 시작 시 활성화한다.
- `wiki/records/handoff/14_배포_계약.md`: 배포 타깃 독립성, 컨테이너 전제, 보류 중인 AWS 범위를 계약으로 명시했다.

`app/**`, 기존 conda 안내, AWS IaC·Secrets Manager·CI/CD는 수정하지 않았다.

## 검증

- Compose YAML 파싱: `python`의 YAML 파서로 `docker/compose.yml`을 파싱해 성공 확인.
- Dockerfile: 베이스 이미지, requirements 설치, `app/` 복사, ASGI CMD를 정적 확인.
- `python -m pytest -q`: `319 passed, 3 failed, 1 deselected`.
- Docker 미설치로 build/run 미검증 — 사용자가 Docker 있는 환경에서 직접 검증 필요.

pytest의 실패 3건은 기존 RAG 통합 테스트가 `api.openai.com` 임베딩을 호출하는
경로에서 실행 환경의 네트워크 권한 오류(`WinError 10013`)로 실패한 것이다.
이번 작업은 `app/**`를 수정하지 않았으므로 이 실패를 숨기거나 우회하지 않았다.

## 다음 사람이 확인할 체크리스트

1. `.env.example`을 `.env`로 복사하고 비밀 값을 채운다.
2. 필요하면 `.env`에 `ACOP_APP_PORT`, `ACOP_DB_PORT`를 지정한다.
3. `docker compose -f docker/compose.yml config`로 Compose 최종 설정을 확인한다.
4. `docker compose -f docker/compose.yml up --build`로 앱·DB를 기동한다.
5. `http://localhost:<ACOP_APP_PORT>/health`가 `{"status":"ok"}`를 반환하는지 확인한다.
6. DB에서 `vector`, `pgcrypto` 확장이 활성화됐는지 확인한다.
7. 실제 OpenAI 호출이 필요한 경로는 유효한 `ACOP_OPENAI_API_KEY`로 별도 확인한다.

## 테스트 결과

2026-08-17 실행 결과: `319 passed, 3 failed, 1 deselected`.
