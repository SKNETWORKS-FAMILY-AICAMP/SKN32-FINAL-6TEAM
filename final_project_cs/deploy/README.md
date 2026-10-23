# guguroute 공개 배포 (Docker)

서버 한 대(WSL2 Docker)에 **DB · API · 상시 작업 일꾼 · 웹**을 올리는 파일 모음이다. 역방향 프록시(Caddy)는 서버에 이미 있는 것을 쓰고, 이 프로젝트는 그 Caddy 에 **사이트 한 블록**만 붙인다.

```
인터넷 → (Cloudflare) → 공유기 → 서버의 Caddy ─┬→ tripilot-web  :3000  (웹앱)
                                               └→ tripilot-api  :8043  (/v1 · /plan · /booking-change · /mcp · /health)
                              tripilot-worker  (되잡기 · 바깥함 일꾼 · 일일 집계 — 밖에서 안 닿는다)
                              tripilot-db      (pgvector — 밖으로 포트를 안 연다)
```

| 파일 | 하는 일 |
|---|---|
| `Dockerfile.api` | API · 일꾼이 쓰는 파이썬 이미지(릴리스 빌드만 — `/composer` · `/admin/reload` 없음) |
| `Dockerfile.web` | Next.js 웹앱 이미지. `NEXT_PUBLIC_*` 는 **빌드할 때** 박힌다 |
| `docker-compose.yml` | 서비스 넷 + 기존 Caddy 네트워크에 붙이는 별칭 |
| `worker.sh` | 상시 작업(`scripts/ops/jobs.py` 의 sweepers · outbox · daily_feedback) 한 컨테이너 |
| `make_server_env.py` | 서버 환경 파일 둘을 만든다 — `.env`(앱 설정 · 새 비밀 5개 · 테넌트 `live`) · `.env.apikeys`(바깥 데이터 소스 키만 옮김). 값을 출력하지 않는다 |
| `export_reference_data.py` | 개발 DB 에서 **기준 데이터만**(장소 · 영업시간 · 정책 지식 · 프롬프트 · 요식 원장) 떠서 SQL 한 파일로. 테넌트 이름은 서버의 `live` 로 바꿔 뜬다(`--as-tenant`) |
| `server_up.sh` | 서버에서: 빌드 → DB → 마이그레이션 → 기준 데이터(비었을 때만) → 전체 기동 |
| `Caddyfile.tripilot` | 기존 Caddy 에 붙일 사이트 블록(공개 경로만 연다) |

## 처음 올리는 순서

1. **이 PC**: `python deploy/make_server_env.py --host <공개 도메인> --proxy-network <Caddy 네트워크> --proxy-cidr <그 대역> --ollama-url <모델 서버> --out <파일>` → 같은 자리에 `.env.apikeys` 도 만들어진다. 둘을 서버 배포 폴더로 복사(권한 600), **이 PC 의 사본은 지운다**. 구글 로그인 값은 자동으로 옮기지 않는다 — 서버 `.env` 에 직접 넣는다(`wiki/operations/google-login-setup.md`).
2. **이 PC**: `python deploy/export_reference_data.py --out reference_data.sql.gz` → 서버로 복사.
3. **이 PC**: `git archive HEAD final_project_cs` 로 소스를 묶어 서버 `src/` 에 푼다(커밋된 것만 — 다시 만들 수 있다). **자료 폴더는 저장소와 같은 구조로 둔다** — 서버 배포 폴더의 `datasets/` 아래에 `mobility/processed`(이동 자료 — 컨테이너가 읽기 전용으로 붙인다) · `activity` · `dining` · `travel` 을 이 PC 의 `datasets/` 와 같은 이름으로 둔다(이 PC 의 `datasets/` 는 git 에 안 올라가므로 따로 복사한다). 이동 자료가 다른 자리에 있으면 `TRIPILOT_MOBILITY_DIR` 로 가리킨다.
4. **서버**: `./server_up.sh`.
5. **DNS**: 공개 도메인이 서버로 오게 한다(주황 구름 프록시 가능).
6. **서버**: 기존 Caddyfile 을 백업 → `Caddyfile.tripilot` 의 `__TRIPILOT_HOST__` 를 바꿔 끝에 붙임 → `caddy validate` → `caddy reload`.
7. 확인: `https://<공개 도메인>/health` 가 `ok`, 웹 첫 화면, 키 발급.

## Cloudflare IP 갱신과 Caddy 복구 (오라클 ARM 서버)
- 같은 Caddy 에 검사용 사이트를 `cloudflare_only` 로 함께 두는 서버(오라클 ARM)는 `update-cloudflare-ips.sh` 가 **매주** Cloudflare 대역을 갱신한다(systemd 타이머 `update-cloudflare-ips.timer`). CI/CD 가 아니라 root 로 손으로 설치한다: `sudo install -m 755 -o root -g root update-cloudflare-ips.sh /usr/local/bin/`
- **2026-10-12 사고**: 갱신 뒤 `systemctl reload caddy` 에서 Caddy 2.6.2 가 `panic: missing cancel error` 로 죽어 서비스가 `failed` 로 멈췄고, 바깥에서는 Cloudflare 521 이 났다. 설정 파일은 `caddy validate` 를 통과한 상태였다. 같은 패닉을 수동 재실행(06:45)에서도 재현했다 — **이 Caddy 에서 reload 는 죽는다**, systemd 는 그래도 "reloaded" 라고 보고한다.
- 그래서 스크립트는 (1) 대역이 **실제로 바뀐 때만** 적용하고(생성 시각 줄은 비교에서 뺀다) (2) 적용은 reload 대신 **restart** 로 하며 (3) 3초 뒤에도 caddy 가 살아 있을 때만 성공으로 본다. restart 때문에 적용 순간에는 몇 초 끊긴다(주 1회).
- 확인: 서버에서 `systemctl is-active caddy` 가 `active`, 바깥에서 `/health` 가 `200`.
- 수동 복구: 설정을 먼저 `sudo caddy validate --config /etc/caddy/Caddyfile` 로 검사한 뒤 `sudo systemctl restart caddy`.

## 환경 파일 둘 · 테넌트 이름
- 이 PC 와 같은 구조다 — `.env`(앱 설정 · 서버에서 새로 만든 비밀 · 구글 로그인 값) · `.env.apikeys`(공공 데이터 · 지도 키만, 키만 따로 갈아 끼우려는 이유가 서버에도 같다). compose 가 둘 다 읽는다(뒤가 이긴다).
- 서버의 테넌트 이름은 **`live`** 다(`ACOP_TENANT_ID`). 개발 PC 는 `demo`. 테넌트 이름이 들어간 값(여행 링크 토큰 등)은 이름이 다르면 서로 안 맞으니, 서버 DB 를 이 PC 의 덤프로 다시 만들 때는 위 `--as-tenant live` 로 떠야 한다.

## 갱신
소스를 다시 풀고(`src/`) `./server_up.sh`. 마이그레이션은 재실행 안전하고 DB 볼륨(`tripilot_pg`)은 그대로다.

## 같은 서버의 다른 프로젝트와 겹치지 않게
- **이름으로 나눈다, 포트로 나누지 않는다.** 두 프로젝트가 같은 80/443 을 쓰되 기존 Caddy 가 **접속한 도메인 이름**을 보고 갈라 보낸다(`Caddyfile.tripilot` 이 한 블록). 주소에 포트 번호가 안 붙는다.
- 이 구성은 **호스트 포트를 하나도 열지 않는다**(`ports:` 없음) — 컨테이너 안 8043·3000·5432 는 각자의 네트워크 안에서만 닿는다. 다른 프로젝트의 같은 번호와 안 부딪힌다.
- 서비스 이름에 `tripilot-` 을 붙여 공유 네트워크(`proxy`)에서 이름이 겹치지 않게 했고, DB 는 `internal` 네트워크에만 둔다.
- 모델 서버(Ollama)는 호스트의 중계 주소로 부른다. 그 중계가 끊기면(WSL 어댑터가 다시 만들어진 뒤 리스너를 잃는다) 호스트에서 `Restart-Service iphlpsvc`.

## 자동 반영 (팀 저장소의 브랜치를 따라간다)
서버가 **5분마다** 정해 둔 저장소·브랜치에 새 커밋이 있는지 보고, 있으면 이미지를 다시 만들어 반영한다(`auto_deploy.sh` + systemd 타이머).

| 단계 | 하는 일 | 실패하면 |
|---|---|---|
| 확인 | 새 커밋이 있나. 그 커밋에 `final_project_cs/deploy/` 가 **없으면 아무것도 안 한다**(배포 구성이 아직 안 합쳐진 브랜치) | 기다린다 |
| 건너뜀 | 배포에 쓰이는 폴더(app · config · prompts · scripts · deploy · frontend/apps/web · requirements)가 **같으면** 다시 빌드하지 않는다(문서만 바뀐 커밋) | — |
| 빌드 | 새 이미지를 **커밋 해시 이름으로** 만든다 | 실행 중인 것은 그대로. 그 커밋은 다시 시도하지 않는다 |
| 마이그레이션 | 앞으로 가기뿐 | 실행 중인 것은 그대로 |
| 반영 | 새 이미지로 교체하고 건강해질 때까지 기다린 뒤 **30초 더 지켜본다**(재시작 0회 · 컨테이너 4개) | **이전 이미지로 되돌린다** |
| 고객 공지 | 빌드 시작 · DB 이주 · 바꾸기 · 끝 · 실패를 `state/service-notice/notice.json` 에 적는다(`deploy_notice.py`). 고객 공지 띠에 정해 둔 문구로 뜬다(D-CS-019) | 경고만 남기고 배포는 계속한다 |
| 정리 | 앱·운영 웹앱 이미지는 최근 3개 + **달마다 하나**(그달 마지막으로 반영에 성공한 판, `keep-YYYY-MM` 이름표), 복구용 이미지(`tripilot-recovery`)는 최신 2세트만. 규칙: `image_retention.py` | 경고만 남긴다(반영은 이미 끝남) |

- **무엇을 따라가나**: 서버의 `autodeploy.conf`(`DEPLOY_REPO` · `DEPLOY_BRANCH`)에 있다 — 서버에만 둔다. 바꾸려면 그 파일만 고친다.
- **기록**: 서버의 `deploy.log`. 상태: `state/`(`current_tag` · `deployed_sha` · `bad_sha`).
- **멈추기**: `systemctl disable --now tripilot-autodeploy.timer`. 한 번만 돌리기: `systemctl start tripilot-autodeploy.service`.
- **설치**(서버, 한 번): `auto_deploy.sh` 를 배포 폴더에 두고(`chmod +x`), `tripilot-autodeploy.service` · `.timer` 를 `/etc/systemd/system/` 에 복사 → `systemctl daemon-reload` → `systemctl enable --now tripilot-autodeploy.timer`.
- ★**마이그레이션은 되돌리지 않는다.** 되돌린 이전 이미지가 새 표 구조를 견딘다는 가정이다 — 표를 지우거나 칸 이름을 바꾸는 파괴적 마이그레이션은 이 방식에 맞지 않는다.
- ★**브랜치의 코드가 곧 공개 서비스다.** 건강 검사로 못 걸러내는 기능 결함은 그대로 올라간다 — 확인이 필요한 브랜치는 따라가는 브랜치를 따로 둔다.
- ★서버는 저장소를 **읽기만** 한다(공개 저장소라 인증이 없다). 비공개가 되면 읽기 전용 배포 키를 서버에 둬야 한다.

## 월별 보존 판으로 되돌리기 (복원)
달마다 하나는 `keep-YYYY-MM` 이름표로 남는다(`tripilot-api` · `tripilot-web` · `tripilot-admin`). 문제가 생기면 그 판으로 되돌린다.

1. **있는 판 보기**: `docker images 'tripilot-*' --format '{{.Repository}}:{{.Tag}}' | grep keep-`
2. **먼저 시험하기 (운영을 건드리지 않는다)**: `python3 deploy/restore_check.py --old-image tripilot-api:keep-YYYY-MM --new-image tripilot-api:local --mobility-dir <이동 자료 폴더>`
   - 바깥과 연결되지 않는 임시 네트워크에 빈 DB 를 만들고, 최신 이미지의 마이그레이션으로 「지금의 DB 구조」를 만든 뒤 옛 이미지의 마이그레이션 · API 기동 · `/health` · 로그 오류를 확인하고 임시 자원(컨테이너 · 네트워크)을 **항상** 지운다. 운영 DB 와 운영 `.env` 는 읽지 않는다. 임시 DB 는 이 시험이 도는 동안에만 있다.
   - **설정 이름은 걸림돌이 아니다(시험으로 확인)**: 설정은 `extra="forbid"` 라서 `.env` **파일**에서 읽은 모르는 이름은 거부하지만, 운영은 compose `env_file` 로 값을 컨테이너 **환경변수**에 넣고 `.env` 는 이미지에 없다(`.dockerignore`). 환경변수로 들어온 모르는 이름은 무시되므로 최신 판에만 있는 설정(2026-10-14: `ACOP_JUSO_COORD_API_KEY` · `ACOP_JUSO_SEARCH_API_KEY`)이 운영 환경 파일에 있어도 옛 이미지는 켜진다. 도구가 이를 직접 재현하고(통과 항목), 파일로 읽을 때의 차이는 참고 줄로 알려 준다. 배포 방식을 `.env` 파일 마운트로 바꾸면 이 점을 다시 본다.
3. **되돌리기 (운영 반영과 같은 안전 절차를 쓴다)**: 자동 반영이 끼어들지 않게 `systemctl stop tripilot-autodeploy.timer` 를 하고, 배포 폴더에서
   ```
   export TRIPILOT_SRC=./repo/final_project_cs
   D=state/migration-safety-ffffffffff-$(date +%s)        # 이름 규칙을 지키면 image_retention 이 나중에 치운다
   TRIPILOT_TAG=<지금 실행 중인 판>  python3 repo/final_project_cs/deploy/migration_safe_deploy.py snapshot --state-dir $D
   TRIPILOT_TAG=keep-YYYY-MM         python3 repo/final_project_cs/deploy/migration_safe_deploy.py check    --state-dir $D
   TRIPILOT_TAG=keep-YYYY-MM         python3 repo/final_project_cs/deploy/migration_safe_deploy.py rollout  --state-dir $D --timeout 240 --settle 30
   ```
   `rollout` 은 새로 띄운 것이 건강하지 않거나 재시작하면 스스로 직전 이미지(이미지 ID 고정)로 복구한다. DB 는 되돌리지 않는다 — 마이그레이션이 앞으로만 가므로(위 자동 반영 표) 옛 이미지가 새 표 구조를 견디는지가 2번이 확인하는 핵심이다.
   - **3번은 2026-10-14 에 운영(x600 서버)에서 시험했다**: 현재 → 직전 판 → `keep-2026-10` → 오래된 판 → 현재 복귀를 위 절차로 네 번 전환해 모두 통과했다(전환마다 1~3분 끊김, 환경 파일은 건드리지 않았다).
4. **최신 판으로 돌아오기**: 같은 절차를 `TRIPILOT_TAG=<state/current_tag 의 값>` 으로 한 번 더 하고 `systemctl start tripilot-autodeploy.timer`. 배포 버전 표시(`ACOP_DEPLOYMENT_VERSION`)가 `keep-…` 로 남으면 다음 자동 반영의 사전 검사(실행 중 구성 일치)에 걸릴 수 있다고 보고 복귀시킨다 — 이 걸림 자체는 확인하지 않았고, 시험에서는 복귀 뒤 사전 검사가 통과했다.

## 알아둘 것
- **DB 는 서버에 하나가 정본이다.** 개발 PC 의 DB 와 합치지 않는다 — 서버에는 사용자 데이터를 안 가져갔고, 거기 쌓이는 것은 서버 것이다.
- **모델은 서버의 Ollama**(해석·일정 짚기는 우리 데이터로 가르친 E4B `tripilot-pointer:e4b-ft`, 임베딩은 `bge-m3`)를 쓴다 — 요금이 안 나간다. 코드 기본값도 `tripilot-pointer:e4b-ft` 이고(`ACOP_OLLAMA_MODEL`, `make_server_env.py` 가 같은 값을 적는다), 문맥 길이 `ACOP_OLLAMA_NUM_CTX=8192` 와 함께여야 한다. 컨테이너가 그 Ollama 에 닿는 길은 서버 쪽 설정이다.
- **사람 확인(Turnstile)**: `ACOP_ENV=prod` 는 사람 확인 키가 없으면 서버가 안 켜진다. 키가 없는 동안 `ACOP_ENV=public` 으로 두면 확인 없이 키 발급이 열린다(주소별 일일 한도만 지킨다). 키를 받으면 `ACOP_TURNSTILE_SECRET` · `NEXT_PUBLIC_TURNSTILE_SITE_KEY` 를 넣고 `prod` 로 올린다.
- 이 폴더의 파일에는 **주소 · 계정 · 비밀을 적지 않는다.** 값은 서버 `.env` · `.env.apikeys` · 서버의 Caddyfile 에만 있다.
