# S-COMPOSER 구현 리포트

## 구현 범위

`app/presentation/ui/composer.py`에 서버 사이드 렌더링 Composer를 추가하고 `mount_ui()`에서 라우터를 등록했다.

- `composer_ui.enabled`가 false이면 `GET /ui/composer`와 저장 POST가 404를 반환한다.
- 모듈은 현재 `project.yaml`의 `modules` 키에서 읽는다.
- Port 선택지는 `PortConfig` 타입 힌트의 `Literal` 허용값에서 읽고, 현재 구현되지 않은 값은 선택지에서 제외했다.
- Team은 `team_id`, `implementation_ref`, `active`를 편집할 수 있으며 새 행은 `active=false`와 placeholder ref로 시작한다. 화면에는 “미구현 — 등록되지만 라우팅되지 않음”을 표시한다.
- 컴포넌트 9종은 토글 입력 없이 읽기 전용 설명으로 표시한다.
- API 키나 PII는 Composer에서 읽거나 표시하지 않는다.

## 검증과 저장

저장 POST는 입력을 임시 YAML에 작성한 뒤 `app.core.project_config.load_project_config()`를 호출한다. 따라서 기존 Pydantic 스키마, 중복 `team_id`, Port 검증, active Team의 implementation import 검증을 재구현하지 않는다. 오류가 있으면 원본과 백업을 변경하지 않고 화면에 오류를 표시한다.

검증 성공 시 순서는 다음과 같다.

1. `config/project.yaml` 원본을 `config/project.yaml.bak`으로 백업
2. 검증된 임시 선언을 원본 경로에 기록
3. 화면에 재기동 필요 메시지 표시

테스트는 `app.state.project_config_path`로 임시 선언을 주입하므로 실제 `config/project.yaml`을 수정하지 않는다.

## 테스트

추가한 `tests/e2e/test_composer_ui.py`는 다음을 검증한다.

- 기본 비활성 상태의 404
- 임시 활성 선언에서 두 Team 표시
- 잘못된 active `implementation_ref` 저장 거부
- 새 Team 기본 `active=false` 및 라우팅 제외 문구
- 컴포넌트 읽기 전용 표시
- 성공 저장과 `.bak` 생성

Composer 전용 실행 결과:

```text
4 passed, 1 warning
```

완료 조건 실행 결과 원문:

```text
148 passed, 3 failed, 1 deselected, 2 warnings in 21.90s
{'vector_rag': ModuleConfig(enabled=True), 'graph_store': ModuleConfig(enabled=True), 'a2a_executor': ModuleConfig(enabled=False), 'mcp': ModuleConfig(enabled=True), 'voc': ModuleConfig(enabled=True), 'ops_ui': ModuleConfig(enabled=True), 'composer_ui': ModuleConfig(enabled=False)}
```

실패한 3건은 기존 RAG 통합 테스트가 `api.openai.com` 임베딩을 호출하다가 실행 환경의 네트워크 차단으로 실패한 것이다. Composer 테스트는 네트워크와 실제 LLM을 호출하지 않는다.

## `project.yaml` 무결성

전체 테스트 전후 SHA-256:

```text
before: 6C777F29E45990C567A78990DDC34AFD91F40C7134D60D92AADEF84E5FD730EB
after:  6C777F29E45990C567A78990DDC34AFD91F40C7134D60D92AADEF84E5FD730EB
PROJECT_YAML_UNCHANGED=True
```

원본 선언은 그대로 유지되었고 테스트용 백업/임시 선언은 저장소의 실제 `config/`에 남지 않았다.
