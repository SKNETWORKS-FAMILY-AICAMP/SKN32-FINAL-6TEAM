# S-VERSIONING-01-SEMVER — basement SemVer·CHANGELOG·릴리스 기준 도입

## 배경

이 저장소("basement")는 지금까지 `pyproject.toml`의 `version = "0.1.0"`
이후 한 번도 버전을 올리지 않았고 CHANGELOG도, git tag도 없다. 형제
저장소 `final_project_cs`가 이 저장소를 복사해 만든 하위 프로젝트인데,
basement가 바뀔 때마다 cs가 "지금 몇 버전 기준인지, 최신 대비 뒤처졌는지"
판단할 방법이 없다. Claude와 Codex가 사전 자문에서 합의한 결론:
SemVer + CHANGELOG + git tag를 지금 시작한다(배포 메커니즘은 별도
스트림에서 다룬다 — 이 스트림은 버전 축만 만든다).

## 만들 것

1. **`pyproject.toml`** — `version = "0.1.0"` → `"0.2.0"`. 이유: 이번
   세션에 하위 호환되는 기능이 여럿 늘었다(Composer 쓰기채널 v2/JWT,
   Response Generation & Review Team/DoD-29, `examples/` 분리, 버그
   수정 여러 건) — 계약을 깨는 변경은 없었으므로 minor.

2. **`CHANGELOG.md`**(신규, 저장소 루트) — [Keep a Changelog](https://keepachangelog.com)
   형식. 최소 두 항목:
   - `## [0.1.0]` — 최초 basement 베이스라인이라고만 짧게 적는다(과거를
     전부 복원하려 하지 마라 — 지어내지 않는다. "이 버전 이전 이력은
     git log 를 참조" 라고 명시).
   - `## [0.2.0]` — 이번 세션 변경 사항을 `git log --oneline` 로 실제
     커밋 이력을 읽고 요약한다(추측하지 말고 커밋 메시지를 근거로 삼는다).
     Added/Fixed/Changed 로 분류: Composer 쓰기채널 v2(JWT), Response
     Generation & Review Team(DoD-29), Billing/Technical→`examples/`
     분리, CLASSIFIED 전이 버그 수정 등.

3. **SemVer 판정 기준 문서화** — `wiki/records/handoff/10_도메인_교체_가이드.md`
   맨 위 또는 별도 절에 다음 표를 추가한다(v8 원문은 건드리지 않는다 —
   이건 `wiki/records/handoff/` 계약 문서다):

   | 등급 | 기준 |
   |---|---|
   | patch | 기존 계약을 안 바꾸는 basement 내부 버그 수정 |
   | minor | 기존 계약을 깨지 않는 기능·Port·registry ID 추가 |
   | major | `contracts.py`(`TeamTask`/`TeamResult`/`TeamManifest`) 필수 필드 변경·삭제, Port 인터페이스 변경, registry ID 제거/의미 변경, config schema 파괴적 변경 |

   `app/modules/**`(도메인)·`config/**`·`knowledge/**`·평가 데이터
   변경은 이 SemVer 축과 **별도**임을 명시한다(basement_version 과
   domain_profile_revision 은 다른 축).

## 하지 않을 것

- basement manifest·export 스크립트를 만들지 않는다(별도 스트림
  `S-VERSIONING-02-MANIFEST-EXPORT`가 담당).
- `app/tools`·basement/domain 경계 재분류를 하지 않는다(별도 스트림
  `S-VERSIONING-03-BOUNDARY-TOOLS`가 담당).
- `app/`·`config/`·`tests/` 등 런타임 코드를 건드리지 않는다.
- git tag 는 만들지 마라(사람이 검토 후 커밋에 직접 붙인다).

## 검증

```powershell
python -m pytest -q --ignore=tests/integration/rag
```
버전·CHANGELOG 변경이므로 테스트 결과가 이 스트림 시작 전과 동일해야
한다(파일 변경이 코드 동작에 영향을 주면 안 된다).

## 만들 것 (리포트)

`wiki/records/reports/2026-08-18_S-VERSIONING-01-SEMVER_리포트.md` — 무엇을
버전 0.2.0 에 포함시켰는지 근거(커밋 목록)와 함께 남긴다.
