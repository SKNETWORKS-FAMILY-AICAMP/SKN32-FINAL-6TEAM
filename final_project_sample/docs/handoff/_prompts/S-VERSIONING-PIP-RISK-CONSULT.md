# S-VERSIONING-PIP-RISK-CONSULT — `app` → 별도 패키지 리네임 + pip 화의 리스크 (의견만, 수정 금지)

## 이것도 설계 자문이다 — 코드를 고치지 마라, 새 파일을 만들지 마라

이전 자문(`S-VERSIONING-DESIGN-CONSULT.md`)에서 너와 나 둘 다 "SemVer +
CHANGELOG + git tag + export artifact(pip 아님)" 로 수렴했다. 그런데
사용자가 "장기적으로는 그냥 pip 으로 만드는 게 낫지 않냐"고 되물었다.
다시 생각해보니 나도 동의하는 면이 있다 — 이 저장소 자신의 설계 원칙
(`docs/handoff/10`)이 이미 "basement 는 복사 후에도 **그대로 둔다**"고
말한다. 그럴 거면 애초에 복사할 이유가 없고 진짜 의존성이어야 맞다.

**이번엔 "pip 이 맞냐 틀리냐"가 아니라 "지금 그 방향으로 갈 때 리스크가
뭐냐"를 냉정하게 따져 달라.** 사용자가 낙관적 답 대신 위험까지 알고
결정하고 싶어 한다.

## 확인한 사실 — 왜 지금 당장 pip install 이 안 되는가

두 저장소(`final_project_sample`, `final_project_cs`)가 **똑같이 `app/`
을 최상위 패키지 이름**으로 쓴다. cs 가 `pip install final-project-sample`
을 해도, cs 자신의 저장소 루트가 보통 `sys.path` 에서 site-packages 보다
먼저 잡히므로 **cs 자신의 `app/core/...` 가 설치된 패키지를 가려버려서
의존성이 적용되지 않는다.** 그래서 basement 최상위 패키지 이름을
`app` 아닌 걸로(예: `app`) 리네임해야 한다고 판단했다.

## 내가 이미 찾은 리스크 — 검증해 달라

1. **"리네임"이 아니라 "분할"이다.** basement(`app/core`·`domain`·
   `application`·`infrastructure`·`presentation`)만 새 이름으로 옮기고
   `app/modules`(도메인)는 그대로 둬야, cs 가 자기 도메인 코드는 로컬에
   두고 basement 만 의존성으로 받는 구조가 된다. 이건 단순 검색·치환
   리네임이 아니라 **한 패키지를 둘로 쪼개고 조립 루트
   (`app/composition.py`)의 import 방향을 다시 잡는 일**이다.
2. **경계 자체가 지금 완전하지 않다.** `app/tools/read_tools.py` 를
   읽어보면 `SELECT subscription_id, plan, status ... FROM subscriptions`
   같은 **도메인 어휘가 박힌 SQL** 이 들어 있다. 그런데 이 디렉터리는
   `tests/architecture/test_basement_is_domain_free.py` 의
   `BASEMENT_DIRS = ("core","domain","application","infrastructure","presentation")`
   에도, `DOMAIN_DIRS = ("modules",)` 에도 **안 들어 있어서 검사 대상이
   아니다.** `app/introspection/` 도 같은 사각지대인지 확인이 필요하다.
   분할 전에 이런 사각지대부터 basement/domain 어느 한쪽으로 명확히
   분류하지 않으면, "domain 무관 basement 패키지" 라고 배포한 것 안에
   도메인 어휘가 실려 나간다 — 지금 이 프로젝트가 이미 한 번 겪은
   실수(`app/core/verification.py` 가 구독·결제 어휘를 물고 있었던 것,
   `docs/handoff/10` §4)를 다른 형태로 반복하는 것이다.
3. **참조가 Python import 문에만 있지 않다.** `config/project.yaml` 의
   `implementation_ref: app.modules.customer_ops.feedback_team:...`,
   `app/core/project_config.py` 의 `KNOWN_IMPLEMENTATION_REFS`,
   `docs/handoff/*.md` 여러 곳의 정확한 모듈 경로 문자열, `Dockerfile`/
   `docker/compose.yml`/`infra/aws/` 의 `COPY app/` 류 경로, `pyproject.toml`/
   `setup.py` 의 패키지 탐색 설정까지 전부 영향받는다.
4. **일상 개발 마찰.** basement 를 pip 의존성으로 바꾸면, basement 를
   고치면서 동시에 실제 도메인 시나리오로 검증하려면 `pip install -e
   ../final_project_sample` 같은 editable install 워크플로가 필요하다.
   지금은 한 저장소·한 venv 로 끝난다.
5. **버전 규율이 배포 시점부터 강제된다.** pip 로 고정되면 cs 가 버전을
   올리기 전엔 basement 버그 수정도 못 받는다 — 지금처럼 파일을 그냥
   복사해 오는 것보다 배포 주기 관리 부담이 커진다.
6. **문서 재작성 범위.** `docs/handoff/10_도메인_교체_가이드.md` 의
   전제("복사해서 만든다")가 "설치해서 만든다"로 바뀌면, 이 문서와
   `CLAUDE.md`·`RULE.md`·여러 `docs/handoff/_prompts/*.md` 에 흩어진
   같은 전제도 갱신해야 한다.

## 물어보는 것

1. 위 6가지 리스크 중 내가 놓쳤거나 과장/과소평가한 게 있나?
2. **지금 당장 전체 리네임+분할을 할지, 아니면 단계적으로 갈지** 에
   대한 네 권고. 예를 들어:
   - (a) 지금 바로 분할+리네임+pip 화까지 간다
   - (b) SemVer/CHANGELOG/git tag 는 지금 시작하되(버전 체계는 pip 로
     가도 어차피 필요하다), 배포 메커니즘은 당분간 export+manifest 로
     두고, "app 분할"은 별도 후속 작업으로 명확히 스코프를 나눠 나중에
     한다
   - (c) 다른 순서
3. (b)를 고른다면, **지금 export+manifest 로 하는 작업이 나중에 pip
   전환을 더 어렵게 만드는 게 있나**(예: 나중에 버리게 될 코드를 지금
   만드는 셈인지), 아니면 SemVer 체계·CHANGELOG·경계 정리(`app/tools`
   사각지대 해소 등)는 어차피 pip 로 가도 그대로 재사용되는 투자인지?
4. `app/tools` 같은 미분류 사각지대를 basement/domain 어느 쪽으로
   보내야 하는지 코드 근거로 판단해 달라(가능하면).

## 출력 형식

산문. 각 권고에 **근거**와 **그 권고가 틀릴 수 있는 조건**을 같이 적어라.
