# 개발 대시보드 분리 검토

## 결론

지금은 **(B) 같은 저장소 안에서 별도 패키지·설치 대상으로 분리**하는 것이 맞다.

별도 저장소(C)는 아직 이르다. 현재 콘솔은 제품의 내부 형식을 다섯 군데에서 직접 읽고, `/ui/admin`에서는 같은 composition root를 다시 호출한다. 이 상태에서 저장소만 나누면 결합은 없어지지 않고 변경·테스트·배포 조정 비용만 늘어난다. 반대로 B는 다음 두 요구를 동시에 만족시킨다.

- 제품 릴리스 artifact에는 콘솔 패키지를 넣지 않을 수 있다.
- 계약·스키마·fixture·경계 테스트를 제품 저장소의 한 변경으로 함께 검증할 수 있다.

즉, **소스가 같은 저장소에 남아 있는 것**과 **릴리스 산출물에 코드가 들어가는 것**을 분리해야 한다. 현재의 토글은 실행 시 라우트를 끄지만, artifact에서 코드를 제거하지는 않는다. 이 차이는 제안의 유효한 문제 제기다. 다만 그 해결책이 곧 별도 저장소일 필요는 없다.

## 1. 현재 정리와 실제 코드의 대조

프롬프트의 현재 상태 정리는 대부분 맞다.

- `app/presentation/ui/__init__.py`에서 `ops_ui`, `console_ui`, `composer_ui`를 독립적으로 라우트 등록한다.
- `console_ui=false`이면 console router와 일반 `/ui/**` router가 등록되지 않는다. `composer_ui`도 별도로 꺼진다.
- `tests/e2e/test_audience_boundary.py`는 고객 화면과 개발 화면의 독립성, 404/200 경계, navigation 누출, 고객 메시지 원문 누출을 검사한다.
- 콘솔은 `wiki/records/evidence/DoD-*.md`, `eval/reports/*.jsonl`, DB를 직접 읽는다. `/ui/admin`은 `composition.build_registry()`와 설정·adapter를 호출한다.
- DB의 trace는 `agent_runs → team_tasks → llm_calls → case_events`를 직접 SQL로 따라간다.

따라서 “토글로 완전히 끌 수 있다”는 **라우트·실행 경계**에 대해서는 맞지만, “릴리스 산출물에서 콘솔 코드가 아예 없다”는 관점에서는 아직 아니다. 또 `311 passed`는 현재 작업 트리에서 재현되지 않았다. 이번 점검에서는 관련 경계·콘솔 테스트가 **17 passed**였고, 전체 테스트는 **315 passed, 3 failed, 1 deselected**였다. 실패 3건은 RAG 통합 테스트가 `api.openai.com` 연결을 시도하다가 실행 환경의 네트워크 권한으로 실패한 것이므로 대시보드 분리의 회귀로 보지는 않는다. 숫자는 환경 의존성이 있으므로 이 문서의 결론 근거는 테스트 총량보다 구조와 경계 검증에 둔다.

보정할 점도 있다. “대시보드가 `app/composition.py`를 읽는다”기보다는 `/ui/admin`이 composition root를 **호출해 실제 조립을 재구성**한다. 이것은 파일 형식 의존보다 더 강한 런타임 결합이다.

## 2. A/B/C 판단

### A — 현행 유지

토글과 경계 테스트만으로는 현재 문제를 모두 해결하지 못한다. 고객 릴리스에서 `/ui`가 404가 되는 것은 보장하지만, 콘솔 모듈의 소스·의존성·취약점·빌드 비용이 제품 artifact에 남을 수 있다. “배포 후 로컬에서 다시 붙인다”는 운영 모델도 토글만으로는 제품과 개발 도구의 설치 단위를 분리하지 못한다.

따라서 A는 단기 안전장치로는 충분하지만 최종 구조로는 부족하다.

### B — 같은 저장소, 별도 패키지·설치 대상

현재 규모에 가장 적합하다. 저장소 하나에서 다음을 함께 바꿀 수 있어 다섯 내부 형식의 drift를 CI로 즉시 잡을 수 있다.

- 콘솔 코드를 별도 패키지/extra 또는 별도 build target으로 묶는다.
- 제품 배포 target은 그 패키지와 UI 의존성을 설치하지 않는다.
- 제품 artifact 검사에서 콘솔 패키지와 `/ui` route가 모두 없는지 확인한다. 단순 `console_ui=false` 테스트만으로는 이 조건을 증명할 수 없다.
- 개발 설치 target은 콘솔을 설치하고, 대상 프로젝트의 주소·자격증명·호환 버전을 명시한다.

B의 주의점은 “패키지 디렉터리를 나누는 것”만으로는 충분하지 않다는 것이다. 직접 파일·DB를 읽는 코드를 그대로 옮기면 패키지만 분리된 분산 모놀리스가 된다. 읽기 계약과 fixture를 먼저 고정해야 한다.

### C — 별도 저장소 `final_project_dashboard`

지금 선택하지 않는다. C가 주는 추가 이득은 여러 프로젝트에 하나의 독립 dashboard release를 배포하는 운영 독립성이다. 그러나 현재는 그 독립성을 뒷받침할 안정된 API/계약 버전/호환성 테스트가 없다. 다섯 형식을 계속 직접 읽는다면 C는 “저장소는 둘인데 함께 고쳐야 하는” 분산 모놀리스가 된다.

C는 이후 dashboard가 여러 제품·여러 버전의 대상에 붙고, 대상이 버전이 있는 read-only API를 제공하며, 호환성 매트릭스를 운영할 때 재검토할 수 있다.

## 3. C를 택한다면 drift를 막는 방법

C를 당장 택하지 않더라도, 향후 C로 갈 때 필요한 최소 통제는 다음과 같다. “계약 문서를 쓴다”만으로는 부족하다.

| 의존 대상 | 필요한 기계적 통제 |
|---|---|
| `config/project.yaml` 스키마·revision | 대상 저장소가 versioned schema endpoint 또는 canonical export를 제공한다. dashboard에는 schema version별 parser가 있고, fixture에 유효/무효 YAML을 둔다. 대상 CI가 dashboard contract test를 실행한다. revision은 dashboard가 임의 계산하지 않고 대상이 반환한 값을 표시한다. |
| `wiki/records/evidence/DoD-*.md` 형식 | Markdown을 정규 문서로 간주하지 말고 evidence manifest/JSON schema를 source of truth로 만든다. 대상 CI에서 모든 DoD fixture에 schema validator를 실행하고, 판정 enum·재현 명령·실제 출력 존재 여부를 검사한다. Markdown은 렌더링용으로만 둔다. |
| `eval/reports/*.jsonl` 필드 | run manifest와 row schema를 별도 version으로 둔다. 샘플 fixture에 arm/dataset/provider/ablation/holdout와 missing·estimated·observed·mock 사례를 모두 포함한다. producer CI와 dashboard CI에서 backward/forward compatibility를 검사하고, 모르는 필드는 0으로 대체하지 않는다. |
| DB 테이블 | dashboard가 테이블을 직접 전제하지 않도록 read-only API DTO 또는 versioned SQL view를 제공한다. migration마다 schema contract test와 최소 fixture DB를 실행하고, 삭제·rename은 deprecation 기간과 compatibility view 없이는 허용하지 않는다. tenant scope와 권한도 테스트한다. |
| `app/composition.py` 조립 결과 | composition 결과를 introspection용 versioned manifest로 직렬화하고, dashboard는 Python 내부 함수를 import하지 않는다. 각 port/module/team의 ID·revision·capability를 contract fixture로 비교한다. 조립 변경 PR은 dashboard contract test를 필수 status check로 둔다. |

여기에 저장소 간 CI가 필요하다. 대상의 contract fixture를 publish하고 dashboard가 소비하는 방식, 또는 대상 CI가 dashboard의 호환성 테스트를 pin된 commit으로 호출하는 방식 중 하나를 정해야 한다. 호환성 매트릭스 없이 “최신 대상에 붙는다”는 운영은 재현할 수 없다.

## 4. dashboard의 대상 접근 방식

권장 방향은 **read-only API를 기본 경계로 하고, 같은 저장소의 개발 모드에서만 직접 adapter를 허용하는 것**이다.

### 파일·DB 직접 읽기

장점은 구현이 빠르고 로컬 점검에 편하며, 현재 코드에서 이미 동작한다는 점이다. 단점은 다음과 같다.

- DB column/table 변경과 JSON/YAML/Markdown 변경이 dashboard release를 즉시 깨뜨린다.
- DB 자격증명과 파일 경로가 dashboard에 퍼진다.
- tenant scope·권한·PII 통제를 dashboard가 다시 구현해야 한다.
- 대상의 내부 Python import, 특히 composition root 결합이 생긴다.

따라서 B의 1단계 개발 adapter로는 허용할 수 있지만, 납품 후 원격 대상에 붙는 기본 방식으로 삼으면 안 된다.

### 대상이 노출하는 read-only API

장점은 대상이 schema version, 권한, tenant scope, redaction, revision을 소유할 수 있다는 점이다. dashboard는 화면용 DTO만 알면 된다. 단점은 API 구현·인증·버전 호환성·장애 상태 처리가 추가된다는 점이다.

그래도 C를 염두에 둔 장기 경계로는 API가 맞다. API가 없는데 C부터 하면 저장소 경계가 계약 경계를 대신하는 척하게 된다.

### 둘 다

운영 모드에 따라 명시적으로 선택하면 가능하다. 단, 두 경로의 결과를 비교하는 contract test가 없으면 같은 화면이 서로 다른 사실을 보여주는 이중 구현이 된다. “자동 fallback”은 인증 실패와 데이터 없음, schema 불일치를 구분하지 못하므로 금지해야 한다.

## 5. “릴리스 후 로컬에서 붙인다”에 필요한 것

최소한 다음 정보가 하나의 dashboard 대상 프로필에 있어야 한다.

- 대상 인스턴스 식별자와 base URL 또는 로컬 경로
- 대상 project/config revision 및 지원하는 dashboard contract version
- read-only 계정·token·TLS 설정 등 자격증명 위치. 자격증명 자체를 config나 evidence에 기록하지 않는다.
- tenant/project scope와 허용된 조회 범위
- 대상의 API/schema version과 dashboard의 호환 범위
- 네트워크 도달성, timeout, 재시도, “대상 없음”과 “데이터 없음”의 구분
- 연결 시 capability/health handshake와 사람이 읽을 수 있는 incompatibility 오류
- 제품 runtime과 dashboard runtime의 의존성·Python 버전·DB client 버전 분리

로컬 재부착은 “dashboard를 실행한다”가 아니라 “특정 revision의 특정 대상에 read-only로 연결한다”여야 한다. 그래야 릴리스 이후 결과가 어느 제품 조립 상태에서 나온 것인지 추적할 수 있다.

## 6. 지금 하지 말아야 할 이유와 먼저 할 일

지금 C를 시작하지 말아야 하는 이유는 명확하다. 현재 콘솔의 계약이 문서·파일·DB·Python 내부 함수에 흩어져 있고, 그 계약을 검증하는 공통 fixture/API가 없다. 지금 저장소를 나누면 변경 때마다 두 저장소를 수동으로 맞추게 된다. 이는 이 프로젝트가 이미 경계 테스트에서 강조하는 “검사하지 않는 규칙은 지켜지지 않는다”를 정면으로 위반한다.

순서는 다음이 맞다.

1. 다섯 의존 대상의 실제 읽기 필드와 최소 출력만 inventory로 고정한다.
2. 각 대상에 versioned schema와 positive/negative fixture를 만든다.
3. 콘솔을 별도 패키지·설치 target으로 묶고, 제품 artifact에서 패키지·route·UI 의존성이 빠지는 빌드 테스트를 추가한다.
4. 콘솔의 데이터 접근을 provider interface 뒤로 모으고, 개발용 direct adapter와 향후 API adapter를 분리한다.
5. 대상 지정·자격증명·revision·호환성 handshake를 갖춘 로컬 attach 명령/프로필을 만든다.
6. 이 계약 테스트가 안정된 뒤 여러 프로젝트·여러 릴리스에 공통 dashboard가 실제로 필요할 때 C를 재평가한다.

최종 선택은 **B**다. A는 artifact 분리를 해결하지 못하고, C는 현재의 내부 결합을 숨긴 채 조정 비용만 외부화한다. B가 제품 산출물 제거와 monorepo의 계약 검증을 동시에 제공하는 현재 규모의 최소 해법이다.
