# P12 — Composer UI 고도화 + 대상 저장소의 `/ui/composer` 완전 제거

## 배경

사용자가 지적: "Composer가 왜 CS project의 고객용 UI에 들어가 있어?" 확인 결과 —

`final_project_cs`·`final_project_sample` 둘 다 `app/presentation/ui/composer.py`
(module/Team/Port를 편집하는 HTML 폼)가 **인증 없이** `/ui/composer`에 마운트돼
있었고, 고객이 접근 가능한 것과 같은 앱·포트에서 서비스되고 있었다. 실측:
`grep -n "Depends|require_scope"` 결과 0건. `final_project_sample`의
`theme.py` `NAV`(사실상 tenant nav)에도 "Composer" 링크가 박혀 있었다(단, cs쪽은
`composer_ui`가 진짜로 tenant 페이지 nav에도 노출돼 있었고, sample쪽은 nav
분리는 돼 있었으나 composer.py가 어차피 default `NAV`로 렌더돼 결과는 같았다).

## 사용자 지시와 절차

1. 완전히 제거하기 전에 원본을 `final_project_ui` 안에 백업
2. `final_project_ui`의 Composer 화면이 원본과 기능·UI 면에서 동등한지 확인하고, 아니면 반영
3. 그 다음에야 대상 저장소(cs, 그리고 basement인 sample도)에서 완전히 제거

## 1. 백업

`docs/backup/composer_ui_원본_2026-08-18/`에 `final_project_sample`·`final_project_cs`의
`composer.py`(+ sample의 `theme.py`) 원본을 그대로 보존. cs쪽 `composer.py`는
구식(revision 충돌 미확인 등 결함 있던 버전)이라 sample쪽을 UI 설계 기준으로 삼았다.

## 2. `final_project_ui`의 Composer 화면 고도화

기존(1차 구현)은 raw JSON textarea 하나였다. 원본과 비교해 부족하다는 지적을 받고 재작성:

- 모듈 체크박스, Port 입력(텍스트 — 대상 `PortConfig`의 enum 선택지를 가져오지
  않는다, `CLAUDE.md` §0.2 때문에 스키마 복제 금지), Team 표(행 추가/제거, 저장
  전 재렌더링)
- ★**구조도**(`flow()`) — 지금 읽은 config 값으로 매 요청마다 다시 그리는
  실행 순서 다이어그램. 원본의 정적 서술은 이 콘솔이 다시 썼고(대상 코드 비import),
  켜짐/꺼짐 상태만 실제 config를 반영한다
- 컴포넌트(고정 인프라) 참고 목록 — 정적 텍스트, 실시간 검증 안 됨을 명시
- 원본 JSON 대조용 뷰(collapsed)

`console/web.py`에 collapsible-card·flow/node CSS를 새로 추가(대상 `theme.py`를
복사하지 않고 이 콘솔 자체 스타일로 다시 그림).

## 3. 실연결로 발견한 것 — v2 인증이 이미 배포돼 있었다

`final_project_sample`의 실서버를 다시 붙여보니 **다른 세션이 그 사이
`docs/handoff/13_Composer_쓰기채널_계약.md` v2(JWT + scope 3분리)를 이미
구현**해 놨다(`app/presentation/composer_auth.py`, `POST /auth/token`,
`CLAUDE.md` 자체 기록: "완료 2026-08-18, Codex"). P11 보고서가 "v2 아직 없음"
이라 적었던 건 이제 틀렸다 — `CLAUDE.md` §0.3 예외 조항을 이 사실에 맞게
갱신했다. `/auth/token`으로 JWT를 발급받아 `CONSOLE_COMPOSER_TOKEN`에 넣어
실제 validate 호출까지 성공 확인.

★부수적으로 `uvicorn --reload`가 이 저장소에서 라우트를 일부 누락한 채로 뜬
증상을 발견(`/auth/token`이 openapi에 안 잡힘, `--reload` 없이 새로 띄우면
정상) — `final_project_ui` 쪽 결함이 아니라 로컬 개발서버 재현 이슈라 기록만
남긴다.

## 4. `final_project_cs`에서 제거

- `app/presentation/ui/composer.py` 삭제
- `app/presentation/ui/__init__.py` — `composer_router` import·마운트 제거
- `app/composition.py` — `_MODULE_IMPLEMENTATIONS`에서 `composer_ui` 제거
- `app/presentation/ui/theme.py`·`routes.py` — nav의 `/ui/composer` 링크 제거
  (theme.py의 단일 `NAV`에 하드코딩돼 있었다 — 이게 "고객용 UI에 Composer가
  보인다"는 사용자 지적의 직접 증거)
- `config/project.yaml`에서 `composer_ui` 모듈 선언 제거
- 테스트: `test_composer_ui.py`·`test_composer_structure.py` 삭제,
  `test_root_landing.py`·`test_project_composition.py` 갱신, 회귀 방지 테스트
  `test_composer_ui_is_no_longer_a_registered_module` 추가
- 문서: `docs/handoff/09`(폐기 배너)·`08`·`10`·`release_checklist.md`·`CLAUDE.md` 갱신
- **검증**: `281 passed, 2 deselected`

## 5. `final_project_sample`(basement)에서도 동일하게 제거

기존 `docs/handoff/09`·`app/presentation/ui/__init__.py`는 "Composer는 이
프로젝트 자신의 설정을 쓰는 기능이라 read-only 외부 프로그램으로 옮길 수
없다"고 명시적으로 판단해 남겨 뒀던 것이었다 — 그 판단은 인증된 쓰기 채널
(§계약 13)이 생기기 전 기준이었고, 이제 `final_project_ui`가 그 채널로
같은 일을 하므로 전제가 사라졌다.

- 동일하게 `composer.py` 삭제, `__init__.py`·`composition.py`·`theme.py`
  (`CONSOLE_NAV` 전체가 죽은 참조였다 — 같이 제거)·`routes.py` 갱신
- `config/project.yaml`에서 `composer_ui` 제거
- 테스트: `test_composer_ui.py`·`test_composer_structure.py` 삭제,
  `test_root_landing.py`·`test_project_composition.py`·`test_audience_boundary.py` 갱신
- `test_composer_write_channel.py` — `composer_ui` 토글을 예시로 쓰던 테스트를
  `ops_ui` 토글 기준으로 재작성(핵심 검사 대상은 그대로: HTML 화면이 없어도
  인증된 API는 산다)
- 문서: `docs/handoff/09`(폐기 배너)·`08`·`release_checklist.md`·`CLAUDE.md` 갱신
- **검증**: `339 passed, 1 deselected`

## 6. 실apply 재검증 (별도 요청 — "다른 세션 안 겹칠 때")

작업 착수 전 `final_project_sample` 파일 변경 이력을 확인해 최근 10분·2.5시간
안에 활동 없음을 확인한 뒤 진행:

- `modules.a2a_executor.enabled`를 `false→true`로 실제 apply(원격 파일 진짜 변경
  확인) → `false`로 재apply(되돌림)
- revision이 되돌리기 전후 정확히 일치(`7a5d44da9ce8`) — 내용 해시 기반이라
  왕복이 완전히 무손실이었음을 증명
- 대상의 `.yaml.bak` 안전장치도 실제로 생성됨을 확인

## 남은 것

- ~~`final_project_ui`가 `/auth/token`을 자동으로 호출해 JWT를 스스로 갱신하는
  기능은 없다~~ → **완료** — `console/composer.py`가 이제 동작별 최소 scope로
  매번 단명 JWT를 자동 발급받는다(`CONSOLE_COMPOSER_ISSUER_SECRET`만 넣으면 됨).
- ~~`final_project_cs`의 v2 JWT 인증 상태 확인 안 됨~~ → **완료** — cs에도 v2
  Composer 쓰기 채널을 이식했다(`S-COMPOSER-WRITE-CHANNEL-PORT`, 2026-08-18).
- `final_project_cs`·`final_project_sample`의 v2 JWT 인증 상태가 서로 다를 수
  있다(cs는 이번에 안 건드림, 확인 안 함) — 대상마다 토큰 발급 방식이 다를 수
  있음을 유의.
