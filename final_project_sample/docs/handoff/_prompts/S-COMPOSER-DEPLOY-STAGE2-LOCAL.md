# S-COMPOSER-DEPLOY-STAGE2-LOCAL — 고객/관리 이미지 실제 분리 (로컬 범위만)

## 배경

`docs/plans/2026-08-18_Composer_배포_경계_분리_계획.md` §4(2단계)가 정의한
목표 — "customer-runtime / composer-control 두 진입점을 각각 다른
실행 커맨드/이미지로 빌드 가능하게 한다" — 는 이번 세션의
`acop_basement`/`acop_composer` 패키지 분리(v0.3.0)로 **코드 경계는 이미
달성됐다**(계획서 §5, 2026-08-19 갱신분 참고): `acop_basement.presentation.
api.app:create_app()`이 Composer 라우터를 옵션 인자로만 받고,
`app/entrypoint.py`가 그 위에 `acop_composer`를 얹는다.

**아직 안 된 것은 배포 산출물(이미지) 경계뿐이다** — `Dockerfile`이 여전히
`app.entrypoint:app`(Composer 포함) 하나만 빌드한다. 이 스트림은 그 나머지,
**로컬(이 저장소 안)에서 끝나는 부분만** 다룬다.

## 범위 — 이번엔 한다 / 안 한다

**한다**:
- 고객 전용 이미지(Composer 없음, `acop_basement.presentation.api.app:app`)와
  관리용 이미지(Composer 포함, `app.entrypoint:app`)를 **각각** 빌드하는
  Dockerfile 구조.
- `docker/compose.yml`에 두 서비스(고객용/관리용)를 선언 — 서로 다른
  Dockerfile(또는 같은 Dockerfile의 다른 build target/stage)과 다른
  uvicorn 커맨드를 쓴다.
- 두 서비스 모두 `--workers 1`을 유지한다(`_WRITE_LOCK`이 프로세스
  로컬이라는 기존 제약 — `docs/handoff/13` 참고. 고객 이미지엔 Composer가
  아예 없으니 이 제약이 무의미해지지만, 관리 이미지엔 여전히 적용된다).

**안 한다(범위 밖)**:
- `infra/aws/**`는 건드리지 않는다 — AWS 쪽 배포 대상 분리는 이 저장소
  CLAUDE.md가 명시하길 "가정일 뿐 사용자 확답 전"이다. 이 스트림은 로컬
  Dockerfile/compose까지만이다.
- 이 기계엔 Docker가 설치돼 있지 않다(`CLAUDE.md` 환경 주의사항) —
  `docker build`/`docker compose up`을 실제로 실행해 검증할 수 없다.
  **문법·정적 확인(파일이 유효한 YAML/Dockerfile 구문인지, COPY 대상
  경로가 실제로 존재하는지)까지만 하고, "미검증"이라고 리포트에 명시한다.**
  거짓으로 "빌드 확인함"이라고 쓰지 않는다.
- Composer 적용(`apply`) 후 customer-runtime 반영 방법(런타임 reload 계약)은
  여전히 정의하지 않는다 — 계획서 §2가 이미 "2단계 안에서 결정"이라고
  했지만, 실제 운영 경험 없이 지금 확정하면 추측이 된다. 이 스트림은
  **이미지가 물리적으로 분리된다**는 사실만 만든다.

## 만들 것

1. **`Dockerfile`** 수정 — 현재 단일 스테이지를 유지하되, 두 가지 최종
   이미지를 낼 수 있는 구조로 바꾼다. 아래 두 방식 중 실제 코드를 읽고
   더 적은 중복으로 가는 쪽을 선택해라(둘 다 무방하나 어느 쪽을 골랐는지
   리포트에 근거와 함께 남겨라):
   - (a) multi-stage build — 공통 베이스 스테이지 + `customer`/`admin` 두
     타깃 스테이지, `docker build --target customer`로 선택.
   - (b) 두 개의 Dockerfile — `Dockerfile`(관리용, 기존과 동일) +
     `Dockerfile.customer`(신규, `acop_composer/` COPY 없음, CMD가
     `acop_basement.presentation.api.app:app`).
   ★고객 이미지는 **`acop_composer/` 디렉터리를 COPY하지 않는다** — 이게
   핵심이다(코드 자체가 이미지 안에 없어야 "릴리스에 컴포저가 딸려
   나간다"는 우려가 실제로 해소된다).
2. **`docker/compose.yml`** 수정 — 서비스 2개(`app-customer`, `app-admin`
   등 적절한 이름)로 나눈다. 기존 DB 서비스는 공유한다(포트만 나눠서
   docs에 표로 정리 — 예: 고객 8000, 관리 8001).
3. **`docs/handoff/13_composer_쓰기채널_v2_계약.md`**(정확한 파일명은
   실제로 확인해라 — Composer v2 계약 문서) 또는
   `docs/handoff/14_배포_계약.md`(정확한 이름 확인) 중 배포 관련 문서에
   이 분리를 반영 — "이제 이미지 자체가 물리적으로 분리된다"는 사실과,
   "런타임 reload는 여전히 미정의"라는 한계를 함께 적는다.
4. **`docs/plans/2026-08-18_Composer_배포_경계_분리_계획.md`** §4를
   "이미지 분리 완료(로컬), 실배포 인프라(AWS)는 별도"로 갱신할 근거
   자료를 리포트에 담아라(문서 자체 수정은 Claude가 검수 후 한다 —
   이 스트림은 코드/설정 파일만 바꾼다. 계획서는 건드리지 마라).

## 검증

```powershell
# Docker가 없으므로 아래는 실행하지 못한다 — 대신 이렇게 확인해라:
python -c "import pathlib; print(pathlib.Path('Dockerfile.customer').exists())"  # 예시, 실제 파일명에 맞게
# YAML 문법 확인
python -c "import yaml; yaml.safe_load(open('docker/compose.yml', encoding='utf-8'))"
python -m pytest -q --ignore=tests/integration/rag
```

Dockerfile/compose.yml 외 코드(`acop_basement/**`, `acop_composer/**`,
`app/**`)를 건드리지 않으므로 전체 테스트 결과는 이 스트림 전후로 동일해야
한다.

## 만들 것 (리포트)

`docs/reports/2026-08-19_S-COMPOSER-DEPLOY-STAGE2-LOCAL_리포트.md` —
선택한 방식(multi-stage vs 이중 Dockerfile)과 근거, 변경한 파일 목록,
**Docker 미설치로 실제 빌드는 검증하지 못했다는 사실을 명시**, YAML 문법
확인 결과, 전체 테스트 결과.

## 하지 말 것

- `infra/aws/**` 수정 금지.
- Docker가 설치돼 있다고 가정하고 "빌드 성공"이라고 쓰지 않는다 — 실행
  못 했으면 못 했다고 쓴다.
- `docs/plans/2026-08-18_Composer_배포_경계_분리_계획.md` 직접 수정 금지
  (Claude가 검수 후 반영한다).
