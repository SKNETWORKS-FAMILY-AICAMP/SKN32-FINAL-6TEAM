# S-COMPOSER-DEPLOY-DOCS-01 — Composer 배포 경계 문서·설정 정합화 (코드 로직 변경 없음, 배포 설정+문서만)

## 배경

Claude·Codex 설계 자문 결론: 지금 `create_app()`은 고객 API(`/v1/cases`)와
Composer 쓰기 API(`/composer/*`, `/auth/token`)를 **같은 프로세스·같은 포트**에
등록한다. `docs/handoff/13`(Composer 쓰기채널 계약)은 "VPN/SSH 터널 + 단명
JWT" 를 전제하는데, `infra/aws/main.tf`의 ALB ingress 는 `0.0.0.0/0`(전체
공개)이라 그 전제와 실제 배포 초안이 서로 모순된다. 또 `_WRITE_LOCK`
(`app/application/composer_service.py`)이 프로세스 로컬 `threading.Lock`이라
다중 인스턴스·다중 워커에서는 동시성 보장이 깨지는데, 이걸 막는 배포
제약이 지금 문서·설정 어디에도 명문화돼 있지 않다.

**두 프로세스로 실제 분리하는 건 다음 스트림(별도 발주)이다. 이번은
코드를 안 건드리고, 지금 있는 구조에서 문서·배포 설정만 정합화한다.**

## 만들 것 — 문서 정정

1. **`docs/handoff/13_Composer_쓰기채널_계약.md`** — "경계 / 운영 제한"
   절에 다음을 명시적으로 추가한다(계약을 뒤집지 않는다, 보강만):
   - Composer API(`/composer/*`, `/auth/token`)는 **수평 확장 금지** —
     writer 인스턴스가 정확히 1개여야 `_WRITE_LOCK`의 동시성 보장이
     성립한다. 인스턴스를 늘리려면 이 락을 분산 락(DB 조건부 쓰기 등)
     으로 먼저 바꿔야 한다.
   - `/auth/token`은 "JWT 를 검증하는 API" 가 아니라 **JWT 발급 권한을
     쥔 민감한 관리 endpoint**다 — 읽기 전용이 아니다.
   - config apply(`config/project.yaml` 교체)와 audit append
     (`var/audit/composer_events.jsonl`)는 **같은 writer lock 아래
     원자적으로 수행되지 않는다** — apply 성공 후 별도 단계에서
     audit 을 남긴다(`app/presentation/api/composer.py`의 `apply()`
     구현을 읽고 실제 순서를 정확히 적어라. 추측하지 마라). 기존
     문서에 "원자적"이라고 쓴 표현이 있으면 사실대로 고친다.
   - Composer 가 `config/project.yaml` 을 바꿔도, **이미 떠 있는
     런타임 프로세스의 조립 상태가 자동으로 갱신된다는 보장은
     없다**(재시작/reload 필요) — 이 사실을 명시하고, 실제 반영
     방법(재배포/reload endpoint/polling)은 "정해지지 않음 — 후속
     과제"로 정직하게 남긴다.

2. **`infra/aws/main.tf`**(또는 관련 `.tf` 파일) — ALB ingress 를
   `0.0.0.0/0`에서 **VPC 내부 CIDR 또는 지정된 관리 IP 대역**으로
   좁히거나, 최소한 **주석으로 "이 초안은 아직 VPN/SSH 전제와 맞지
   않는다 — 프로덕션 적용 전 반드시 좁혀야 한다"**를 명시한다.
   ★이 저장소엔 Terraform 이 설치돼 있지 않아 `terraform plan`으로
   실제 검증할 수 없다(기존 인프라 스트림들도 전부 그렇게 명시했다,
   `docs/plans/2026-08-17_Docker_AWS_배포_모듈화_계획.md` 참고) —
   문법 정합성만 확인해라.
   `aws_ecs_service.desired_count` 가 이미 `1`이면, 그 옆에 **"이 값을
   1보다 크게 올리려면 `_WRITE_LOCK` 을 먼저 분산 락으로 바꿔야 한다"**
   는 주석을 남긴다.

3. **`docker/compose.yml`, `Dockerfile`(또는 실행 커맨드가 정의된 곳)** —
   Uvicorn 실행 커맨드에 워커 수 지정이 없으면 **명시적으로
   `--workers 1`을 추가**하고(기본값에 암묵적으로 기대지 않는다,
   CLAUDE.md "폴백 금지" 원칙), 주석으로 이유(Composer `_WRITE_LOCK`
   프로세스 로컬)를 남긴다. 이미 1이 기본이라도 명시적으로 적어라 —
   나중에 누가 스케일 아웃하려고 이 줄을 건드릴 때 이유가 안 보이면
   그냥 지워버릴 수 있다.

4. **`docs/handoff/14_배포_계약.md`**(있으면, 없으면 만들지 말고
   `docs/handoff/13`에만 적어라) — 위 제약들을 배포 체크리스트로
   한 번 더 요약한다. 새 파일을 만들지 마라 — 기존 문서에 절을
   추가하는 형태로만.

## 하지 않을 것

- `app/`, `config/`, `tests/` 등 **런타임 코드를 하나도 고치지 않는다.**
  이번은 문서·IaC 설정·배포 커맨드만 다룬다.
- 두 프로세스(`customer-runtime`/`composer-control`) 분리를 시작하지
  않는다 — 그건 다음 스트림이다.
- `docs/handoff/13`의 계약 자체(엔드포인트·scope·audit 이벤트 shape)를
  뒤집지 않는다 — 사실을 더 정확히 적을 뿐이다.
- Terraform 실행(`terraform plan`/`apply`)을 시도하지 않는다 — 이
  환경엔 Terraform 이 없다.

## 검증

```powershell
python -m pytest -q --ignore=tests/integration/rag
```
코드를 안 건드렸으니 이 스트림 전후로 테스트 결과가 동일해야 한다(다른
동시 진행 중인 변경 때문에 달라졌다면 그 사실만 리포트에 적어라).

## 만들 것 (리포트)

`docs/reports/2026-08-18_S-COMPOSER-DEPLOY-DOCS-01_리포트.md` — 고친
파일 목록과 diff 요약, `apply()`의 실제 config-write/audit-append 순서를
코드에서 확인한 원문 인용(추측 금지).
