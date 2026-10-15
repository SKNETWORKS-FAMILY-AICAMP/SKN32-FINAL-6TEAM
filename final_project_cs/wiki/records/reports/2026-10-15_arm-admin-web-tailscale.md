---
type: report
title: 오라클 서버 develop 배포에 관리자웹앱 · Tailscale 추가 — 2026-10-15
description: 관리자웹앱을 고객 웹·API 와 같은 자동 배포 회차에 넣고, 팀원이 Tailscale 로만 들어오게 한 설치 기록과 확인 결과
status: draft
domain: travel
---

# 오라클 서버 develop 배포에 관리자웹앱 · Tailscale 추가 — 2026-10-15

`[2026-10-15 사용자 지시]` 「오라클 서버 develop 배포에 관리자웹앱(127.0.0.1:3300)을 추가하고 Tailscale 을 깔아 팀원이 Tailscale 로만 접속하게」 · 「관리자웹앱도 알아서 CD 처리되게 서비스 서버랑 똑같이」. x600 서버와는 잇지 않는다(오라클 서버의 자체 DB · 고객 API 를 쓴다).

## 바꾼 것

| 무엇 | 내용 |
|---|---|
| `deploy/arm/compose.yml` | `admin` 서비스 추가 — host 네트워크, `ADMIN_HOST=127.0.0.1`, 운영 API → 고객 API `127.0.0.1:8043`, `.env.admin` 은 없어도 기동(`required: false`), 1GiB · 0.3코어 |
| `deploy/arm/deploy.py` | 소스에 `frontend/apps/admin` 포함 · API/웹 다음 관리자웹앱 빌드(bake `target:api`) · 기동 대기·건강 검사(8070 `/health` · 3300 `/`, 컨테이너 6개) · 실패 복구 · 이미지 정리 대상에 추가. 실행기에 `ADMIN_HOST` 가 없는 SHA 는 관리자웹앱을 만들지 않고, 그런 판으로 되돌릴 때는 관리자웹앱만 멈춘다 |
| `deploy/admin_runner.py` | 관리자웹앱 받는 주소를 `ADMIN_HOST` 로 고를 수 있게(기본 `0.0.0.0` — x600 서버 동작은 그대로) |
| `deploy/arm/admin_env.py` · `admin_env.sh` | `control/.env.admin` 의 운영자 계정 넣기·빼기·목록, 고객 API 열쇠 넣기. 값은 홑따옴표로 써서 해시의 `$` 를 Compose 가 변수로 읽지 않게 한다. 비밀값은 화면에 찍지 않는다 |
| 시험 | `test_deploy.py` 4개 추가(관리자웹앱 기동·검사 · 옛 판 되돌림 · bake 기반 · 건강 검사 포트) · `test_admin_env.py` 3개 |

## 오라클 서버에서 한 일 `[실측 2026-10-15]`

- 바꾼 배포 파일을 기계 안 `control/` 에 설치했다. 원본은 `control/_backup/2026-10-15_admin-cd/`(compose.yml · deploy.py). develop 판 compose 가 이미 갖고 있던 진단 저장 볼륨(`diagnostics`)도 같이 들어왔다 — 그동안 기계 안 사본이 develop 보다 뒤였다.
- 현재 develop 판(386973a45)으로 관리자웹앱 이미지를 자동 배포와 같은 잠금 아래에서 만들었다(arm64 · 2.14GB · 빌드 약 6분).
- 고객 API 열쇠 3개(`action:approve` · `delegation:read` · `delegation:write`)를 기계 안 비밀값으로 만들어 `.env.admin` 에 넣었다(값은 아무 데도 출력하지 않았다).
- Tailscale 1.104.1 을 공식 패키지 저장소로 설치했다. 기계 이름 `tripilot-admin`, 서버 DNS 는 바꾸지 않게(`--accept-dns=false`).

## 확인 `[실측 2026-10-15]`

| 확인 | 결과 |
|---|---|
| 배포 도구 단위 시험(오라클 서버, Python 3.14) | 10/10 통과 |
| 받는 주소 | 3300 · 8070 모두 `127.0.0.1` 에서만 |
| 관리자웹앱 `/` · 운영 API `/health` · `/admin/api/session` | 200 · 200 · 200(`configured:false` — 계정 0개라 정상) |
| 고객 API 가 열쇠를 받는지 | 맞는 열쇠 200 · 틀린 열쇠 401 |
| 컨테이너 상태 · 메모리 | admin healthy · 134MiB / 1GiB |
| 바깥에서 | 서버 주소 `:3300` 연결 시간 초과 · 공개 주소 `/admin/api/session` 404(관리자 경로 없음) |
| Tailscale 로그인 · `serve` 연결(사용자 로그인 뒤) | `tripilot-admin` 연결됨, `tailscale serve --bg --http=3300 http://127.0.0.1:3300` — tailscaled 가 Tailscale 망 주소에서만 3300 을 받는다 |
| Tailscale 망 기기 이름으로 `/` · `/admin/api/session` | 200 · 200 (숫자 주소로는 404 — 이름으로 온 요청만 받는다). 공개 주소 :3300 은 여전히 시간 초과 |

## 안 한 것 · 남은 것

- **develop 반영 전**: 위 코드는 develop 에 아직 없다. 그동안 새 develop SHA 가 오면 그 판에는 관리자웹앱이 만들어지지 않고(실행기에 `ADMIN_HOST` 없음) 관리자웹앱만 멈춘다 — 고객 웹 · API 는 평소대로 배포된다. 반영되면 다음 회차부터 자동으로 함께 만든다.
- **자동 배포 회차로 관리자웹앱을 만든 것은 아직 확인하지 못했다**(이번 이미지는 같은 함수를 손으로 불러 만들었다). develop 반영 뒤 첫 회차에서 확인한다.
- Tailscale 로그인 · `serve` 연결은 2026-10-15 끝냈다. 팀원 공유 · 운영자 계정은 [따라 하기](../../operations/arm-admin-tailscale.md)의 사람 손 작업이다.
- 팀원이 실제로 들어와 로그인해 본 확인은 없다.
- x600 서버의 관리자웹앱은 여전히 손으로 올린다(`deploy/admin_up.sh`) — 이번 범위가 아니다.
