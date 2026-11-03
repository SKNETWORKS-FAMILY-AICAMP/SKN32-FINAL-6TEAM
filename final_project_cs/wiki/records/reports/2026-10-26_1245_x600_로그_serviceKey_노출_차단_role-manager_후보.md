---
type: report
title: x600 api 로그 serviceKey 노출 차단 — role-manager 커밋 후보
status: candidate
date: 2026-10-26
---

# x600 api 로그 serviceKey 노출 차단 — role-manager 커밋 후보

**결론:** 원인은 `create_app()` → `composition.build_mcp_surface` → `FastMCP(...)` 가 `mcp.server.fastmcp.utilities.logging.configure_logging("INFO")` 로 **루트 로거를 INFO** 로 올린 것이다(`logging.basicConfig`, RichHandler). 레벨 없는 `httpx` 로거의 `HTTP Request: GET <주소 전체>` INFO 줄이 루트로 올라가 `serviceKey=` 쿼리째 찍혔다. 로컬 커밋 후보 `590c73920726c1b36b538ca71837c41ef796e760`(기준 role-manager `74b2b2325e54172e626cd9cdd8385c4bbe337252`)로 막았다. **push 안 함 · x600 변경 없음.**

## 원인 재현(코드)

- 실측 probe(격리 runner): `create_app()` 전 루트 `WARNING`/핸들러 0 → 후 `INFO`/`RichHandler`. MockTransport GET 한 번에 `httpx HTTP Request: GET https://apis.data.go.kr/x?serviceKey=<가짜값>&pageNo=1 "HTTP/1.1 200 OK"` 가 잡혔다.
- 자체 로그 · 예외 경로 전수: `TravelSource._fetch_json` 의 `_miss(... str(exc))`(httpx 예외 글) → `logger.warning("travel source miss")`. `VWorldGeocoder._ask` · `tourapi_client._fetch_body` · `bike.py` 는 이미 예외 이름만 남긴다(주소 미기록). 저장되는 진단(`last_error`)에도 주소 없음.

## 키를 쿼리 · 경로에 싣는 사용처(전수)

- `serviceKey` 쿼리: `air_quality` · `disaster_msg` · `holiday` · `incheon_airport` · `kma` · `kma_earthquake` · `kma_warning` · `mofa` · `seoul_bus` · `subway_notice` · `tago_transit` · `tour_api` · `tourapi_client`(urllib)
- 다른 이름: `its_traffic`(`apiKey`) · `utic`(`key`) · `geocode` vworld(`key`) · `serpapi_flights`/`serpapi_hotels`(`api_key`)
- **경로 조각**: `seoul_subway`(`/api/subway/{KEY}/…`) · `bike.py`(`openapi.seoul.go.kr:8088/{key}/…`) — 이름 규칙으로 못 잡아 설정 키 값 등록으로 가린다
- 헤더(무관): `kakao_local` · `google_places` 등

## 수정

- `app/core/redaction.py`: `SECRET_QUERY_PARAMS`(이름 목록 한 곳) · `redact_secrets`(쿼리 `name=value` · JSON `"name": "value"` · 등록 키 값) · `redact_secret_values`(등록 값만 — `mask_json`/`masked` 저장값에 적용, 고객 링크의 `?token=` · `?key=` 는 보존)
- `app/core/log_redaction.py`(새): `install_log_redaction` — `httpx` · `httpcore` WARNING, 로그 레코드 팩토리로 메시지 · 예외 글 · 스택 글 가림, 설정 `*_key`/`*_keys`/`*_secret`/`*_token`/`*_key_server` 값 등록(JSON · 쉼표 목록 분해). 팩토리가 바뀌면 다시 건다.
- 거는 곳: `create_app` · `create_ops_app` · `TravelSource.__init__`
- `tests/unit/travel/test_telegram_client.py`: httpx INFO 를 이 시험 안에서만 여는 contract_correction(단언 그대로)
- wiki `quality/invariants.md` `INV-CS-SEC-016` 한 줄

## 검증

- RED: 새 시험 파일 수집 실패(모듈 없음) · `mask_json` 시험 1 failed → GREEN 24/24
- 빠른 관문(tests/architecture · contract · unit · security · eval/tests, `-m 'not live and not db and not slow'`, 격리 runner): **10214 passed / 0 failed / 173 skipped**(XML tests=10387, failures=0, errors=0, 새 시험 24건 포함). 그 뒤 시험 파일의 f-접두사 1개만 ruff 로 고쳐 파일 단독 재실행 24 passed.
- ruff(바뀐 7 파일): All checks passed
- Codex CLI 리뷰(텍스트 전용): 1차 「수정 필요」 — 쉼표 값 잔여, JSON 모양, `mask_json` 이 고객 링크 훼손, `getMessage` 실패 시 예외 미가림, 팩토리 교체 시 재설치 불가, fixture 값 목록 초기화 → 모두 반영하고 시험 추가. 2차 리뷰는 안 함.
- patch: `fix-logkey.patch` sha256 `428d1f265fc378b59c77da23d6131f5227b07c740b73b9b83912777e1466c28d`

## 남은 것 · 권고

- **이미 x600 로그에 남은 키는 이 수정으로 지워지지 않는다. data.go.kr 키(그리고 같은 기간 로그에 쿼리 · 경로로 실렸을 ITS · UTIC · vworld · SerpApi · 서울 열린데이터 키) 교체를 사용자가 직접 하길 권고한다.** 로그 파일 · 수집처 보존본 정리도 사용자 판단.
- 한계: `extra=` 로 붙인 필드는 가림 대상이 아니다(현재 그런 사용처 없음). 8자 미만 키 값은 값 등록을 안 한다.
- push · x600 배포 · 로컬 serving 반영: 모두 안 함.

증거: `cache/scratch/fix-logkey-20261026-1221/`(evidence/gate3.xml · gate3.log · ruff.log · codex-review.md · probe_cause.py · fix-logkey.patch)
