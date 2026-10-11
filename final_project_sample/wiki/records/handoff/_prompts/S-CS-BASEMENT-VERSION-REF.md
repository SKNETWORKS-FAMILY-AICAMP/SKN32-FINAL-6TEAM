# S-CS-BASEMENT-VERSION-REF — final_project_cs 쪽 basement 버전 참조 기록

## 배경

`final_project_sample`(basement)이 이번 세션에 SemVer/CHANGELOG/manifest
체계를 도입했다(`CHANGELOG.md`, `scripts/export_basement.py`,
`wiki/records/handoff/15_basement_버전_배포_계약.md`). 지금 basement 버전은
`0.2.0`, 커밋 `92b4c438a8f3bce1a5c65a54b38285d150020225`이고, 이 상태로
`python -m scripts.export_basement`를 실행해 **이미 최신 manifest 를
`final_project_sample/dist/basement/manifest.json`에 만들어 뒀다**(파일
목록·SHA-256 포함).

`final_project_cs`(형제 디렉터리)는 이 basement 를 복사해 만든 실제
프로젝트다. `final_project_cs`는 어떤 basement 버전을 기준으로 만들어졌는지
기록한 적이 **한 번도 없다.** 이번 스트림의 목적은 그 첫 기록을 남기고,
지금 cs 의 basement 파일들이 sample 의 manifest 와 실제로 얼마나
다른지(로컬 drift)를 사실대로 보고하는 것이다.

## ★중요 — git 저장소 경계에 대한 사실 확인

`final_project_cs`는 **자체 `.git` 저장소가 없다**(안에 빈 `.git/`
디렉터리가 있지만 내용이 비어 있어 git 이 인식하지 않는다). git 명령을
그 디렉터리에서 실행하면 위쪽 `final_workspace/.git`(원격
`https://github.com/roroblack/A-COP.git`, 여러 브랜치로 하위 프로젝트를
매핑하는 별도 워크플로가 있음)으로 해석된다. **그 저장소에는 지금 이
스트림과 무관한 변경이 이미 대량으로 쌓여 있다**(계획서 삭제, 다른
세션의 진행 중인 작업 등). **이 스트림은 어떤 git 명령도 실행하지
않는다** — add·commit·push 전부 금지. 파일만 만들고 끝낸다. 커밋은
사람(Claude)이 검토 후 별도로 판단한다.

## 만들 것 — `final_project_cs/` 안에만

1. **`final_project_cs/wiki/records/manuals/basement_version.json`**(신규) —
   `final_project_sample/dist/basement/manifest.json`(방금 생성됨, 읽기만
   해라 — 그 저장소의 다른 어떤 파일도 건드리지 마라)을 읽어 다음을 기록한다:

   ```json
   {
     "basement_version": "<manifest.basement_version>",
     "source_commit": "<manifest.source_commit>",
     "source_repo": "https://github.com/roroblack/A-COP",
     "source_branch": "project-final_project_sample",
     "manifest_recorded_at": "<manifest.generated_at>",
     "applied_at": "<이 스트림 실행 시각, UTC ISO8601>",
     "recorded_by": "S-CS-BASEMENT-VERSION-REF"
   }
   ```

2. **드리프트 리포트** — `wiki/records/reports/2026-08-18_S-CS-BASEMENT-VERSION-REF_리포트.md`
   에 다음을 실측으로 남긴다(추측 금지):
   - manifest 의 `files[]` 목록 파일마다, `final_project_cs/` 안의 같은
     상대경로 파일이 **존재하는지, 존재한다면 SHA-256 이 일치하는지**를
     직접 비교해라(파이썬 스크립트를 짜서 실행하되, 저장소에 남기지 않아도
     된다 — 일회성 비교면 충분하다. 남기고 싶으면
     `wiki/records/manuals/basement_drift_check.py` 로 만들어도 된다, 선택).
   - 결과를 세 그룹으로 나눠 리포트에 표로 적어라: **일치**(같은 내용),
     **존재하지만 다름**(cs 가 로컬에서 손댔거나 오래된 버전),
     **cs 에 파일 자체가 없음**.
   - `final_project_cs` 자신의 `app/core`·`app/domain`·`app/application`·
     `app/infrastructure`·`app/presentation` 아래에, sample 의 manifest
     에는 없는 **cs 고유 파일**이 있는지도 확인해서 목록으로 남겨라(있으면
     "cs 가 basement 를 확장했다"는 뜻이니 결함이 아니라 사실로만 적는다).

3. **`final_project_cs/wiki/records/handoff/`**(cs 자신의 번호 체계를 따라 다음
   빈 번호로 — `wiki/records/handoff/`를 먼저 나열해서 다음 번호를 확인해라)에
   짧은 계약 문서 — `final_project_sample/wiki/records/handoff/15_basement_버전_배포_계약.md`
   의 존재와 `basement_version.json` 을 어떻게 갱신하는지만 인용(복사
   아님)해서 1페이지로 적는다.

## 하지 않을 것

- **git 명령 전부 금지**(위 참고).
- `final_project_cs` 의 `app/core`·`domain`·`application`·`infrastructure`·
  `presentation` 파일을 **하나도 고치지 않는다** — 이번 스트림은 기록과
  보고만 한다. 드리프트가 발견돼도 자동으로 덮어쓰거나 고치지 않는다.
- `final_project_sample/` 안의 어떤 파일도 고치지 않는다(manifest 는
  이미 만들어 뒀으니 읽기만 해라).
- `final_workspace/` 최상위나 다른 형제 디렉터리(`final_project_ui` 등)는
  건드리지 않는다.

## 검증

파일 비교 스크립트를 실제로 실행한 원문 출력(몇 개 일치/다름/없음인지
개수)을 리포트에 그대로 인용해라. 실행 안 하고 추측으로 채우면 안 된다.
