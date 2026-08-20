# S-COMPOSER-DEPLOYMENT-TOPOLOGY-CONSULT — Composer 쓰기 API를 같은 프로세스에 실어도 되는가 (의견만, 수정 금지)

## 이것도 설계 자문이다 — 코드를 고치지 마라, 새 파일을 만들지 마라

## 배경 — 정확히 확인한 사실

`app/presentation/api/app.py`의 `create_app()`이 **하나의 FastAPI `app`
객체**에 다음을 전부 등록한다:

```python
app.include_router(build_router(classifier, runtime_controller))   # 고객 대면: /v1/cases 등
app.include_router(build_outbox_router())
mount_ui(app)                                                       # 운영 UI
app.include_router(composer_write_router)                           # /composer/validate, /composer/apply — 구성 쓰기
app.include_router(composer_auth_router)                            # /auth/token — JWT 발급
```

같은 프로세스, 같은 포트, 같은 바인딩이다. `docs/handoff/13`(Composer
쓰기채널 계약)은 "VPN/SSH 터널 + 단명 JWT" 를 인증 계층으로 전제하는데,
실제로는 고객 트래픽(`/v1/cases`)과 구성 쓰기 API(`/composer/apply`)가
**같은 서버 프로세스**를 쓴다. VPN 전제를 지키려면 인프라(리버스 프록시·
방화벽 규칙)가 경로별로 접근을 갈라야 하는데, 그건 이 코드 밖의 일이고
강제하는 장치가 코드 안에는 없다 — scope(JWT)로만 막는다.

`setup.py`의 `ProductBuildPy`는 릴리스 빌드에서 `app/console/**`(개발
콘솔 대시보드) 와 `app/presentation/ui/composer.py`(HTML 폼)만 뺀다.
`app/application/composer_service.py`·`app/presentation/api/composer.py`
(REST 라우터)·`app/presentation/composer_auth.py`(JWT 발급)는 **릴리스
빌드에도 그대로 포함된다** — 그래야 릴리스 이후 `final_project_ui`가
이 API 로 원격 구성 관리를 계속할 수 있다는 게 지금까지의 설계 의도다.

## 사용자가 제기한 문제

"고객이 쓰는 프로그램에 쓰기 가능한 구성 관리 API(폭탄 같은 기능)가
같이 딸려서 릴리스된다 — 이게 실무적으로 맞는 구조냐?"

일리 있는 지적이다. 같은 프로세스에 있으면:
- JWT 서명 비밀키 유출, 인증 코드의 버그, 이 경로의 취약점 하나가
  **고객 대면 서비스 전체**의 가용성·무결성에 영향을 줄 수 있다.
- 공격 표면이 늘어난다 — 감사·펜테스트 범위가 고객 기능과 관리 기능을
  분리하지 못한다.
- 배포 주기가 묶인다 — Composer 쪽 보안 패치가 고객 기능과 무관해도
  같은 바이너리를 다시 배포해야 한다.
- "VPN/SSH 전제" 를 인프라가 강제하지 않으면(예: 같은 포트를 공인 IP 로
  열어버리면) 그 전제 자체가 종이 위의 약속일 뿐이다.

## 반대로, 지금 구조가 이렇게 된 이유(무시하면 안 되는 근거)

- `composer_service.py` 가 대상 앱의 **실제 canonical config loader**
  (`load_project_config`)를 그대로 재사용한다 — "검증기가 실제 로더와
  다르면 검증은 통과했는데 기동은 실패한다" 는 문제를 피하려던 것이다.
  검증 로직을 분리 배포하면 이 보장이 깨질 위험이 있다.
- `final_project_ui`(대상을 관리하는 외부 콘솔)는 **자기 저장소에
  대상의 검증 모델을 절대 복사하지 않는다**는 원칙이 있다
  (`final_project_ui/CLAUDE.md` §0.2: "대상의 검증 모델을 가져오지
  않는다 — 그 순간 포크가 시작되고, 대상이 스키마를 바꿀 때마다 여기도
  따라 고쳐야 한다"). 즉 쓰기 로직을 ui 쪽으로 옮기는 건 이미 명시적으로
  피하려던 안티패턴이다.
- 이번 세션에 basement SemVer/manifest 배포 체계(`scripts/export_basement.py`,
  `docs/handoff/15`)를 막 만들었는데, 이 API 를 별도 서비스로 쪼개면
  그 배포 체계에도 영향이 있다(별도 컴포넌트로 봐야 하는지, 같은
  manifest 안에 있어야 하는지).

## 물어보는 것

1. **지금처럼 같은 프로세스/포트에 두는 게 실무적으로 문제인가, 아니면
   VPN/SSH + JWT + scope 분리만으로 실무 기준을 충족하는가?** 이 규모
   (6명·10주 학생 프로젝트, 근거: `docs/handoff/13`이 반복해서 드는
   전제)에서 "충분히 안전한 최소 구성" 은 뭔가?
2. **대안 — 별도 프로세스/서비스로 쪼갠다면 어떤 형태가 맞나?**
   - (a) 같은 코드베이스, 같은 배포 산출물이지만 **다른 포트/바인딩**으로
     띄우는 두 번째 ASGI 앱(예: `create_app()` 을 두 개로 쪼개 고객용
     앱과 관리용 앱을 분리하고, 관리용은 방화벽 뒤 별도 포트에만 바인딩)
   - (b) 완전히 별도 프로세스(사이드카)로 배포하되, **같은 basement
     라이브러리를 import** 해서 `composer_service.py` 를 재사용(코드
     복제 아님, 배포만 분리)
   - (c) `docs/handoff/13`이 이미 전제하는 대로 VPN/SSH **네트워크
     경계만으로 충분**하다고 보고 지금 구조를 유지하되, 문서에 "이
     포트를 공인 인터넷에 노출하면 안 된다"는 배포 요구사항을 더
     명시적으로 못박는다
   - (d) 다른 형태
3. **basement SemVer/manifest 배포 체계와의 관계** — 만약 (a)나 (b)로
   쪼갠다면, `scripts/basement_manifest.py`의 `BASEMENT_COMPONENTS`
   선언(지금은 `app/core`·`domain`·`application`·`infrastructure`·
   `presentation` 전체를 하나로 묶는다)도 다시 나눠야 하는지, 아니면
   지금 이대로도 재사용 가능한지.
4. **지금 당장 뭘 해야 하나** — 이건 학생 프로젝트 규모의 릴리스
   준비 단계인데, 지금 구조 변경까지 가야 할 사안인지, 아니면 문서화
   (배포 가이드에 네트워크 경계 요구사항 명시)만으로 충분하고 실제
   프로세스 분리는 나중 과제(`docs/vision/`)로 미뤄도 되는지.

## 출력 형식

산문. 각 권고에 근거와, 그 권고가 틀릴 수 있는 조건을 같이 적어라.
