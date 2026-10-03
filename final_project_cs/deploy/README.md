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
| `make_server_env.py` | 서버 `.env` 를 만든다(새 비밀 5개 + 공공 데이터 키 옮김). 값을 출력하지 않는다 |
| `export_reference_data.py` | 개발 DB 에서 **기준 데이터만**(장소 · 영업시간 · 정책 지식 · 프롬프트 · 요식 원장) 떠서 SQL 한 파일로 |
| `server_up.sh` | 서버에서: 빌드 → DB → 마이그레이션 → 기준 데이터(비었을 때만) → 전체 기동 |
| `Caddyfile.tripilot` | 기존 Caddy 에 붙일 사이트 블록(공개 경로만 연다) |

## 처음 올리는 순서

1. **이 PC**: `python deploy/make_server_env.py --host <공개 도메인> --proxy-network <Caddy 네트워크> --proxy-cidr <그 대역> --ollama-url <모델 서버> --out <파일>` → 서버 `.env` 로 복사(권한 600), **이 PC 의 사본은 지운다**.
2. **이 PC**: `python deploy/export_reference_data.py --out reference_data.sql.gz` → 서버로 복사.
3. **이 PC**: `git archive HEAD final_project_cs` 로 소스를 묶어 서버 `src/` 에 푼다(커밋된 것만 — 다시 만들 수 있다). 이동 데이터(`datasets/mobility`)는 따로 복사해 `TRIPILOT_MOBILITY_DIR` 로 가리킨다.
4. **서버**: `./server_up.sh`.
5. **DNS**: 공개 도메인이 서버로 오게 한다(주황 구름 프록시 가능).
6. **서버**: 기존 Caddyfile 을 백업 → `Caddyfile.tripilot` 의 `__TRIPILOT_HOST__` 를 바꿔 끝에 붙임 → `caddy validate` → `caddy reload`.
7. 확인: `https://<공개 도메인>/health` 가 `ok`, 웹 첫 화면, 키 발급.

## 갱신
소스를 다시 풀고(`src/`) `./server_up.sh`. 마이그레이션은 재실행 안전하고 DB 볼륨(`tripilot_pg`)은 그대로다.

## 알아둘 것
- **DB 는 서버에 하나가 정본이다.** 개발 PC 의 DB 와 합치지 않는다 — 서버에는 사용자 데이터를 안 가져갔고, 거기 쌓이는 것은 서버 것이다.
- **모델은 서버의 Ollama**(`gemma4:12b` · `bge-m3`)를 쓴다 — 요금이 안 나간다. 컨테이너가 그 Ollama 에 닿는 길은 서버 쪽 설정이다.
- **사람 확인(Turnstile)**: `ACOP_ENV=prod` 는 사람 확인 키가 없으면 서버가 안 켜진다. 키가 없는 동안 `ACOP_ENV=public` 으로 두면 확인 없이 키 발급이 열린다(주소별 일일 한도만 지킨다). 키를 받으면 `ACOP_TURNSTILE_SECRET` · `NEXT_PUBLIC_TURNSTILE_SITE_KEY` 를 넣고 `prod` 로 올린다.
- 이 폴더의 파일에는 **주소 · 계정 · 비밀을 적지 않는다.** 값은 서버 `.env` · 서버의 Caddyfile 에만 있다.
