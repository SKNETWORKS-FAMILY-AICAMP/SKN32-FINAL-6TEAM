# 15 — basement 버전·배포 계약

★2026-08-19(v0.3.0) 갱신 — basement 는 이제 실제 **pip 설치 가능한 패키지**
`acop_basement`다(2026-08-18 작성 당시엔 아직 export artifact 방식뿐이었다).
Composer 쓰기 채널은 `acop_composer`라는 별도 선택 패키지로 분리됐다 —
릴리스 대상(예: `final_project_cs`)은 `acop_basement`만 설치하고,
"관리용 빌드"만 `acop_composer`를 추가로 설치한다. 아래 export/manifest
절차는 **pip 설치가 아직 안 되는 소비자**(예: 수동 diff·검토가 필요한
경우)를 위한 보조 수단으로 유지한다 — 정식 소비 경로는
`pip install`이다. 현재 artifact의 `basement_version`은 `0.3.0`이고
manifest 계약 버전은 `1.0`이다.

## 경계와 manifest

경계는 `scripts/basement_manifest.py`의 `BASEMENT_COMPONENTS` 선언이 소유한다.
현재 컴포넌트는 `acop_basement/core`, `acop_basement/domain`,
`acop_basement/application`, `acop_basement/infrastructure`,
`acop_basement/presentation`, `acop_basement/tools`,
`acop_basement/introspection`, `acop_basement/teams` 8개다(`teams` 는
2026-08-30 에 선언형 Team 실행기와 함께 추가됐다 — 빠뜨리면 export 를 받은
소비자가 `DECLARATIVE_TEAM_REF` 를 못 쓴다.
`tests/architecture/test_basement_manifest_covers_every_package.py` 가
이제 누락을 잡는다)(`tools`·`introspection`은 2026-08-19에
basement 경계로 확정됐다 — `docs/handoff/10` §0). `acop_composer/**`는
별도 패키지라 이 manifest 대상이 아니다. `__pycache__`, `*.pyc`는
export하지 않는다. 도메인 마이그레이션(`config/migrations/
002_domain_*.sql`)은 애초에 `acop_basement/` 경로 밖에 있어 자동으로
빠진다(예전엔 `acop_basement/infrastructure/db/migrations/` 안에 있어서
패턴으로 제외해야 했다 — 지금은 물리적으로 그 경로에 없다).

manifest에는 basement 버전, source commit/tag, UTC 생성 시각, 컴포넌트와
제외 목록, 파일별 SHA-256, 계약 버전, export 도구 버전이 들어간다. 파일
경로는 저장소 상대 POSIX 경로로 기록하고 정렬한다.

## export 사용법

저장소 루트에서 실행한다.

```powershell
python -m scripts.export_basement
```

결과는 `dist/basement/manifest.json`과 `dist/basement/files/` 아래에 생성된다.
다른 위치를 검사하거나 테스트하려면 `--output-dir`를 사용할 수 있다.

cs 프로젝트에서는 `manifest.json`의 `files[].path`와 SHA-256을 먼저 확인한
뒤 `files/`의 파일을 basement 경계에 수동으로 diff·적용한다. 이 도구는 cs
프로젝트를 찾아가거나 파일을 자동 적용하지 않는다.

## 버전 규칙

SemVer 기준은 `docs/handoff/10_도메인_교체_가이드.md`의 경계를 따른다. 기존
계약과의 버그 수정은 patch, 호환 가능한 기능·Port·registry ID 추가는
minor, 필수 계약 필드·Port 인터페이스·registry ID 제거/변경은 major다.
`app/modules`, `config`, `knowledge`와 같은 복사본의 도메인 변경은 basement
버전과 별도로 관리한다.

export artifact는 빌드 산출물이므로 `dist/` 전체를 git에 커밋하지 않는다.
