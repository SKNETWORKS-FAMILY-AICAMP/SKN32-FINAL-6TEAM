# 구현 지시 — 제품 introspection 계약 (런타임 결합 제거)

## 0. 왜 이걸 먼저 하나

결정이 바뀌었다. **(B) 같은 저장소 패키지 분리 → (C) 별도 대시보드 프로그램.**

이유는 확장성이다. (B) 는 프로젝트마다 콘솔 사본을 갖게 되고,
수십·수백 프로젝트가 되면 **사본이 각자 드리프트**한다. 릴리스본이 보수하러 돌아올 때마다
어느 버전 콘솔을 붙일지 맞춰야 한다. 그건 복사-붙여넣기 운영이다.

가야 할 모델은 **control plane / data plane** 이다 —
콘솔을 각 인스턴스에 심는 게 아니라, **콘솔 하나가 여러 인스턴스를 가리킨다.**

★그런데 지금은 그게 불가능하다:

```python
# /ui/admin 이 하는 일
registry = composition.build_registry()      # ← 대상 프로세스 안에서 파이썬을 실행한다
executor = LocalTeamExecutor(registry)
llm = OpenAITeamLLM()
```

**별도 프로그램은 남의 프로세스에서 이걸 못 부른다.** 이 런타임 결합을 먼저 끊어야
분리가 껍데기가 되지 않는다.

## 1. ★직전 작업에서 발견된 결함 (같이 고쳐라)

지난 발주(`S-CONSOLE-PACKAGE.md`) 결과를 검증했더니 두 가지가 틀렸다.

### 1-1. 분리가 껍데기였다

```
app/console/console.py            4줄   ← from app.presentation.ui.console import *
app/presentation/ui/console.py  390줄   ← 진짜 코드. 제품 패키지에 그대로 포함된다
```

`pyproject.toml` 이 `app.console*` 만 제외하는데, **실제 코드는 `app.presentation.ui` 에 있고
그 패키지는 제품에 포함된다.** 이름만 옮기고 코드는 안 옮겼다.

### 1-2. 빌드 테스트가 항상 참이었다

`tests/console/test_package_boundary.py`:

```python
assert "app.console" in "\n".join(Path("app/console").glob("*.py").__str__() for _ in [0]) \
       or Path("app/console").is_dir()
```

앞 항은 제너레이터 객체를 문자열로 만들어 **항상 거짓**, 뒤 항은 **항상 참**.
폴더가 있기만 하면 통과한다 — **패키징이 어떻게 깨져도 못 잡는다.**

★이 저장소에서 반복된 유형이다: **검사하는 척하는 검사.**

## 2. 소유 범위

```
app/introspection/**            ← ★새로 만든다 (제품의 read-only 자기소개)
app/console/**                  ← 실제 코드를 여기로 **진짜** 옮긴다
app/presentation/ui/__init__.py ← mount 배선
pyproject.toml
tests/console/** tests/contracts/** tests/architecture/**
wiki/records/handoff/12_*.md , wiki/records/reports/
```
★금지: `app/core/**`, `app/domain/**`, `app/application/**`, `app/infrastructure/**`,
`app/presentation/api/**`, `app/presentation/ui/routes.py`(고객사 화면), `app/modules/**`,
`config/**`, `eval/**`(읽기만), `knowledge/**`, `scripts/**`, `wiki/records/evidence/**`(읽기만).

## 3. 만들 것

### 3-1. `app/introspection/` — 제품이 자기 상태를 **데이터로** 낸다

제품에 남는 **아주 작은** read-only 표면이다. 콘솔 전체와 비교가 안 되게 작아야 한다.

내야 하는 것 (지금 `/ui/admin` 이 런타임 호출로 얻는 것과 같은 정보):
- 구성 revision, 모듈 on/off, Port 선택
- Team manifest 요약 (team_id·display_name·capabilities·allowed_tools·active·revision)
- 조립된 Port 구현 이름 (`LocalTeamExecutor` 등)
- guardrails 수치
- ★**API key 원문 금지.** 지금처럼 `sk-****`

★**계약에 version 을 박아라.** `{"contract_version": "1.0", ...}`.
버전이 없으면 대시보드가 무엇을 기대해야 할지 모른다.

### 3-2. 콘솔이 그것을 **소비**한다

`/ui/admin` 이 `composition.build_registry()` 를 직접 부르지 않고
introspection 이 낸 **데이터**를 읽게 바꾼다.

★같은 프로세스에서는 함수로 직접 얻어도 된다. 중요한 것은
**콘솔이 조립 절차가 아니라 데이터 형식에 의존**하게 만드는 것이다 —
그래야 나중에 그 데이터를 파일·HTTP 어디서 가져와도 콘솔이 안 바뀐다.

### 3-3. 코드를 **진짜** 옮긴다

`app/presentation/ui/{console,composer,theme}.py` 의 실제 내용을 `app/console/` 로 옮긴다.
고객사 화면(`routes.py`)이 쓰는 theme 요소가 있으면 **공용 부분만** 제품에 남기고
콘솔 전용 조각을 분리하라. 재수출 shim 으로 때우지 마라.

### 3-4. 설치 대상 둘

- 제품 — `app.console` **없이** 설치된다
- 콘솔 — `app.console` 을 **담는** 대상이 존재한다

★지난번엔 콘솔을 담는 대상이 아예 없어서 **붙일 방법이 없었다.** 둘 다 있어야 한다.

## 4. 완료 조건 — ★출력으로 증명하라

```powershell
python -m pytest tests -q
```
**317건 이상, 0 failed, skipped 0.**

그리고 아래를 **실행해 출력을 리포트에 붙여라.** 단언문만 쓰지 마라.

```powershell
# (1) 제품 대상에 콘솔 코드가 없다 / 콘솔 대상엔 있다
python -c "from setuptools import find_packages; import tomllib,pathlib; f=tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['tool']['setuptools']['packages']['find']; p=find_packages(where='.',include=f['include'],exclude=f['exclude']); print('제품:', sorted(x for x in p if 'console' in x)); print('전체 app 패키지:', len(p))"

# (2) 콘솔 없이 제품이 뜬다
python -m uvicorn app.presentation.api.app:app --port 8057
curl.exe -s -o NUL -w "ops=%{http_code}\n" http://127.0.0.1:8057/ops/cases
```

★**negative fixture 가 실제로 실패하는 것을 보여라.**
계약 필드를 하나 지운 fixture 로 테스트를 돌려 **빨간 것을 캡처**해서 리포트에 붙여라.
"negative 테스트를 만들었다" 는 말만으로는 안 된다 — 이번에 항상-참 단언이 나왔다.

## 5. 리포트

`wiki/records/reports/2026-08-17_S-INTROSPECT_리포트.md`
`wiki/records/handoff/12_introspection_계약.md` — 계약 필드표와 version 규칙

## 6. 하지 말 것
- ❌ 재수출 shim 으로 "옮겼다" 고 하기
- ❌ 항상 참인 단언
- ❌ 콘솔을 담는 설치 대상 없이 "분리 완료"
- ❌ 제품에 콘솔 로직을 남기기
- ❌ API key 원문 노출
- ❌ 별도 저장소 만들기 (그건 다음 단계다)
- ❌ 띄워보지 않고 "완료"
