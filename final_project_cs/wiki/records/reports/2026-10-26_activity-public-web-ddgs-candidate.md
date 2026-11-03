# Activity 공개 웹 보조조회 ddgs backend — 후보 (2026-10-26)

## 결론

- role-manager `53dea261` 위 후보를 staged로 준비했다. push·live 교체는 하지 않았다. 기본값은 `enabled: false`다.
- 빠른 관문(tests/architecture·contract·unit·security, `not live and not db and not slow`): 후보 **9489 통과 / 173 skip / 실패 0**(총 9662). 기준 `53dea261`은 9419 / 173 / 0(총 9592). 새 nodeid 70개이고 기준에만 있는 nodeid는 0개다. ruff F/E9 0.
- 실검색(격리 환경, 제품 경로, 공개 장소명 3건 × 2회): **사실 보존 0/6 = 0%**. ddgs가 결과를 낸 것은 2/6 = 33%, 둘 다 공식 페이지 규칙에서 멈췄다. 나머지 4/6은 `search_no_results`.
- 로컬에서 카카오가 늘 실패하는 원인은 serving guard `runtime-v9-serving/policy.py`다. 근거는 제품 계약이 아니라 serving 결정이다. 최소 허용목록 diff를 준비만 했다.
- 로컬 live 켜기안은 **준비만** 했다. Codex 검토 결론도 prepared-only 유지다.

## 계약 변경 (`wiki/external/activity-public-web.md` 「backend `ddgs`」 절)

- `backend=ddgs`로 키·가입·요금이 없다. 옵션은 `travel.activity_public_web.ddgs`(backends·region·safesearch·max_results)에서만 읽는다. `auto`/`all`은 받지 않는다. ddgs 등록부 `search_url`의 host가 모두 `search_hosts`에 있어야 켜진다.
- 질의에는 공개 정식 이름과 `district`(행정구)만 넣는다. 고객 원문·별칭·주소·ID는 넣지 않는다. `DDGS_PROXY`가 있으면 거절한다.
- snippet은 URL 발견에만 쓰고 저장하지 않는다. 사실은 공식 페이지 JSON-LD에서만 가져온다. robots·403·redirect 거절은 공식 페이지 취득에 적용한다. ddgs는 비공식 결과 수집이라 결과가 흔들릴 수 있다는 점을 계약에 적었다.
- 실패는 `public_web.reason`으로 드러낸다: `search_http_429`·`search_web_timeout`·`search_no_results`·`search_failed`·`search_budget_blocked`·`search_proxy_rejected`·`search_query_unconfigured`. 거절된 설정은 `web_not_configured`와 `config_detail`로 드러난다. 조용한 폴백은 없다.

## 이식 방식

- `4260498075b9` 「공개 웹 보조조회」(develop 이식 브랜치 `port/writer-on-develop`)를 `cherry-pick -x`로 가져왔다. 작성자 roroblack을 유지했고, 결과 로컬 커밋은 `fd1867e41e57`(부모 `53dea261`)이다. 충돌은 0이다. 이식 파일 8개 중 activity 관련 파일은 v9 source와 바이트가 같다(review.py·read_tools.py·fallback 시험의 차이는 다른 기능 hunk다).
- 접수 연결은 `4f565ffe2`에 reader 안전 변경과 섞여 있다. 그래서 activity_web hunk만 파일 단위로 이식했다(pipeline.py 4줄, trip_api.py 1줄).
- wiki 두 문서(activity-public-web·activity-public-web-intake)는 v9에서 파일 단위로 이식했다.

## hunk 요약 (staged, cherry-pick 위)

- `activity_public_web.py`: 추가 — `_ddgs_engine_hosts`, `_ddgs_client_factory`, `DdgsWebSearch`(같은 meter `activity_web_search`를 engine 요청 1회당 1로 소비, ResponseCache, total_seconds deadline 사용). 변경 — 팩토리의 backend 분기와 `config_detail`, 결과의 `search_backend`, 공식 페이지 읽기 실패를 official-host 거절보다 먼저 reason으로 낸다(실검색에서 발견, RED→GREEN).
- `base.py`: `unavailable['activity_web']`에 config_detail을 붙인다.
- `guardrails.yaml`: `ddgs` 블록 추가. enabled false 유지.
- `requirements.txt`: `ddgs==9.16.1`, `primp==2.0.1`, `lxml==6.1.3` 추가.
- 시험 `tests/unit/travel/test_activity_public_web_ddgs.py` 23건. RED는 21 실패를 확인했고, 추가한 reason 순서 시험 1건은 기준 모듈에서 RED를 따로 재현했다.

## 실검색 (격리, `real_search.py`, 카카오 실패 대역 → `places.resolve` → ddgs → `PublicWebTransport`)

| 회 | 장소 | ddgs 결과 | 공식 URL | 보존된 사실 | reason |
|---|---|---|---|---|---|
| 1 | 국립중앙박물관 | 5 URL / 1.0초 | `https://www.museum.go.kr/site/main/home` | 없음 | 읽기 redirect_blocked. 당시 코드는 `source_url_rejected`를 냈고 수정 후에는 `extract_redirect_blocked` |
| 1 | 광장시장 | 0 | — | 없음 | `search_no_results`(0.3초, throttle 추정) |
| 1 | N서울타워 | 0 | — | 없음 | `search_no_results` |
| 2 | 국립중앙박물관 | 0 | — | 없음 | `search_no_results` |
| 2 | 광장시장 | 5 URL / 0.75초 | `http://www.kwangjangmarket.co.kr/`(HTTP만) | 없음 | `source_url_rejected`(HTTPS 전용) |
| 2 | N서울타워 | 0 | — | 없음 | `search_no_results` |

- identities는 한국관광공사 자료(`activity_total_data.csv` contentid 129703·132183·126535)에서 옮겼다. 고객 자료는 쓰지 않았다.
- meter 사용: 1회 search 3·extract 2, 2회 search 3·extract 0. 증거는 `ev/real-search-run1.json`·`run2.json`이다.

## 로컬 서빙 정책 차단 근거와 허용 diff

- `policy.py` 첫 줄은 「Owned serving guard: exact shared DB and pinned local model only」다. 127.0.0.1:5433·11434 외의 DNS·socket·httpx를 막는다. `policy-counters.json`의 denied는 51이고, 마지막 차단은 `dapi.kakao.com`이다.
- 결정 근거: `wiki/handoff/2026-10-25_service-emergency-recovery.md:29` 「무료 외부조회도 현 egress거부 유지, 추가 승인 없이 넓히지 않습니다」. v5 serving부터 이어온 serving 결정이며 제품 wiki 계약은 아니다. `readiness-decision.json`에도 `optional_search_enabled:false`로 적혀 있다.
- 허용 diff `local-live-proposal/policy.diff`: HTTPS:443 GET만 허용한다. 대상은 `dapi.kakao.com /v2/local/search/`, `apis.data.go.kr /B551011/KorService2/`, 공식 3 host다. 연결은 그 host가 해석한 public IP로만 허용하고, pinned IP가 일치하는지 확인한다. ddgs는 `html.duckduckgo.com` POST `/html/`만, 파라미터 키 제한, redirect 끔, ambient proxy 거절로 막는다. 유료 모델·알림 host는 계속 차단하며 DENIED 자체검사를 넣었다. **문법 검사만 했고 실행 검증은 하지 않았다.**
- 주의: ddgs의 primp는 Rust라 Python audit hook에 보이지 않는다. 현재 정책도 primp egress는 막지 못한다. 그래서 `ddgs.http_client.HttpClient.request`를 감싸는 방식으로 막는다.

## Codex 논의 (`codex exec` read-only, 텍스트 번들, `codex-answer.md`)

1. 예산 DB 오류 규칙: 로컬은 전역 `source_budget_on_db_error: allow`다(10-05 결정 대기). 팩토리는 `refuse`를 요구한다. Codex 의견은 (c) **두 meter에만 소스별 refuse를 코드로 넣기**다. 이번 후보에는 넣지 않았다. 지금 켜면 `config_detail=budget_unconfigured`로 꺼진 채 관찰된다. 켜기안의 `refuse` 줄은 「결정 필요」로 남겼다.
2. HTTP→HTTPS 승격과 redirect 추적: **현 계약대로 거절을 유지**한다. 바꾸려면 별도 계약 변경이 필요하다.
3. 정책 diff 1차안의 구멍 5개를 받았다(경로 미검사, IP 결속 없음, ddgs redirect/proxy, 파라미터 제한, 요청별 계량). 앞의 4개는 반영했다. 요청별 계량(ddgs 내부 재시도)은 남은 한계다.
4. 켜기 권고: **prepared-only**. 0/6이라 효용이 입증되지 않았다.

## 산출물 (`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/public-web-ddgs-20261026-053927/`)

- staged 트리 `rm/`: HEAD `fd1867e41e57`(cherry-pick), write-tree `7cd7463333d2`. 커밋 메시지는 `COMMIT_MSG.txt`.
- `rm-53dea261-activity-public-web-ddgs.full.patch` sha256 `c75d905e2471f25605d7500a6c14863e16ebcfdd2c288cb71019331115f27509`(53dea261 → 후보, 17 파일).
- `rm-ddgs-over-cherrypick.patch` sha256 `6c4868033244118da45e025929ea4bf78233d65d22c84ef2eefa0a7ff180bf7e`.
- v10 재료 `v9-activity-public-web-ddgs.patch` sha256 `8b207d9788cb95c2e4b1badf5698a8ec325aa4c142778b428204d4d36a4156d5`. v9 사본에서 apply-check와 결과 바이트 대조를 했다(6/6 일치, guardrails는 hunk 적용).
- 켜기안 `local-live-proposal/activity_public_web.local.yaml`, `policy.proposed.py`, `policy.diff`.
- 관문 XML: `ev/fast-cand53/*.xml`, `ev/fast-base53/*.xml`(실행기 `run_gate.py` = run_aig 사본, 루트 변수 `PWDDGS_SRC`).
