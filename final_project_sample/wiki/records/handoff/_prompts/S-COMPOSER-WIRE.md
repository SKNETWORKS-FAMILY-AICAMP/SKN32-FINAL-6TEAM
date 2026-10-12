# 구현 지시 — Composer UI 를 모듈 구현으로 등록 (배선 누락)

## 0. 결함

`composer_ui.enabled: true` 로 바꾸고 기동하면 **앱이 죽는다**:

```
app.composition.CompositionError: enabled module has no implementation: composer_ui
  app/composition.py:58 _validate_modules
  app/composition.py:168 build_controller
```

★**검증기는 옳게 동작했다.** "enabled 인데 구현 없음" 을 정확히 잡았다.
문제는 **Composer 화면이 실제로 구현됐는데 모듈 구현으로 등록되지 않은 것**이다.

원인: 직전 지시(`S-COMPOSER.md`)가 `app/composition.py` 를 **금지 범위**로 뒀는데
모듈 등록이 거기서 일어난다. **경계의 배선을 아무에게도 주지 않았다.**
(같은 유형: `wiki/records/evidence/DoD-09_인라인분류_전건실행.md` — 분류기 미연결)

현재 기준선: **151 passed, 0 failed, skipped 0** (`composer_ui: false` 기본 상태).

## 1. 소유 범위

```
app/composition.py            ← 모듈 구현 등록
app/presentation/ui/**        ← 필요하면 mount 함수 정리
tests/**
wiki/records/reports/ , wiki/records/history/
```
★금지: `app/core/**`, `app/domain/**`, `app/modules/**`, `app/application/**`,
`app/infrastructure/**`, `app/presentation/api/**`, `config/project.yaml`,
`config/guardrails.yaml`, `eval/**`, `knowledge/**`, `scripts/**`,
`wiki/records/handoff/**`, `wiki/records/evidence/**`.

## 2. 고칠 것

`composition.py` 의 모듈 구현 레지스트리(`_validate_modules` 가 참조하는 것)에
**`composer_ui` 를 등록**한다. `ops_ui` 가 어떻게 등록돼 있는지 보고 같은 방식으로 하라.

- `enabled: true` → Composer 라우터가 mount 된다
- `enabled: false` → mount 되지 않는다 (**현재 404 동작 유지**)
- ★`ops_ui` 와 `composer_ui` 는 **독립적**이다. 하나만 켜도 동작해야 한다

## 3. 테스트

1. ★`composer_ui: false`(기본) → `/ui/composer` **404**, 앱은 정상 기동 (현재 동작 유지)
2. ★`composer_ui: true` → **앱이 죽지 않고** `/ui/composer` **200**
3. ★`ops_ui: false` + `composer_ui: true` → `/ui/cases` 404, `/ui/composer` 200
4. 기존 151건이 그대로 통과

★테스트는 **임시 선언 파일**을 쓰고 실제 `config/project.yaml` 을 **훼손하지 마라**.
(직전 작업에서 이미 그 방식을 썼다 — 참고하라)

★`pytest.skip` 금지. 실제 LLM·네트워크 호출 금지.

## 4. 완료 조건

```powershell
python -m pytest tests -q
```
기대: **151건 이상, 0 failed, skipped 0**.

그리고 ★**실제로 켜서 띄워라**:
```powershell
copy config\project.yaml config\project.yaml.tmpbak
python -c "import pathlib;p=pathlib.Path('config/project.yaml');t=p.read_text(encoding='utf-8').replace('composer_ui: { enabled: false }','composer_ui: { enabled: true }');p.write_text(t,encoding='utf-8')"
Start-Process -NoNewWindow python -ArgumentList "-m","uvicorn","app.presentation.api.app:app","--port","8033"
Start-Sleep 8
curl.exe -s -o NUL -w "composer=%{http_code}\n" http://127.0.0.1:8033/ui/composer
```
기대: `composer=200`.
★확인 후 **서버를 종료하고 `config/project.yaml` 을 원복**하라
(`copy config\project.yaml.tmpbak config\project.yaml` 후 tmpbak 삭제).
★원복했는지 리포트에 적어라.

## 5. 리포트

`wiki/records/reports/2026-08-14_S-COMPOSER-WIRE_리포트.md` — 등록 방식,
`ops_ui` 와 어떻게 다르게/같게 했는지, §4 출력 원문, `project.yaml` 원복 확인.

## 6. 하지 말 것
- ❌ `composer_ui: false` 인데 라우트가 살아 있기
- ❌ `ops_ui` 와 `composer_ui` 를 하나로 묶기
- ❌ 검증기를 느슨하게 해서 통과시키기 (등록이 정답이다)
- ❌ 실제 `config/project.yaml` 훼손
- ❌ 소유 범위 밖 수정
- ❌ 띄워보지 않고 "완료"
