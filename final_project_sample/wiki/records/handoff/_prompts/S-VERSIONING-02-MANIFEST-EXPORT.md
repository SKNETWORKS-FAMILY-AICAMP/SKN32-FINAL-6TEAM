# S-VERSIONING-02-MANIFEST-EXPORT — basement manifest 스키마 + export 도구

## 배경

`final_project_cs`(형제 저장소, 완전히 별도의 git 저장소)가 이 저장소를
복사해 만든 하위 프로젝트다. basement(`app/core`·`domain`·`application`·
`infrastructure`·`presentation`)가 바뀔 때 cs 가 "어떤 버전을, 어떤
파일들을, 무엇과 함께" 받았는지 재현 가능하게 기록해야 한다. Claude·
Codex 자문 결론: 지금은 pip 패키지가 아니라 **export artifact + manifest**
로 간다 — 단, manifest 는 **폴더 경로를 하드코딩해 크롤링하는 방식이
아니라 "선언된 컴포넌트 집합" 방식**으로 설계해야 나중에 pip wheel
패키지 파일 목록과 자연스럽게 이어진다(지금 버려질 임시 코드를 만들지
않는다).

## 만들 것

1. **`scripts/basement_manifest.py`**(신규) — basement 컴포넌트 목록을
   **선언**하는 모듈. 하드코딩된 디렉터리 나열이 아니라, 아래 형태의
   명시적 선언으로 시작한다(나중에 `S-VERSIONING-03-BOUNDARY-TOOLS`
   가 경계를 재조정하면 이 선언만 고치면 되게):

   ```python
   BASEMENT_COMPONENTS: tuple[str, ...] = (
       "app/core",
       "app/domain",
       "app/application",
       "app/infrastructure",
       "app/presentation",
   )
   EXCLUDED_PATTERNS: tuple[str, ...] = ("__pycache__", "*.pyc")
   ```

   ★도메인 마이그레이션(`app/infrastructure/db/migrations/002_domain_*.sql`)
   은 `app/infrastructure` 안에 있지만 도메인이다 — `EXCLUDED_PATTERNS`
   또는 별도 목록으로 명시적으로 제외한다. `wiki/records/handoff/10` §0 경계표를
   그대로 따른다.

2. **`scripts/export_basement.py`**(신규) — `basement_manifest.py`의
   선언을 읽어 다음을 만든다:
   - `dist/basement/manifest.json` — 스키마:
     ```json
     {
       "basement_version": "0.2.0",
       "source_commit": "<git rev-parse HEAD>",
       "source_tag": "<git describe --tags 결과, 없으면 null>",
       "generated_at": "<ISO8601>",
       "components": ["app/core", "app/domain", ...],
       "excluded": ["..."],
       "files": [{"path": "app/core/contracts.py", "sha256": "..."}, ...],
       "contract_version": "1.0",
       "export_tool_version": "1"
     }
     ```
     ★`generated_at`은 `datetime.now(UTC)` 등 실행 시점 값이라 테스트에서
     결정론이 필요하면 주입 가능하게 만들어라(고정 못 박지 마라).
   - `dist/basement/files/` — 선언된 컴포넌트 파일을 그대로 복사한
     디렉터리(cs 쪽에서 diff·적용에 쓸 원본).
   - `dist/`는 재생성 가능한 빌드 산출물이다 — `.gitignore`에
     `dist/` 를 추가해라(이미 있는 패턴들 형식을 따른다).

3. **테스트**(신규, `tests/unit/scripts/test_export_basement.py` 등
   적절한 위치) — manifest 가 실제로 선언된 파일들과 일치하는지(해시가
   맞는지), `EXCLUDED_PATTERNS`에 걸리는 파일이 제외되는지, 도메인
   마이그레이션이 export 에 포함되지 않는지 검증한다.

4. **`wiki/records/handoff/15_basement_버전_배포_계약.md`**(신규) — manifest
   스키마 표, `export_basement.py` 사용법(`python -m scripts.export_basement`),
   cs 쪽에서 이걸 어떻게 받는지(지금은 사람이 diff 검토 후 수동 적용 —
   자동 적용 스크립트는 이번 스트림 범위 밖. `wiki/records/handoff/10`을 참조해
   "복사 후 갈아 끼운다"의 반복 버전이라고 명시), `S-VERSIONING-01-SEMVER`
   가 정한 SemVer 기준을 인용(복사하지 말고 인용).

## 하지 않을 것

- `app/`·`config/`·`tests/architecture/**` 등 기존 런타임/검사 코드를
  건드리지 않는다(별도 스트림 `S-VERSIONING-03-BOUNDARY-TOOLS`가
  경계 재분류와 `app/tools` 리팩터를 담당한다 — 이 스트림은 그 결과를
  **그대로 선언만 참조**하면 된다).
- cs 저장소(`../final_project_cs`)의 어떤 파일도 건드리지 않는다.
- basement manifest 를 실제로 cs 에 적용하는 자동화(apply/preflight)는
  만들지 않는다 — 이번 스트림은 **export**까지다.
- 사람이 아직 검토 전이므로 실제 `dist/basement/` 산출물을 git 에
  커밋하지 않는다(`.gitignore` 대상이다).

## 검증

```powershell
python -m scripts.export_basement
python -m pytest tests/unit/scripts/test_export_basement.py -q
python -m pytest -q --ignore=tests/integration/rag
```
새 파일만 추가하므로 기존 테스트 결과는 이 스트림 시작 전과 동일해야
한다.

## 만들 것 (리포트)

`wiki/records/reports/2026-08-18_S-VERSIONING-02-MANIFEST-EXPORT_리포트.md` —
실행 명령과 실제 출력(manifest.json 예시 일부 포함), 만든 파일 목록.
