# S-VERSIONING-DESIGN-CONSULT — basement 버전 관리 설계 자문 (의견만, 수정 금지)

## 이건 버그 스캔이 아니라 설계 자문 요청이다

코드를 고치지 마라. 파일을 만들지 마라. **네 의견을 텍스트로만** 달라.
Claude(나)가 이미 검토한 내용에 반박하고 싶으면 반박해도 된다 — 근거를
대면 된다.

## 배경 — 정확히 확인한 사실

- `final_project_sample`(이 저장소)은 "basement" — 어떤 CS 플랫폼이든
  대응 가능한 도메인 무관 기반 구현. `wiki/records/handoff/10_도메인_교체_가이드.md`
  가 "복사 후 무엇을 갈아 끼우면 되는지"를 규정한다. basement 층:
  `app/core`·`app/domain`·`app/application`·`app/infrastructure`·
  `app/presentation`(도메인을 몰라야 함, 테스트가 강제:
  `tests/architecture/test_basement_is_domain_free.py`). 도메인 자리:
  `app/modules/**`·`config/**`·마이그레이션·`knowledge/**`·평가 데이터.
- `pyproject.toml` 의 `version = "0.1.0"` 이후 한 번도 안 올랐다.
  `CHANGELOG` 도 없고 git tag 도 없다.
- `../final_project_cs/`(형제 디렉터리, **완전히 별도의 git 저장소**)가
  이 저장소를 "복사해서" 만든 실제 CS 프로젝트다. 확인해 보니 **pip
  install 관계도, git submodule/subtree 관계도 아니다** — 그냥 한 번
  파일을 복사해 시작한 뒤 독립적으로 발전한 완전한 fork 다(자기 CLAUDE.md·
  RULE.md·wiki/records/handoff 01~10·docs/history·wiki/records/evidence 를 전부 따로
  갖고 있다). basement 버전을 추적하는 장치가 지금 **전혀 없다.**
- final_project_sample 은 이번 세션에 실질적인 기능이 여럿 늘었다
  (Composer 쓰기채널 v2/JWT, Response Generation & Review Team/DoD-29,
  버그 수정 여러 건). 이런 변경이 있을 때마다 final_project_cs 가 반영
  여부를 판단할 수 있어야 한다.
- 팀 규모는 작다(이 저장소의 다른 설계 결정들이 "6명·10주 학생 프로젝트
  규모"를 반복해서 근거로 든다 — 예: `wiki/records/handoff/13`의 인증 방식 선택).
  Windows 환경, 별도 CI 인프라는 확인되지 않았다.

## 물어보는 것

final_project_sample("basement")의 버전을 어떻게 관리해야
1) 스스로도 관리가 되고,
2) final_project_cs 처럼 그걸 복사해 만든 하위 프로젝트가 "지금 내
   basement 는 몇 버전 기준이고, 최신 대비 뒤처졌는지" 를 쉽게 알고,
3) 뒤처졌으면 **domain 층(app/modules/**, config/**)을 건드리지 않고
   basement 층만** 안전하게 업데이트할 수 있는가?

## 내(Claude)가 지금 기울어 있는 방향과 이유

**SemVer(`pyproject.toml`) + `CHANGELOG.md` + git tag** 로 sample 쪽
버전을 관리하고, cs 쪽에는 "이 저장소의 basement 는 sample vX.Y.Z
기준" 이라는 마커 파일 하나만 두는 가벼운 방식. **git subtree/submodule
은 추천하지 않는다** — 두 저장소가 이미 완전히 다른 git history 로
갈라져 있어서 지금 subtree 관계를 소급 적용하면 배보다 배꼽이 커진다.
**pip 설치 가능한 패키지로 배포**하는 것도 추천하지 않는다 — `app/modules`
가 이미 `app/core` 를 상속/오버라이드하는 구조가 아니라 "선언(config/
project.yaml)으로 조립"하는 구조라서, 패키지 의존성으로 바꾸려면 앱
조립 방식 자체를 바꿔야 해서 작업량이 이 팀 규모에 안 맞는다.

## 하지만 답이 안 나온 것들 — 여기가 진짜 자문이 필요한 부분

1. **basement 갱신을 cs 에 "적용"하는 실제 메커니즘.** 마커 파일로
   "뒤처졌다"는 알아도, 실제로 파일을 옮기는 건 무엇으로 하나?
   - (a) sample 쪽에 `scripts/export_basement.py` 를 만들어 basement
     경로만 압축/복사해 내보내고, cs 쪽은 받아서 직접 diff 검토 후
     덮어쓴다?
   - (b) 그냥 `git diff --no-index` 두 체크아웃 디렉터리를 비교해
     패치를 만들고 cs 에 `git apply` 한다?
   - (c) 아예 자동화하지 않고, "basement 변경 로그(CHANGELOG)를 읽고
     사람이 손으로 옮긴다"를 공식 절차로 삼는다(이 팀 규모엔 이게
     맞을 수도 있다)?
   - 다른 방법이 있나?
2. **버전 단위를 뭘로 쪼개나.** 매 커밋마다 버전을 올리나, 아니면
   "이 정도면 basement 변경이 쌓였다" 판단이 필요한 시점(패치/기능
   릴리스)에만 올리나? patch/minor/major 를 가르는 기준을 이 프로젝트
   맥락에서 뭘로 잡아야 하나(예: `contracts.py` 계약 변경=major,
   `app/modules` 예시 추가/이동=버전 무관, basement 버그 수정=patch)?
3. **cs 프로젝트가 이미 갈아 끼운 부분과 sample 의 새 basement 변경이
   충돌하면?** — cs 가 자기 도메인에 맞게 `app/core/verification.py`
   같은 basement 파일을 (규칙을 어기고) 손댔을 수도 있다. 업데이트
   전에 그런 드리프트를 어떻게 미리 감지하나?
4. **"모듈, 컴포넌트, 인스턴스 설계를 잘 해서 매번 업데이트해도 문제
   없도록"** 이라는 사용자 요구를 만족하려면 지금 basement 의 경계
   (Port 6종, Registry, `TeamManifest`, `contracts.py`) 가 이미
   충분한가, 아니면 버전 호환성을 위해 추가로 굳혀야 할 계약이 있나?

## 출력 형식

프리즈 없이 산문으로 답해도 된다. 다만 각 항목에 대해 **네 최종 권고**와
**그 권고를 뒤집을 수 있는 반례/전제**를 함께 적어라 — "이럴 땐 다른
답이 맞다" 없이 확신만 말하지 마라.
