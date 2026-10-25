# Activity 공개 웹 보조조회 계약 — 사용자 명시 요구

2026-10-25 후속 독립 후보: [접수 bridge 계약](activity-public-web-intake.md) · [112/112 검증과 실제 robots 차단/공식 본문 미확인](../records/reports/2026-10-25_activity-intake-public-web-followup.md). 아래는 최초 provider 후보 범위입니다. 후속은 정상 resolver/claim/review 연결을 보완했으나 실검색 JSON·공유PG·브라우저·rollout 수락은 여전히 미완료입니다.

요구: “카카오에서도 못 찾으면 우리 Hermes 웹검색하는 것처럼 그거 그대로 적용하면 되지 않아?”

이는 **공개 장소명·주소·좌표 사실을 보완하는 제품 provider** 요구입니다. Hermes 내부 도구 gateway나 키를 제품에서 호출/복사하는 요구가 아닙니다. x600 원장 수집·복원, 로컬 Activity 원장 적재, x600 password 대기, Dining Google 유료 live-check를 대체하지 않습니다.

## 발동과 결과

- 순서: Activity DB 정본/확정 별칭 → Kakao 정상 조회 → 미일치(`not_found`) / 미조회·장애(`unknown`)를 보존 → 별도 공개 search → 공식 페이지 본문 structured extract.
- DB found/ambiguous/짧은 이름, Kakao found이면 보조 search를 부르지 않습니다. Kakao 응답 이름·좌표·주소·id는 저장하지 않습니다.
- 검색 snippet은 운영 근거가 아니며 저장하지 않습니다. 결과 URL은 후보 발견에만 사용합니다.
- 공용 설정에서 검토한 canonical_id·정식 이름·별칭·주소·공식 host를 먼저 묶습니다. customer/customer_note 출처를 공용 anchor로 승격하지 않습니다. 같은 이름 여러 곳, 주소·좌표 불일치, 출처 상충은 확인 질문으로 끝납니다.
- 공식 HTML의 JSON-LD name/address 및 (설정에 있으면) coordinates를 대조합니다. 현재 parser는 엄격한 `openingHours` 문자열만 읽으며, 자유 본문 해석·휴무 추론·날짜별 영업 추정은 **구현하지 않았습니다**. 해당 값은 `unknown`으로 보존합니다. 안내문에서 시각을 만들지 않습니다.
- 보조 결과는 `status=unknown`, `needs_question=true`, `reason`, `unknown`, `fallback.upstream_status/reason/detail`, 검증된 `facts`를 갖습니다. 웹 확인 실패를 `found=false`/장소 부재로 확정하거나 공원으로 대체하지 않습니다.
- 각 fact에는 `source_url`, 실제 본문을 읽은 `checked_at`, `confidence=official_structured`, JSON-LD field와 `body_sha256`이 붙습니다. 캐시를 읽은 시각으로 checked_at을 갱신하지 않습니다.
- 실패는 search_http_403/429, extract_http_403, robots_blocked, timeout, page_unreadable, no_official_facts, conflicting_sources, ambiguous_identity, address_mismatch, coordinates_unverified, provenance_rejected 등으로 구분합니다. HTTP/robots 차단은 다른 서비스로 몰래 우회하지 않습니다.

## 외부 전송·저장·표시 범위

외부 search payload는 **설정에서 확인한 public canonical name + public address**, `format=json`뿐입니다. 원래 고객 입력은 alias lookup에만 사용합니다. 고객원문·여행전체·사용자ID·예약번호·쿠키·API키를 넘길 자리는 없습니다. 요청 헤더는 Accept/Accept-Encoding/User-Agent뿐이며 ambient proxy/cookie를 사용하지 않습니다.

페이지 문자열은 파서에 공급한 뒤 폐기하며, 공용 ResponseCache에는 검색 URL 목록/검증한 구조화 fact만 둡니다. 소개글·원문 전체·snippet은 저장하지 않습니다. 기존 source TTL/limiter/DB budget을 재사용합니다. 상태/fact 결과는 JSON 직렬화 가능하나 **실제 고객 UI 영속화/재로드는 이번 독립 provider 후보에서 검증하지 않았습니다**. UI는 검증한 각 값 옆에 출처 URL·확인시각·미확인을 표시하고 질문을 유지해야 합니다. 전역 alias/원장에 고객 값을 자동 기록하는 기능은 없습니다.

웹 데이터는 facts data일 뿐 실행 지시가 아닙니다. 프롬프트/셸/도구/권한변경 모델을 호출하지 않습니다. JSON-LD openingHours에 명령문이 들어가도 문법검사로 버립니다.

## 공통 설정과 공급자 등록

기존 `TravelSources` → `ReadToolbox.read.place_lookup` 등록 경로를 사용합니다. `TravelSource`의 limiter/성공 캐시/실패 계수, `social_links`의 공인-IP DNS 검증 및 pinned-IP TLS 연결을 재사용합니다. 검색과 공식 추출은 `activity_web_search`, `activity_official_extract` 두 meter입니다.

현재 제품에는 OpenAI 웹검색+place_enrichment/web_info 검증·저장 경로가 이미 있지만 **유료 모델 호출**이므로 이번 경로에서는 사용하지 않습니다. SerpAPI는 항공/호텔, Naver 설정은 블로그/카페 검색이며 일반 무료 공식-site discovery 설정으로 간주하지 않았습니다. 기존 `social_links`는 SNS host 한정이므로 도메인 허용목록을 몰래 늘리지 않고 DNS/TLS 원시구현만 재사용했습니다.

이번 후보의 기본값은 `travel.activity_public_web.enabled=false`입니다. 실제 사용에는 다음 **정확한 설정**이 필요하며, endpoint/수치/공식 identity를 임의로 채우지 않았습니다.

- `travel.activity_public_web`: enabled=true, backend=searxng, paid=false, approved_public_queries=true
- `search_endpoint`: 운영자가 허용한 **무료 HTTPS SearXNG JSON search endpoint**(query/userinfo/fragment 없는 URL). `search_hosts`: 해당 host allowlist. 새 유료 API·가입·키 불필요. 공개 인스턴스 임의 선택/무료 보장은 하지 않습니다.
- `identities`: canonical_id, name, aliases, address, official_hosts, provenance=public_catalog. 선택 coordinates=[latitude, longitude]. 고객 자료가 아닌 검토된 공공 catalog anchor. 실제 N타워의 현재 주소/공식 host 검토는 미완료이며 fixture 값을 넣으면 안 됩니다.
- `max_pages`, `total_seconds`, `coordinate_tolerance`, `daily_limits.activity_web_search`, `daily_limits.activity_official_extract`: 공통 guardrails에서 명시할 값. 신규 hardcoded 운영 수치 없음.
- `travel.source_budget_sources`에 두 meter 추가, `travel.source_budget_shared=true`, `travel.source_budget_on_db_error=refuse`. 공유 DB budget을 세지 못하면 외부 호출하지 않습니다. 캐시 전용 모드는 그대로 외부 호출 금지입니다.
- HTTP bounds는 기존 `travel.social_dining.timeout_seconds/max_response_bytes/max_url_chars`; TTL은 기존 `travel.source_cache_seconds`를 재사용합니다.

HTTPS·정확 host·userinfo/비표준 port/query/fragment 금지, 모든 DNS 응답의 공인 IP 확인, IP 고정 TLS, 전체 deadline/body 제한을 적용합니다. redirect는 따라가지 않으며 `redirect_blocked`로 공개합니다. robots.txt를 먼저 읽고 허용한 경우에만 본문을 읽습니다(robots 실패도 미확인). robots와 본문 각각 예산을 소비합니다. URL/본문 캐시는 중복 호출을 줄이고 provider lock은 같은 인스턴스의 동시 cache-miss를 직렬화합니다.

## 기존 계약과 소유권

기존 place_enrichment는 DB miss + Kakao 미일치/장애에서 웹으로 가지 않는 2026-10-19 계약입니다. 이번 명시 요구는 그 제한을 **읽기 보조경로에 한하여** 넓힙니다. 유료 enrichment·Dining·후보 선호/자동추천/원장변경 계약은 변경하지 않습니다.

6c34589b4e34dede82e566d43b3757e127a5d5d9 + rollout owner의 작업 중인 candidate를 읽고 별도 `activity-public-web-7f91/candidate`에만 구현했습니다. 원본/현서비스/타 writer 파일을 덮지 않았습니다. `pipeline.py`, Activity candidates/prepared preference는 변경하지 않았습니다.

**중요한 남은 접점:** 실제 고객 접수는 `components.intake.pipeline.read_source` → `places.resolve`로 흐릅니다. `read.place_lookup`는 등록된 도구이지만 현재 접수 호출과 동일하지 않습니다. 그러므로 이 후보의 정상 ReadToolbox/provider 수락을 고객 N타워 해결로 주장하면 안 됩니다. rollout owner 9238ab26 및 prepared/preference owner c7088b38와 조율해 현재 resolver의 미확정 반환에서 `sources.activity_web.lookup(public_name)`의 safe result를 evidence에 연결하고 UI 저장/재로드를 검증하는 통합이 남습니다. 검증된 본문 근거만 연결하고 기존 일정은 변경하지 않습니다.

비용: 격리 시험의 실제 외부요청/모델호출/유료API/서비스재시작은 모두 0입니다. 무료 backend가 설정되지 않아 **실N타워 search+공식본문 조회는 실행하지 않았고 0원 실서비스 검색 성공을 주장하지 않습니다**. fixture 공급자 검증과 실provider 수락은 별개입니다.

## backend `ddgs` — 키 없는 무료 검색 결과 수집 (2026-10-26 사용자 지시)

요구: 「우리 헤르메스 웹 검색 방식 우리 로컬 서버에도 적용해서 써먹기로 하지 않았냐 … 카카오도 검색 안되면 그걸로 하기로 했잖아」. Hermes 웹검색 backend 중 하나인 `ddgs` 패키지(MIT, 키·가입·요금 없음)를 **발견 단계 backend**로 추가합니다. Hermes gateway·키를 제품에서 부르는 것이 아니라 같은 공개 패키지를 제품이 직접 씁니다.

- 설정: `travel.activity_public_web.backend=ddgs`. 옵션은 `travel.activity_public_web.ddgs`의 `backends`(ddgs text engine 이름 목록) · `region` · `safesearch`(on/moderate/off) · `max_results`에서만 읽습니다. 코드에 운영 수치를 두지 않습니다. `search_endpoint`는 쓰지 않습니다.
- `backends`에 `auto`/`all`은 받지 않습니다(부르는 host가 정해지지 않음). 설치된 ddgs 등록부의 각 engine `search_url` host가 모두 `search_hosts`에 있어야 켜집니다. 패키지는 `requirements.txt`에 `ddgs==9.16.1`(+ native 의존성 `primp`·`lxml`)로 고정합니다.
- 질의: 검토된 `identities` 항목의 **공개 정식 이름 + 행정구(`district`, 예: 「서울 용산구」)**만 보냅니다. 고객 원문·고객 별칭·여행·사용자/예약 ID·상세 주소·쿠키·키는 보내지 않습니다. `district`가 없는 identity는 검색하지 않고 `search_query_unconfigured`로 끝납니다. `DDGS_PROXY` 같은 ambient proxy가 있으면 `search_proxy_rejected`로 거절합니다.
- 검색 결과의 title/snippet은 **URL 발견용**이며 사실·저장 대상이 아닙니다. 결과 URL은 기존 규칙대로 identity의 `official_hosts`(HTTPS·query 없음)만 통과하고, 사실은 공식 페이지 구조화 근거(JSON-LD name/address/선택 coordinates, 엄격한 `openingHours`)만 씁니다. 공식 페이지 취득에는 기존 robots.txt 선확인·403/redirect 거절·공인 IP·pinned TLS가 그대로 적용됩니다.
- ddgs는 공식 검색 API가 아니라 검색엔진 결과 화면을 수집하는 비공식 도구입니다. 같은 질의도 결과가 흔들리거나 비거나 차단될 수 있으며(2026-10-26 격리 시험 3회 중 1회 「No results found」), 그 경우도 장소 부재가 아니라 미확인입니다. 검색엔진 쪽 robots/약관은 이 경로가 보장하지 않습니다 — 운영 승인(`approved_public_queries=true`)이 그 판단을 대신합니다.
- 예산·캐시·시간: 같은 meter `activity_web_search`(engine 요청 1회당 1단위)·`activity_official_extract`, 같은 공용 ResponseCache(URL 목록만 저장), `travel.social_dining.timeout_seconds`와 `total_seconds` 전체 deadline을 공유합니다.
- 실패는 `public_web.reason`으로 드러냅니다: `search_http_429`(rate limit) · `search_web_timeout` · `search_no_results` · `search_failed` · `search_budget_blocked` · `search_proxy_rejected` · `search_query_unconfigured`, 이후 공식 페이지 단계는 기존 `extract_*`/`identity_unverified`/`no_official_facts` 등. 다른 검색 backend·유료 검색·SearXNG로 **몰래 넘어가지 않습니다**.
- 꺼짐도 관찰 가능합니다: 켜려 했으나 거절된 설정은 `reason=web_not_configured`와 함께 `config_detail`(`backend_unsupported` · `not_approved` · `budget_unconfigured` · `ddgs_package_missing` · `ddgs_backends_unbounded` · `ddgs_options_invalid` · `ddgs_backend_unknown` · `ddgs_backend_host_unlisted` · `limits_or_identities_invalid` · `config_invalid`)를 돌려주고, `TravelSources.unavailable['activity_web']`에도 같은 이유가 붙습니다.
- 기본값은 계속 `enabled: false`입니다. 켜는 것은 사용자 승인 뒤 배포 담당이 합니다.
