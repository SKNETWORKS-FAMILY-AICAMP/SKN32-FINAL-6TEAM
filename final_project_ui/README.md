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

### Composer 화면이 비어 있다면

Composer 화면은 **대상에게 물어봐서** 그립니다 — 이 콘솔은 대상의 파이썬을
import하지 않고(`CLAUDE.md` §0.3), 쓰기는 대상이 자기 계약으로 검증한 뒤
실행합니다. 그래서 **대상 서버가 떠 있어야** 값이 채워집니다.

```powershell
# 1) 대상을 띄운다 (예: final_project_cs, 그 저장소의 실행 방법대로)
$env:ACOP_COMPOSER_JWT_SECRET="<대상 JWT 서명키>"
$env:ACOP_COMPOSER_ISSUER_SECRET="<대상 발급자 비밀키>"
python -m uvicorn app.presentation.api.app:app --port 8075

# 2) 콘솔을 그 대상에 연결해 띄운다
$env:CONSOLE_COMPOSER_URL="http://127.0.0.1:8075/composer"
$env:CONSOLE_COMPOSER_ISSUER_SECRET="<대상과 같은 발급자 비밀키>"
python -m console.web
```

`composer_url 이 프로필에 없음`은 결함이 아니라 **연결 정보가 없다는 뜻**입니다.
화면이 그 자리에서 무엇을 설정해야 하는지 함께 알려줍니다.

### Composer 쓰기는 이 화면의 폼으로만 됩니다 (CSRF)

`POST /composer`는 이 콘솔이 그린 폼의 CSRF 토큰을 요구하고, 다른 출처에서 온
요청은 거부합니다. 콘솔이 켜져 있는 동안 운영자가 악성 페이지를 열면 그 페이지가
`127.0.0.1`로 폼 POST를 보낼 수 있고(브라우저가 막지 않습니다), 응답은 못 읽어도
**대상 config 변경이라는 부작용은 일어나기** 때문입니다.

스크립트로 자동화하려면 이 콘솔이 아니라 **대상의 `/composer/*` API를 직접**
호출하세요 — 그게 원래 계약입니다.

## 테스트

```powershell
python -m pytest tests -q
```
CI를 만들 경우에는 GitHub Actions repository secrets에 `CONSOLE_INTROSPECTION_TOKEN`과 `CONSOLE_COMPOSER_ISSUER_SECRET`을 secret으로 등록하고, workflow의 `env:`에서 `secrets.CONSOLE_INTROSPECTION_TOKEN`과 `secrets.CONSOLE_COMPOSER_ISSUER_SECRET`으로 주입합니다. 지금은 수동 실행으로 전달하고 CI 파일은 없으며, 나중에 CI를 붙일 때 이 방식을 사용합니다.
