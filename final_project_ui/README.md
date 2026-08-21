# final_project_ui

여러 프로젝트를 가리키는 읽기 전용 개발 콘솔입니다. 대상 프로젝트의 코드를 가져오거나 실행하지 않습니다. `config/project.yaml`, `docs/evidence/`, `eval/reports/`, introspection HTTP 응답, PostgreSQL DB를 데이터로만 읽어 대상의 상태를 보여줍니다.

## 실행

```powershell
python -m console.web
```

포트는 `PORT` 환경변수로 지정할 수 있으며, 기본값은 `8060`입니다.

## 프로젝트 연결

- `/`에서 `root` 쿼리로 부모 폴더 경로를 주면 형제 프로젝트를 자동 탐지합니다. `config/project.yaml`의 존재 여부로 프로젝트를 판별합니다.
- `/project?path=<프로젝트 경로>`로 특정 프로젝트를 직접 엽니다.

## 라이브 연결

다음 환경변수는 모두 선택 사항입니다. 설정하지 않으면 콘솔은 연결하지 않음으로 표시합니다.

- `CONSOLE_DATABASE_URL`: 대상 PostgreSQL 연결 URL입니다. `postgresql://` 형식만 지원합니다.
- `CONSOLE_INTROSPECTION_URL`: 대상의 `GET /introspection` URL입니다.
- `CONSOLE_INTROSPECTION_TOKEN`: introspection 엔드포인트가 scope 인증을 요구할 때 사용하는 토큰입니다. 토큰 없이 연결하면 인증 실패로 표시됩니다.
- `CONSOLE_CONTRACT_VERSIONS`: 콘솔이 아는 introspection 계약 버전의 콤마 구분 목록입니다.
- `CONSOLE_COMPOSER_URL`: 대상의 Composer 쓰기 채널(`/composer/*`) base URL입니다.
- `CONSOLE_COMPOSER_ISSUER_SECRET`: Composer 요청마다 동작별 최소 scope로 단명 JWT를
  발급받을 때 쓰는 issuer secret입니다(`/auth/token`).

토큰과 DB 비밀번호 같은 비밀값은 파일에 저장하지 않으며, 매번 환경변수로 전달합니다.

## 테스트

```powershell
python -m pytest tests -q
```
CI를 만들 경우에는 GitHub Actions repository secrets에 `CONSOLE_INTROSPECTION_TOKEN`과 `CONSOLE_COMPOSER_ISSUER_SECRET`을 secret으로 등록하고, workflow의 `env:`에서 `secrets.CONSOLE_INTROSPECTION_TOKEN`과 `secrets.CONSOLE_COMPOSER_ISSUER_SECRET`으로 주입합니다. 지금은 수동 실행으로 전달하고 CI 파일은 없으며, 나중에 CI를 붙일 때 이 방식을 사용합니다.
