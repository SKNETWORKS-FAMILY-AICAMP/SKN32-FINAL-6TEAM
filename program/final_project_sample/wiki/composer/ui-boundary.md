---
type: concept
title: Composer UI 패키지의 경계
description: UI가 넘지 말아야 할 구현 경계와 이를 검사하는 장치를 설명한다.
status: draft
tags: [architecture, contract, testing, security]
---

# Composer UI 패키지의 경계

UI는 대상의 검증 모델, 서버 구현, Python 구현 경로를 소유하거나 복제하지 않는다. `[실측]` UI 클라이언트는 JSON API 계약만 사용하고, 선언 검증과 권한 판정은 Composer 서버가 수행하도록 경계가 설정되어 있다. `tests/architecture/test_composer_ui_package_boundary.py:1-9`, `tests/e2e/test_composer_ui_client_contract.py:1-9`

## 넘으면 안 되는 선

`[실측]` `acop_composer_ui` 소스에는 다음 import 문자열이 들어오면 안 된다. `tests/architecture/test_composer_ui_package_boundary.py:22-46`

- `acop_basement`
- `acop_composer.`
- `app.`
- `fastapi`
- `pydantic`
- `yaml`

이 제한은 UI 프로세스가 대상 Core, Composer 서버, 제품 조립부, 서버 프레임워크와 선언 모델 구현을 끌어오는 것을 막는다. `[실측]` 검사 코드는 UI 패키지 아래의 모든 `*.py` 파일에서 `import` 또는 `from`으로 시작하는 줄을 확인한다. `tests/architecture/test_composer_ui_package_boundary.py:19-27`, `tests/architecture/test_composer_ui_package_boundary.py:36-46`

`[실측]` UI 코드에는 `ProjectConfig`, `TeamManifest`, `ContextPack` 식별자가 나타나면 안 된다. 주석과 삼중 큰따옴표 docstring은 검사 대상에서 제거한 뒤 실제 코드만 검사한다. `tests/architecture/test_composer_ui_package_boundary.py:49-58`

`[실측]` UI 패키지의 `project.dependencies`는 빈 목록이어야 한다. 또한 제품 루트의 패키지 탐색 설정은 `packages`로 시작하는 제외 패턴을 가져야 한다. 즉 UI 클라이언트는 표준 라이브러리만 사용하는 별도 배포 단위로 유지되는 것이 검사 계약이다. `tests/architecture/test_composer_ui_package_boundary.py:61-75`

## UI가 대신 사용하는 계약

`[실측]` UI는 구현 Python 경로 대신 서버 카탈로그가 제공하는 `implementation_id`를 사용한다. ID와 Python 경로의 매핑은 Composer 서버의 `IMPLEMENTATION_IDS`에만 있다. `acop_composer/catalog.py:22-27`, `acop_composer/catalog.py:52-57`

`[실측]` 카탈로그 응답은 `implementation_id`, 종류, 표시 이름, 설명, 입력 스키마, 재시작 필요 여부를 제공하지만 Python 경로를 포함하지 않는다. `acop_composer/catalog.py:68-105`

`[실측]` 카탈로그 E2E 검사는 응답에 선언형 Team과 선언된 모듈 ID가 포함되고 `app.modules` Python 경로는 노출되지 않도록 요구한다. `tests/e2e/test_composer_catalog_changes.py:74-91`

`[실측]` UI가 인스턴스를 변경할 때는 전체 선언 구조를 재구성하지 않고 작업 종류, 자원 종류, 인스턴스 ID와 필요한 입력값을 `/composer/changes`에 보낸다. 서버가 현재 선언을 읽어 대상 하나만 바꾼 후보를 만든다. `acop_composer/api.py:143-160`, `acop_composer/api.py:259-314`

`[실측]` 토글은 대상 종류, 대상 ID, 활성 상태, 기준 revision과 사유만 받는다. 서버가 이를 `enable` 또는 `disable` 변경으로 변환한다. `acop_composer/api.py:164-179`, `acop_composer/api.py:202-215`

## 검증 책임이 서버에 남는 방식

`[실측]` UI 클라이언트와 실제 FastAPI 앱을 직접 연결하는 E2E 검사가 경로, payload, scope와 상태 코드의 일치를 확인한다. 네트워크 대신 주입된 transport가 `TestClient`를 호출한다. `tests/e2e/test_composer_ui_client_contract.py:1-9`, `tests/e2e/test_composer_ui_client_contract.py:48-68`

`[실측]` 계약 검사는 카탈로그 조회, 토글, 선언형 Team 생성, dry-run, revision 충돌을 실제 서버와 왕복한다. `tests/e2e/test_composer_ui_client_contract.py:71-136`

`[실측]` 읽기 전용 선언형 Team에 쓰기 도구를 넣는 요청도 UI 클라이언트가 자체 판정하지 않는다. 요청을 그대로 보낸 뒤 서버가 422로 거부해야 한다. `tests/e2e/test_composer_ui_client_contract.py:139-156`

`[실측]` 같은 권한 상승 요청을 Composer API에서 직접 보내도 422와 읽기 전용 오류가 나야 한다는 검사가 있다. `tests/e2e/test_composer_catalog_changes.py:306-320`

`[실측]` 중앙 방식에서는 UI 클라이언트가 deployment ID를 헤더로 전달한다. 대상 없이 중앙 서비스에 연결하면 400 `deployment_required`를 받아야 한다. `tests/e2e/test_composer_ui_client_contract.py:175-236`

## 경계를 막는 검사의 범위

`[실측]` 소스가 하나도 없을 때 경계 검사가 공허하게 통과하지 않도록, 검사 대상 `*.py` 파일이 최소 하나 존재하는지도 확인한다. `tests/architecture/test_composer_ui_package_boundary.py:26-33`

`[실측]` import 검사는 `import` 또는 `from`으로 시작하는 줄과 금지 문자열의 포함 여부를 검사한다. 동적 import나 다른 방식으로 구성한 모듈 이름을 탐지하는 로직은 없다. `tests/architecture/test_composer_ui_package_boundary.py:36-46`

`[실측]` 모델 복제 검사는 세 식별자 이름만 탐지한다. 같은 구조를 다른 이름으로 다시 구현했는지를 구조적으로 비교하지는 않는다. `tests/architecture/test_composer_ui_package_boundary.py:49-58`

`[실측]` 배포 분리 검사는 제품 루트 제외 목록에 `packages`로 시작하는 패턴이 하나 이상 있는지만 확인한다. UI 패키지의 실제 배포 산출물을 검사하는 코드는 이 테스트에 없다. `tests/architecture/test_composer_ui_package_boundary.py:69-75`

`[미확보]` 허용된 경계·E2E 테스트의 현재 실행 성공 여부와 동적 import 같은 우회가 실제 UI 소스에 존재하는지는 확인하지 않았다.

## ★ [2026-09-03] pip 제공 구조 — 권고 3개 중 2개가 됐다

`[실측]` `program/research/_컴포저_UI배포구조_점검_2026-08-29.md` 에서 이관. **2026-09-03 에 코드로 확인했다.**

| 권고 | 지금 |
|---|---|
| UI 클라이언트 패키지를 만든다 | **됨** — `packages/acop_composer_ui/` |
| 배포 메타데이터를 분리한다 | **됨** — 별도 `pyproject.toml`, `dependencies = []` |
| **wheel 경계 테스트를 붙인다** | **안 됨** |

### 의존성이 비어 있는 게 계약이다

`[실측]` `packages/acop_composer_ui/pyproject.toml:10-12` 가 이유를 적어 뒀다.

> ★의존성이 비어 있는 것이 이 패키지의 계약이다. **fastapi·pydantic·`acop_basement` 를 끌어오면 UI 프로세스에 대상의 검증 모델이 들어온다.**

```toml
dependencies = []
```

**테스트가 이걸 강제한다** — `test_declares_no_dependencies`.

### 넣는 것과 안 넣는 것

| 넣는다 | 넣지 않는다 |
|---|---|
| JWT 발급 요청 · HTTP 전송 · 오류 정규화 | **`ProjectConfig`·`TeamManifest` 등 Core 모델** |
| 계약 버전 협상 | **선언 유효성 판정** |
| 엔드포인트 래퍼 | capability 충돌 검사 · 권한 판정 |

> **판정 로직을 넣는 순간 스키마 결합의 재현이다.**
>
> **UI 는 서버가 준 JSON Schema 로 폼을 그리고, 유효성은 서버가 판정한다.**

### 아직 안 된 것 — wheel 경계 테스트

`[실측]` 지금 테스트 5개는 **소스를 본다.**

```
금지 import 없음 · Core 모델 이름 없음
dependencies 비어 있음 · 배포에서 제외됨
```

**권고는 다른 것이었다.**

> `acop_composer_ui` **빌드 산출물**에 `acop_basement`·`app` 파일이 **0개인지 실제로 검사한다.**
>
> import 검사가 아니라 **빌드 산출물 파일 목록 검사**다.

`[미확보]` **`packages/acop_composer_ui/build/` 가 존재하는데 그 안을 검사하는 테스트는 없다.**

**소스가 깨끗해도 빌드 설정이 잘못되면 파일이 딸려 들어간다.** 그건 지금 안 잡힌다. → [../quality/invariants.md](../quality/invariants.md)

## 실제로 눌러 보다 찾은 결함 3건 (2026-08-28)

`[실측]` `program/research/_일일작업_2026-08-28.md` §3. 운영 콘솔(`final_project_ui`)에서 직접 눌러 찾았다 — **백엔드 테스트만으로는 안 나왔을 것들이다.** 위 "계약 검사는 실제 서버와 왕복한다"가 그 뒤에 생긴 이유이기도 하다.

| 결함 | 증상 | 원인 |
|---|---|---|
| 적용 사유 누락 | 화면의 적용 버튼이 **항상** 422 | 대상이 사유를 필수로 요구하는데 화면이 안 보냈다. 사유는 감사 기록의 근거라 뺄 수 없다 |
| 계약 버전 기본값 | 실제 대상과 값이 안 맞았다 | 기본값이 `v1`로 박혀 있었다. 실연결로 확인하니 `1.0` |
| 토글 상태 형태 | 어떤 항목은 토글이 안 보였다 | 서버가 상태를 **세 가지 모양**으로 돌려주는데 화면이 한 가지만 알았다 |

셋 다 "서버는 맞고 화면이 서버를 잘못 알고 있던" 종류다. 계약을 문서로만 맞추면 이 자리가 남는다.

## 관계

- UI 요청이 공유하는 실제 저장 경로는 [write-channel.md](write-channel.md)를 참조한다.
- UI 요청을 읽기·검증·쓰기로 나누는 권한 판정은 [auth-scope.md](auth-scope.md)를 참조한다.
