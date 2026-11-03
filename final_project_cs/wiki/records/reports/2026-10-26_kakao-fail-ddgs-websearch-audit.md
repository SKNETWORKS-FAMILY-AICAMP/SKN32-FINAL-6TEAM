# 카카오 실패 시 ddgs 웹검색 — 읽기 전용 점검 (2026-10-26)

## 결론

**제품 코드에 ddgs 경로는 없다.** 로컬 live v9·role-manager·develop 세 곳 모두 `ddgs`/`duckduckgo` 0건이며, 서빙 venv·requirements.txt에도 ddgs가 없다. 카카오 실패 뒤 붙는 보조조회는 **Activity 공개 웹 보조조회**(`travel.activity_public_web`, backend=`searxng` 고정)이고, 이것도 로컬 live v9에만 있으며 **OFF**다. 그래서 지금은 카카오가 실패하면 `public_web.reason=web_not_configured`(미확인, 확인 질문)로 끝나고, 실제 웹검색은 0회다. ddgs는 Hermes 개발도구의 웹검색 backend 이름이다(현재 profile 설정은 `tor`). 제품에 들어간 적은 없다.

## 구현 위치 (로컬 live v9 `integ-v9-20261026-025943/source/final_project_cs`)

- `app/domains/travel_ops/components/intake/places.py:171-199` `resolve()`: `_resolve_existing`(DB·별칭·관광공사·카카오)가 `unresolved`이고 후보가 없는 Activity일 때만 `activity_web.lookup(title)` 호출. 결과는 `Resolved.public_web`, `needs_review=True`, `upstream_status=unknown|not_found`.
- `app/domains/travel_ops/ports/data_sources/activity_public_web.py:295-337` `build_activity_public_web`: `enabled is True`, `backend == "searxng"`, `paid is False`, `approved_public_queries is True`, 두 meter 예산, endpoint·identities가 모두 있어야 켜짐. 아니면 `{"enabled": False}`.
- `app/domains/travel_ops/ports/data_sources/base.py:503-506`: `sources.activity_web` 등록, OFF면 `unavailable['activity_web']`.
- 호출 경로: `entry/trip_api.py:1440` → `intake/pipeline.py` `process`/`read_source`(`activity_web=`) → `places.resolve`.
- 설정: `config/guardrails.yaml:457-465` `enabled: false`, `backend: searxng`, `search_endpoint: ""`, `identities: []`.
- 계약: `wiki/external/activity-public-web.md` — 요구 원문 「카카오에서도 못 찾으면 우리 Hermes 웹검색하는 것처럼…」을 무료 SearXNG JSON provider로 구현. 2026-10-25 후속 보고서: 후보 endpoint `priv.au` robots `Disallow: /*?*q=*`로 실검색 0회.
- 별개: `settings.activity_judge_web_search=True`는 OpenAI Responses 웹검색(유료 모델 경로)이며 이 보조조회가 아니다.

## 환경별 켜짐

| 환경 | 기준 | 보조조회 코드 | ddgs | 설정 | 외부통신 |
|---|---|---|---|---|---|
| 로컬 live v9 (pid 5088, :8042) | `runtime-v9-serving/local-guardrails.yaml:254` | 있음(searxng) | 없음 | `enabled: false` | `policy.py`가 127.0.0.1:5433/11434 외 DNS·socket 차단. `policy-counters.json` denied 47, 마지막 차단 `dapi.kakao.com`(Dining `kakao_local.search`) |
| role-manager `da4ccd97` (x600 추정) | 저장소 grep | 없음 | 없음 | 키 없음 | x600 미호출(추정만) |
| develop `7c326cbb` | 저장소 grep | 없음 | 없음 | 키 없음 | — |

로컬 live는 카카오 호출 자체도 서빙 정책이 막는다. 따라서 로컬에서는 카카오가 항상 `kakao:unavailable`로 실패하고 보조조회는 `web_not_configured`가 된다.

## 실제 동작 (격리 `cache/scratch/ddgs-check-20261026-043722`, live 미접촉)

1. 제품 경로: live v9 소스를 읽기 전용으로 import하고 카카오 실패 대역(`search()→None`, misses `http_503`)을 넣어 `places.resolve` 호출. source guardrails와 live local-guardrails 모두 국립중앙박물관·광장시장 2/2 = 100% `status=unresolved`, `blocked=["kakao:http_503"]`, `public_web.reason=web_not_configured`, facts 없음, 외부요청 0.
2. ddgs 직접 시험(제품 경로 아님, 격리 venv ddgs 9.16.1, 공개 장소명만): 3회 중 2회 = 67% 결과 반환.
   - 「국립중앙박물관 운영시간」 5건, 3.8초. museum.go.kr 공식 + 블로그. 블로그 snippet끼리 운영시간이 다름(2026-03 조정 언급).
   - 「광장시장 휴무일」 5건, 2.6초. kwangjangmarket.co.kr 공식 페이지 snippet에 「오전 9시~오후 6시, 휴무 일요일」.
   - 「남산서울타워 운영시간」 `DDGSException: No results found`, 4.6초.
   - snippet은 계약상 운영 근거가 아니다(URL 발견용). ddgs는 공식 API가 아니라 검색엔진 HTML 스크래핑이라 결과가 흔들린다.
3. 카카오 실호출: 하지 않음(로컬 정책상 차단 대상, 키 조회 불필요).

## 단위시험

복사본에서 실행(date_risk_env_312, 더미 env): `test_activity_public_web_fallback.py`, `test_activity_intake_public_web.py`, `test_activity_place_lookup.py`, `test_intake_resolve.py`, `test_intake_chain_resolve.py` 117/117 = 100% 통과. 이 수치는 fixture 시험이며 실검색 성공이 아니다.

## 문제와 고칠 것

1. 「ddgs로 넘어간다」는 인식과 코드가 다르다. ddgs를 원하면 backend 추가 결정이 필요하다(`build_activity_public_web`의 `backend == "searxng"` 조건, `PublicWebSearch.discover`가 SearXNG JSON 전용). ddgs는 비공식 스크래핑이라 약관·robots·안정성 검토가 계약(무료·공개약관·robots 준수)과 충돌할 수 있다.
2. 켜져 있지 않다: endpoint, identities, daily_limits, meter 등록이 모두 비어 있다. 켜도 로컬 live 서빙 정책은 외부 host를 막으므로 정책 허용목록 결정도 필요하다.
3. role-manager·develop에는 보조조회 코드 자체가 없다. x600에서는 카카오 실패 시 웹 보조조회가 없다(저장소 기준 추정).
4. 실검색이 되어도 운영시간·휴무는 공식 페이지 JSON-LD `openingHours`만 사실로 쓴다. 광장시장처럼 공식 페이지가 본문 문장으로만 시간을 쓰면 계속 미확인이다.

수정·push·live 변경 없음.
