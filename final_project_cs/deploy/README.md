# triPilot 공개 배포 (Docker)

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
| 정리 | 이전 이미지는 최근 3개만 | — |

- **무엇을 따라가나**: 서버의 `autodeploy.conf`(`DEPLOY_REPO` · `DEPLOY_BRANCH`)에 있다 — 서버에만 둔다. 바꾸려면 그 파일만 고친다.
- **기록**: 서버의 `deploy.log`. 상태: `state/`(`current_tag` · `deployed_sha` · `bad_sha`).
- **멈추기**: `systemctl disable --now tripilot-autodeploy.timer`. 한 번만 돌리기: `systemctl start tripilot-autodeploy.service`.
- **설치**(서버, 한 번): `auto_deploy.sh` 를 배포 폴더에 두고(`chmod +x`), `tripilot-autodeploy.service` · `.timer` 를 `/etc/systemd/system/` 에 복사 → `systemctl daemon-reload` → `systemctl enable --now tripilot-autodeploy.timer`.
- ★**마이그레이션은 되돌리지 않는다.** 되돌린 이전 이미지가 새 표 구조를 견딘다는 가정이다 — 표를 지우거나 칸 이름을 바꾸는 파괴적 마이그레이션은 이 방식에 맞지 않는다.
- ★**브랜치의 코드가 곧 공개 서비스다.** 건강 검사로 못 걸러내는 기능 결함은 그대로 올라간다 — 확인이 필요한 브랜치는 따라가는 브랜치를 따로 둔다.
- ★서버는 저장소를 **읽기만** 한다(공개 저장소라 인증이 없다). 비공개가 되면 읽기 전용 배포 키를 서버에 둬야 한다.

## 알아둘 것
- **DB 는 서버에 하나가 정본이다.** 개발 PC 의 DB 와 합치지 않는다 — 서버에는 사용자 데이터를 안 가져갔고, 거기 쌓이는 것은 서버 것이다.
- **모델은 서버의 Ollama**(`gemma4:12b` · `bge-m3`)를 쓴다 — 요금이 안 나간다. 컨테이너가 그 Ollama 에 닿는 길은 서버 쪽 설정이다.
- **사람 확인(Turnstile)**: `ACOP_ENV=prod` 는 사람 확인 키가 없으면 서버가 안 켜진다. 키가 없는 동안 `ACOP_ENV=public` 으로 두면 확인 없이 키 발급이 열린다(주소별 일일 한도만 지킨다). 키를 받으면 `ACOP_TURNSTILE_SECRET` · `NEXT_PUBLIC_TURNSTILE_SITE_KEY` 를 넣고 `prod` 로 올린다.
- 이 폴더의 파일에는 **주소 · 계정 · 비밀을 적지 않는다.** 값은 서버 `.env` · `.env.apikeys` · 서버의 Caddyfile 에만 있다.
