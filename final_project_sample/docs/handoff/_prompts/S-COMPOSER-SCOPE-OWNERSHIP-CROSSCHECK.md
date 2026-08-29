# S-COMPOSER-SCOPE-OWNERSHIP-CROSSCHECK — 다른 세션 산출물 3건 교차검증 (의견만, 수정 금지)

## 이것도 설계 자문이다 — 어떤 파일도 고치지 마라, 새 파일을 만들지 마라

읽기 전용 샌드박스로 실행된다. `final_project_sample`·`final_project_cs`·
`program/`·`final_project_ui`(존재한다면) 어떤 파일도 건드리지 마라.

## 배경

오늘(2026-08-24) 다른 세션이 `program/plan/`에 문서 3개를 만들었고, 사용자가
"코덱스랑 교차검증해봐"라고 요청했다. 이 요청을 받은 세션(나, Claude)이
이미 세 문서를 직접 읽고 두 핵심 기술 주장을 `final_project_cs`의 실제
코드로 재현·확인했다(아래 "이미 확인한 것" 참고). 이제 **독립적인** 두
번째 의견이 필요하다 — 앞선 세션이 낸 결론을 그대로 베끼지 말고, 스스로
코드를 다시 읽고 판단해라.

## 세 문서 (읽어라)

1. `program/plan/A-COP_Composer_소유권_정정.md` — 핵심 주장: `final_project_
   ui/CLAUDE.md` §0.3의 "대상 프로젝트의 파이썬을 import 하지 않는다"에서
   **"대상"은 `final_project_cs`만을 가리키고 `final_project_sample`은
   대상이 아니다**. 따라서 UI가 sample이 만든 패키지(예: `acop_composer_ui`,
   가칭)를 import하는 것은 이 원칙 위반이 아니고, sample이 Composer
   판단·요청 로직을 만들고 UI가 그걸 가져다 쓰는 구조가 맞다고 결론짓는다.
   기존 `A-COP_Composer_v3_설계_토글전용_UI이관.md`(§3 표, §8.1)가 이 구분을
   안 하고 "UI는 이번 설계의 구현 대상이 아니다"/"UI는 아무것도 pip
   install 안 해도 동작해야 한다"고 써서 여러 세션이 "UI가 자체 구현해야
   한다"로 잘못 읽었다고 주장한다.

2. `program/plan/A-COP_Composer_범위재검토.md` — 핵심 주장: 토글 전용 v3를
   Composer 전체의 대체 계약으로 쓰면 안 된다. 실제 요구(운영 UI에서 Team
   모듈·GraphStore 등을 이름·설정만 입력해 새로 만들고 지울 수 있어야
   함)를 토글만으로는 충족 못 한다. `POST /composer/catalog`,
   `POST /composer/changes`, `POST /composer/activations` 세 계약과
   "선언형 Team"(범용 실행기 하나를 배포해두고 개별 Team은 데이터로만
   만드는 방식)을 새로 제안한다.

3. `program/plan/A-COP_남은작업_인수인계.md` — 여러 세션에 걸친 작업
   인수인계 문서. Composer 관련해서는 위 두 문서를 다음 세션이 이어받으라고
   지시한다.

## 이미 확인한 것 (다시 반복해서 검증하지 마라, 대신 그 위에서 판단해라)

- `final_project_cs/app/core/project_config.py`의 `TeamConfig`에
  `team_id`/`active`/`implementation_ref`만 있고 설정 필드가 없음 — 실측
  확인.
- `final_project_cs/app/composition.py`가 동일 capability를 주장하는 두
  Team 선언을 거부함(`duplicate capability` 에러) — 실측 확인.
- `f2b2049`, `16f0ca0` 커밋이 `final_workspace`(workspace 브랜치) git
  이력에 실제로 존재함 — 확인.

## 물어보는 것

### 1. 소유권 정정(`A-COP_Composer_소유권_정정.md`)이 옳은가

- §0.3의 "대상"이 정말로 `final_project_cs`만 가리키고 `final_project_
  sample`은 제외되는 게 맞는가? `final_project_ui/CLAUDE.md` 원문을 실제로
  찾아 읽고(있다면) §0.2·§0.3 전후 문맥까지 확인해라. 이 문서가 자기
  주장에 유리하게 문맥을 잘라 인용했을 가능성도 검토해라.
- UI가 sample이 만든 패키지(`acop_composer_ui` 류)를 import하는 것이
  "라이브러리 사용"과 "대상 코드 포크" 중 어느 쪽에 더 가까운가?
  `acop_basement`/`acop_composer`가 실제로 도메인 무관하고 안정적인
  버전 계약(SemVer, `docs/handoff/15`)을 갖고 있다는 사실이 이 판단에
  실제로 영향을 주는가, 아니면 "누가 만들었나"와 무관하게 "UI 프로세스가
  남의 검증 로직을 통째로 흡수한다"는 근본 문제는 그대로 남는가?
- 이 정정이 맞다면, `final_project_ui`가 이 새 패키지를 import했을 때
  생기는 새로운 결합(coupling) 위험은 뭔가 — 예를 들어 `acop_composer_ui`
  버전이 오르내릴 때마다 UI 배포도 다시 해야 하는가? 이게 원래 v3 설계가
  피하려던 "UI가 대상 스키마 변경에 끌려다니는 문제"를 다른 이름으로
  재현하는 건 아닌가?

### 2. 범위재검토(`A-COP_Composer_범위재검토.md`)가 제안하는 확장이 타당한가

- `POST /composer/catalog`·`/changes`·`/activations` 3계약 + "선언형
  Team" 제안이 기술적으로 맞는 방향인가, 아니면 이 프로젝트 규모(6명·
  10주 학생 프로젝트, `CLAUDE.md`가 반복해서 드는 전제)에 비해 과설계인가?
- 이 문서가 스스로 인정한 "확인하지 못한 것"(§8 — 실제 HTTP 요청 안 보냄,
  다중 worker 여부 미확인, 외부 `/apply` 소비자 수 미확인 등)이 결론의
  신뢰도를 얼마나 깎아먹는가?
- "선언형 Team"(`DeclarativeTeamRuntime` 범용 실행기 + 데이터로 Team
  정의) 아이디어 자체는 이 저장소의 기존 원칙(`TeamModule` 계약,
  `manifest`/`execute()` 요구, "Core는 Team 내부를 모른다")과 충돌 없이
  들어맞는가, 아니면 새로운 종류의 위험(예: 프롬프트가 곧 코드가 되는
  구조에서 프롬프트 injection이 곧 권한 상승이 되는 위험)을 만드는가?

### 3. 지금 당장 뭘 해야 하나

- `final_project_sample`은 오늘(2026-08-19~24 사이) `acop_basement`/
  `acop_composer` 패키지 분리, `docs/handoff/13` §0(v3 토글 계약 canonical
  사본)까지 이미 진행했다. 이 새 방향(소유권 정정 + 범위 확장)이 맞다면
  sample 쪽에서 뭘 되돌리거나 다시 써야 하는가, 아니면 지금까지 한 일과
  양립 가능한가?
- 세 문서 모두 "다음 세션이 이어받으라"고만 하고 실제 착수 순서를 못
  박지 않았다. 지금 이 시점에 사용자가 실제로 승인해야 할 최소 결정이
  뭔가(패키지 이름? 계약 확정? 코드 착수 여부?) — 문서만 더 쌓이는 걸
  피하려면 뭘 먼저 확정해야 하는지 짚어라.

## 출력 형식

산문. 각 판단에 근거(`파일:줄번호`, 저장소 이름 명시)와, 그 판단이 틀릴 수
있는 조건을 같이 적어라. 앞선 세션 결론에 동의하든 반대하든 "좋습니다"로
끝내지 마라 — 동의한다면 왜 스스로 다시 확인해도 같은 결론이 나오는지,
반대한다면 구체적으로 뭐가 다른지 적어라.
