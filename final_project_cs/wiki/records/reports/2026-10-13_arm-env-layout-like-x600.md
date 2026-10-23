---
type: report
title: Oracle ARM 환경 파일을 x600 서버와 같은 두 파일 구조로 맞춤
description: app.env·control.env 를 .env·.env.apikeys 로 나눈 저장소 수정과 오라클 서버 적용
status: draft
domain: travel
---

# Oracle ARM 환경 파일을 x600 서버와 같은 두 파일 구조로 맞춤

`[2026-10-13 사용자 지시]` 오라클 서버(dr-a2)의 cs 프로젝트 서버 환경 파일을 x600 서버와 같은 구조로 맞춘다 — `.env`(설정·비밀값) + `.env.apikeys`(외부 API 키·호출 한도). 저장소 쪽 수정과 오라클 서버 적용을 마쳤다(오라클 서버 적용은 처음에 자동 승인 심사에서 막혔고, 사용자가 「오라클 서버 적용 허용」이라고 해 다시 실행했다).

| 할 일 | 상태 | 진행 |
|---|---|---|
| 저장소 배포 도구 수정(`compose.yml` · `deploy.py`) | 끝 | 2/2 = 100% |
| 키 템플릿에 SerpApi 자리 추가 | 필요 없음 — 원격 role-manager 에 이미 있다 | 0/0 |
| 오라클 서버 시험 실행(쓰지 않고 결과만) | 끝 | 1/1 = 100% |
| 오라클 서버 적용 | 끝 | 1/1 = 100% |
| 오라클 서버 api·worker 컨테이너 새로 띄우기 | 안 함 | 0/1 = 0% |

## 왜 바꾸나

옛 구조(`control/app.env` + `control/control.env`)는 2026-10-09 Codex 가 처음 설치하면서 정했다. 사용자 결정 기록은 루트·cs 결정 문서에서 찾지 못했다. 이 구조에서는 저장소의 키 맞춤 스크립트(`scripts/sync_apikeys.py`)가 적용되지 않고, 10-10 장소 추천 실패의 원인 중 하나도 검색 키 누락이었다([복구 기록](2026-10-10_0535_arm-place-source-recovery.md)).

## 바뀌는 것

| 옛 파일 | 새 파일 | 담는 것 |
|---|---|---|
| `control.env`(compose 변수 6개) + `app.env` 의 설정 24개 | `control/.env` | DB 비밀번호·모델 주소 등 compose 변수, 앱 설정·서명 비밀값 |
| `app.env` 의 키 4개 | `control/.env.apikeys` | 카카오·관광공사 키, 관광공사 하루 한도, SerpApi 키 |

- 키와 설정을 가르는 기준은 저장소 [`.env.apikeys.example`](../../../.env.apikeys.example) 의 이름 목록이다. 원격 role-manager 의 템플릿에는 `ACOP_SERPAPI_API_KEY` 와 호출 한도 `ACOP_RATE_SERPAPI_PER_MONTH`(250) · `ACOP_RATE_SERPAPI_PER_DAY`(8)가 이미 있다. 한도 두 줄은 오라클 서버 `.env.apikeys` 에 넣지 않았다 — 비어 있으면 앱 기본값을 쓴다.
- `compose.yml` 의 api·worker 는 `env_file: [.env, .env.apikeys]` 를 읽는다(x600 서버와 같다). `deploy.py` 는 `--env-file control/.env` 로 compose 변수를 읽는다.
- 오라클 서버에만 있는 스크립트 셋(`pin_model.py` · `fix_env.py` · `bootstrap.py`)도 새 이름을 쓰게 고친다. `bootstrap.py` 는 처음 설치 때 빈 `.env.apikeys` 를 만든다.
- 고치지 않는 것: `incoming/` 아래의 지난 일회성 수리 스크립트(10-10~10-12, 모두 실행이 끝난 기록). 다시 돌리면 옛 이름을 찾다 실패하므로 재사용하지 않는다.

## 시험 실행 결과 (오라클 서버, 쓰지 않음)

`[실측 2026-10-13]` 배포 잠금을 잡고 현재 실행판(`6866c5960357`)으로 `docker compose config` 를 옛 구조·새 구조 둘 다 풀어 컨테이너가 받는 값을 해시로 비교했다.

- api·worker 의 `ACOP_` 설정 30개: 값 전부 같다.
- 다른 점: api·worker 가 compose 변수 6개(`DB_PASSWORD` · `CHAT_URL` · `EMBED_URL` · `MOBILITY_DIR` · `CHAT_ID` · `EMBED_ID`)를 환경 변수로도 받게 된다. x600 서버도 `.env` 의 compose 변수를 같은 방식으로 컨테이너에 넘긴다. 앱은 `ACOP_` 이름만 읽는다.
- db · model-adapter · web: 차이 없음.

## 오라클 서버 적용 방법

스크립트: [`deploy/arm/migrate_env_layout_20261013.py`](../../../deploy/arm/migrate_env_layout_20261013.py). 배포 잠금을 잡고, `control/_backup/<날짜>_env_layout_like_x600/` 에 옛 파일을 백업한 뒤 새 두 파일을 쓰고 스크립트 다섯 개를 고친다. 옛 `app.env`·`control.env` 는 백업 폴더에만 남긴다. 컨테이너는 건드리지 않는다.

- 인자 1: `dry`(쓰지 않음) 또는 `apply`
- 인자 2: 키 이름 목록(저장소 `.env.apikeys.example` 의 `ACOP_` 이름들, 공백 구분)

적용 뒤 SerpApi 키가 앱에 들어가려면 배포 잠금을 잡은 상태에서 api·worker 만 다시 띄운다(`docker compose --env-file .env -f compose.yml up -d --no-deps api worker`). `[정정 2026-10-13]` 처음에 「SerpApi 를 부르는 코드가 없다」고 적었으나, 그것은 이 PC 작업 폴더(원격보다 16커밋 뒤)만 검색한 결과였다. 원격 role-manager 에는 숙소 · 항공 SerpApi 호출 코드가 있다. 오라클 서버는 develop 을 따르므로, 그 코드가 develop 에 들어가 자동 배포될 때 새 컨테이너가 키를 읽는다.

## 적용 결과 (오라클 서버)

`[실측 2026-10-13 10:47 서버 시각]` 배포 잠금을 잡고 적용했다. 백업은 오라클 서버 `control/_backup/2026-10-13_1047_env_layout_like_x600/`(옛 `app.env`·`control.env`·고친 스크립트 원본·전후 비교 `fingerprint.json`).

- `control/.env`(root, 600) · `control/.env.apikeys`(root, 600, 키 4개). 옛 두 파일은 `control/` 에서 빠지고 백업에만 있다.
- 고친 스크립트 4개 파이썬 문법 검사 통과, `docker compose --env-file .env -f compose.yml config` 통과.
- 실행 중인 컨테이너는 다시 띄우지 않았다 — 5개 모두 실행 중, api `/health` 200 · 웹 200. 다음 자동 배포(새 develop 커밋)나 api·worker 재기동 때 SerpApi 키가 앱에 들어간다.

## 남은 한계

- 저장소 `deploy/arm/test_deploy.py` 는 Linux 전용(`fcntl`)이라 이 PC(Windows)에서 돌리지 않았다. 바꾼 것은 파일 이름 문자열뿐이다.
- 저장소 `deploy/arm/compose.yml`·`deploy.py` 와 오라클 서버 `control/` 의 같은 이름 파일은 원래부터 내용이 다르다(서버 쪽이 진단 볼륨·검색 자료 준비 단계를 더 가졌다). 이번에는 환경 파일 줄만 각각 고쳤고 둘을 맞추지 않았다.
- 백업: 저장소 [`deploy/arm/_backup/2026-10-13_1926_env_layout_like_x600/`](../../../deploy/arm/_backup/2026-10-13_1926_env_layout_like_x600/) · [`wiki/operations/_backup/2026-10-13_1927_env_layout_like_x600/`](../../operations/_backup/2026-10-13_1927_env_layout_like_x600/).
