# S-COMPOSER-WIRE 구현 리포트

## 변경 내용

`app/composition.py`의 모듈 구현 레지스트리를 `_MODULE_IMPLEMENTATIONS`로 명시하고 `composer_ui`를 등록했다. 기존 검증기의 `composer_ui` 강제 거부 분기를 제거하여, 활성화된 Composer가 정상적인 구현 등록으로 검증되도록 했다.

`ops_ui`와 `composer_ui`는 레지스트리에서 별도 항목으로 유지했다. `app/presentation/ui/__init__.py`의 `mount_ui()`도 각 플래그를 독립적으로 확인한다.

- `ops_ui: true`이면 Operations UI 라우터만 mount
- `composer_ui: true`이면 Composer 라우터만 mount
- 각 모듈이 false이면 해당 라우터를 mount하지 않아 404 유지

## 테스트

추가한 검증:

- `composer_ui: true`에서 composition registry가 정상 조립됨
- `ops_ui: false` + `composer_ui: true`에서 `/ui/cases`는 404, `/ui/composer`는 200

대상 테스트 출력:

```text
21 passed, 1 warning in 1.51s
```

전체 실행 출력:

```text
150 passed, 3 failed, 1 deselected, 2 warnings in 23.48s
```

실패한 3건은 기존 RAG 통합 테스트가 `api.openai.com` 임베딩 호출을 시도했으나 이 실행 환경에서 네트워크가 차단되어 발생했다. Composer 변경과 무관하며, 지시대로 실제 LLM·네트워크 호출을 우회하거나 `pytest.skip`으로 숨기지 않았다.

## 실제 기동 검증

`config/project.yaml`을 백업한 뒤 `composer_ui: true`로 임시 변경하고 uvicorn을 실제 기동했다. 실행 출력 원문은 다음과 같다.

```text
INFO:     127.0.0.1:64121 - "GET /ui/composer HTTP/1.1" 200 OK
INFO:     127.0.0.1:64122 - "GET /ui/cases HTTP/1.1" 200 OK
composer=200
cases=200
server_returncode=1
INFO:     Started server process [31564]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8033 (Press CTRL+C to quit)
```

`cases=200`은 실기동에 사용한 기본 선언에서 `ops_ui: true`였기 때문이다. 독립 동작인 `ops_ui: false` 조합은 위 대상 e2e 테스트에서 `/ui/cases=404`, `/ui/composer=200`으로 검증했다.

검증 후 서버를 종료했으며, 포트 8033은 현재 free 상태다.

## project.yaml 원복

임시 백업 `config/project.yaml.tmpbak`에서 원복했고 백업 파일은 삭제했다.

```text
original/restored SHA-256: 6C777F29E45990C567A78990DDC34AFD91F40C7134D60D92AADEF84E5FD730EB
tmpbak_exists=False
```

따라서 실제 `config/project.yaml`은 원복 완료 상태다.
