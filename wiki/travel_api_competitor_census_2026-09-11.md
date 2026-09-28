# 여행 일정·관리 API/MCP 경쟁업체 전수조사

## 조사 결론

2026년 9월 11일 기준 공개 웹에서 공식 개발자 문서, 회사 발표 또는 공식 MCP Registry 항목으로 확인되는 업체를 조사했다. 조사 대상은 외부 개발자나 AI 에이전트가 여행 일정의 생성·통합·조회·변경 또는 예약 실행 기능을 호출할 수 있는 서비스다. 항공·숙소 검색 API처럼 일정 상태를 관리하지 않는 서비스는 인접군으로 분리했다.

가장 중요한 결론은 다음과 같다.

1. **우리 제품과 가장 가까운 공개 API/MCP 경쟁사는 mTrip, Nezasa TripBuilder, Sabre, Vibe, TripIt이다.** 단순 일정 생성이 아니라 예약 통합, 일정 갱신, 변경 알림 또는 사후 서비스까지 연결한다.
2. **이름이 비슷했던 업체는 mTrip일 가능성이 높다.** mTrip은 Mindtrip이나 마이리얼트립과 다른 회사이며 REST API·SDK, 실시간 일정 동기화, 항공편 변경 알림, 여행자 메시징을 제공한다.[^1][^2]
3. **Nezasa TripBuilder는 현재 가장 직접적인 API 제품 경쟁자다.** 공개 API 전반에 MCP를 지원하고, 자연어에서 예약 가능한 맞춤 일정을 만드는 Itinerary API, Booking API와 웹훅, Notification API를 제공한다.[^3][^4]
4. **Sabre는 가장 강한 실행 인프라 경쟁자다.** 에이전트용 API와 자체 MCP 서버로 검색·예약·서비스·실시간 최적화를 지원하며, 실제 파트너 환경에서 재발권·교환·사후 처리를 운영 중이라고 밝혔다.[^5][^6]
5. **Mindtrip에 대한 기존 평가는 수정해야 한다.** 외부 개발자용 공개 API는 확인되지 않았지만 2026년 5월 Sabre·PayPal 기반 대화형 항공 예약을 실제 출시했다. 공식 파트너 발표는 이후 일정 변경을 포함한 예약 후 관리까지 목표로 명시한다.[^7][^8]
6. **국내에서는 마이리얼트립이 이미 파트너 API와 MCP 연동을 공개했다.** 항공·숙소·투어티켓 조회 및 제휴 수익 추적이 중심이며, 전체 일정의 지속 관리 API라는 근거는 없다.[^9]
7. **놀유니버스는 직접 경쟁 잠재력이 크지만 아직 개발 단계다.** 여행 AI 에이전트 1종과 외부 호출 가능한 MCP 8종을 2026년 말까지 개발하는 목표이며, 도구 명세와 일반 이용조건은 공개되지 않았다.[^10][^11]
8. 공개 근거에서 **예약·운항 변화 감지 → 모든 후속 일정의 영향 계산 → 제약을 보존한 재계획 → 고객 승인 → 실제 수행 확인**을 하나의 소비자용 외부 API로 완전히 제공한다고 입증된 업체는 찾지 못했다. 그러나 Sabre·BizTrip AI·Nezasa·mTrip·Vibe가 이 영역의 상당 부분을 이미 점유한다.

## 조사 범위와 판정 기준

‘전수조사’는 웹에 공개되어 검색 가능한 한국어·영어 자료 안에서 다음 조건 중 하나를 충족하는 업체를 최대한 포괄했다.

- 공식 REST/SOAP/OpenAPI 문서가 존재한다.
- 회사가 외부 고객용 API·SDK·MCP 지원을 공식 페이지에서 명시한다.
- 공식 MCP Registry에 여행 서버가 등록되어 있다.
- 개발 완료 전이면 공공사업 원문이나 회사 발표에서 외부 호출 요건과 일정이 확인된다.

사설 GitHub 데모, 단순 LLM 프롬프트 앱, API가 있다고 주장하지만 호출 규격·고객대상·접근절차가 전혀 없는 검색 결과는 핵심 경쟁군에서 제외했다. 비공개 계약 API, 검색엔진에 색인되지 않은 업체, 지역별 비영어 서비스까지 전 세계 모든 공급자를 수학적으로 완전하게 증명하는 것은 불가능하므로 이 문서의 ‘전수’는 **공개 검증 가능한 시장 표본의 전수**를 뜻한다.

판정 항목은 다음과 같다.

- **생성:** 선호·예산·기간을 받아 일정을 새로 생성
- **통합:** 항공·숙소·활동·교통 예약을 하나의 여행 상태로 통합
- **변경:** 기존 일정·예약을 수정·취소·재발권
- **이벤트:** 웹훅·푸시·항공편 상태 등 변화 감지 수단
- **외부 호출:** 제3자 앱·에이전트가 API/MCP로 호출
- **지속 관리:** 고객 요청이 없어도 변화 감지 후 전체 영향 검증·대안 제시·후속 확인

## 이름이 비슷한 네 업체

| 업체 | 정체 | 외부 API/MCP | 현재 확인된 핵심 기능 | 혼동 방지 |
|---|---|---:|---|---|
| **마이리얼트립** | 한국 OTA | 예 | 항공·숙소·투어티켓 검색, 제휴 링크·예약·수익 정보, MCP 연동 | 국내 상품 유통 API |
| **Mindtrip** | 미국 소비자 AI 여행 플랫폼 | 공개 개발자 API 미확인 | 일정 생성·협업·예약 정리, 대화형 항공 검색·예약 출시, B2B 임베드 | Sabre API를 사용하는 소비자 제품 |
| **mTrip** | 여행사·TMC용 화이트라벨 여행 관리 플랫폼 | 예 | REST API·SDK, 예약 통합, 일정 동기화, 운항변경·위험 알림, 메시징 | 우리 기능과 가장 가까운 ‘비슷한 이름’ |
| **TripIt** | SAP Concur 계열 여행 일정 통합 서비스 | 예 | 여행·예약 객체 CRUD, 변경 Notification API, Pro 항공 상태 | 오래된 공개 API지만 일정 변경 이벤트 지원 |

## 핵심 경쟁군 전수표

상태 표기: **운영**은 공개 문서상 실제 접근 또는 고객 운영 근거가 있는 경우, **계약형**은 영업·승인 후 접근, **개발/탐색**은 출시 완료 근거가 없는 경우다.

| 업체 | 국가/시장 | 인터페이스·상태 | 생성 | 통합 | 변경·이벤트 | 우리와 중복 | 근거 |
|---|---|---|---:|---:|---|---|---|
| **mTrip** | 글로벌 B2B, 여행사·TMC | REST API·SDK·SSO, 계약형 운영 | 일부/Trip Genius | 예 | 실시간 동기화, PNR 변경 푸시, 운항·위험 알림 | **매우 높음**. 단, 자동 전체 재계획·수행확인 근거는 없음 | [공식 Leisure/API](https://www.mtrip.com/en/leisure-travel/), [Business Travel](https://www.mtrip.com/en/business-travel/apps/) |
| **Nezasa TripBuilder** | 글로벌 B2B/B2C 여행 브랜드 | Public APIs + MCP, 계약형 운영 | **예, from-prompt** | 예 | Booking Webhooks, Notification API, post-booking Cockpit | **매우 높음**. 예약 가능한 AI 일정과 운영 검증까지 제공 | [MCP 지원](https://help.tripbuilder.app/en/articles/746057-tripbuilder-mcp-api-support), [Planner Copilot/API](https://help.tripbuilder.app/en/articles/414843-planner-copilot) |
| **Sabre** | 글로벌 여행 유통·엔터프라이즈 | Agentic APIs + 자체 MCP, 운영/계약형 | 파트너 에이전트가 수행 | 예 | 재예약·재발권·환불·서비스·실시간 최적화 | **매우 높음**. 공급·거래 실행은 우리보다 강함 | [Agentic API 발표](https://investors.sabre.com/news-releases/news-release-details/sabre-seizes-first-mover-position-comprehensive-agentic-apis), [실운영 사례](https://investors.sabre.com/node/19991/pdf) |
| **Vibe** | 영국·글로벌 TMC | Remote MCP, Vibe 고객용 운영 | 대화형 검색·조합 | 예 | 기존 예약 조회, 변경·취소·서비스 요청 | **매우 높음**. 외부 개인 AI 접점과 예약 관리가 직접 중복 | [Vibe MCP](https://www.vibe.travel/mcp/) |
| **TripIt** | 글로벌 소비자·파트너 | REST/XML API v1 + Notification API, 운영 | 자동 예약 통합 중심 | **예** | 여행 객체 변경 푸시, Pro 항공편 상태 | **높음**. 이벤트와 최신 여행 상태는 중복, 재계획은 미확인 | [API v1](https://tripit.github.io/api/doc/v1/), [Notification API](https://tripit.github.io/api/doc/v1/notification.html) |
| **SAP Concur** | 글로벌 기업여행 | Itinerary API OAuth 2.0, 파트너/고객용 | 아니오 | **예** | 여행·예약 생성·조회·수정·삭제 | **높음**. 기업여행 데이터 허브, 선제 재계획은 별도 | [Itinerary Service](https://github.com/concur/developer.concur.com/blob/preview/src/api-reference/travel/itinerary/itinerary.markdown) |
| **BizTrip AI** | 미국 기업여행 | 자체 공개 API 미확인; Sabre MCP/API 기반 제품 운영 | 예 | 예 | 실시간 일정관리, 자동 disruption 재예약, 운임 하락 재예약 주장 | **매우 높음** 기능 경쟁자. 외부 API 공급자는 아님 | [공식 제품](https://www.biztrip.ai/), [Sabre 제휴](https://investors.sabre.com/news-releases/news-release-details/sabre-and-biztrip-ai-announce-strategic-partnership-deliver) |
| **Mindtrip** | 글로벌 소비자·관광기관 | B2B 임베드, 공개 개발자 API 미확인 | **예** | 예약·영수증 통합 | 항공 예약 출시; 파트너 로드맵에 일정 변경 | **높음** 제품 경쟁자. 현재 공개 API 공급자는 아님 | [공식 서비스](https://mindtrip.ai/), [Sabre·PayPal 제휴](https://investors.sabre.com/news-releases/news-release-details/sabre-paypal-and-mindtrip-partner-deliver-industrys-first-end), [출시](https://mindtrip.ai/press/mindtrip-launches-travels-first-all-in-one-agentic-ai-flight-booking-e-2026-05-06) |
| **Perk** | 글로벌 기업여행·경비 | Perk MCP, 계정 고객용 운영 | 대화형 검색·예약 | 예 | MCP에서 여행 조회·승인; 앱에서 변경·취소 | **높음** 기업시장. MCP의 자율 disruption 처리 범위는 미확인 | [Perk MCP](https://support.perk.com/hc/en-us/articles/28593327231900-About-the-Perk-MCP), [여행 변경](https://support.perk.com/hc/en-us/articles/21926011340828-Change-or-cancel-a-trip) |
| **Travelport TripServices** | 글로벌 GDS·여행 판매자 | REST API 운영; MCP 기반 인터페이스 구축 | 외부 에이전트가 조합 | 예 | 발권·교환·취소·환불·서비스 | **높음** 실행 기반. 소비자 일정 CS 완제품은 아님 | [TripServices](https://developer.travelport.com/), [MCP 협력](https://www.travelport.com/press-releases/cognizant-anthropic-collaboration-to-power-travel-technology-ai-era) |
| **놀유니버스** | 한국 소비자 OTA | AI 에이전트 1종 + MCP 8종, **2026년 말 개발 목표** | 기존 NOL 앱에서 예 | 예약 데이터 연동 | 외부 호출 요구사항은 확인, 세부 명세 미공개 | **높은 잠재 경쟁**. 출시·지속관리 기능은 미확인 | [회사 발표](https://nol-universe.com/ko/newsroom/pressRelease/detail?prNo=2535), [NIA 공모](https://www.nia.or.kr/site/nia_kor/ex/bbs/View.do?bcIdx=29494&cbIdx=78336) |
| **마이리얼트립** | 한국 소비자 OTA·파트너 유통 | REST API + MCP 안내, 파트너 운영 | 상품 조합 보조 | 상품·예약 링크 중심 | 수익·예약 조회; 전체 일정 이벤트 미확인 | **중간**. 외부 에이전트 유통은 중복, 지속 일정관리는 약함 | [개발자센터](https://docs.myrealtrip.com/), [MCP PoC 설명](https://blog.myrealtrip.com/ai-travel-conversation-search/) |
| **Travefy** | 글로벌 여행사·DMC | OpenAPI, 유료 계약형 운영 | 일정 자동화 가능 | 예 | 여행·일정·제안서·상태 양방향 동기화 | **높음** B2B 일정 상태 API, 자동 감지·재계획 근거는 없음 | [API 안내](https://intercom.help/travefy/en/articles/15385261-travefy-api), [가격](https://intercom.help/travefy/en/articles/956803-api-pricing) |
| **WeTravel** | 그룹여행·투어 사업자 | Partner API v3, Bearer, 운영 | 구조화 작성/AI import | 예 | 일정 PATCH 후 참가자용 사본 즉시 게시 | **중간~높음**. 운영자 중심 일정 배포·결제 | [Create Trip](https://developer.wetravel.com/v3/reference/createtrip), [Update Itinerary](https://developer.wetravel.com/v3/reference/updatetripitinerary) |
| **Wetu** | 여행사·투어 사업자 | Itinerary API v7, REST JSON·SOAP XML | API로 생성 | 예 | 생성·수정·삭제, 고객 열람 알림 옵션 | **중간~높음**. 일정 출판·열람 추적 중심 | [Itinerary API v7](https://knowledge.wetu.com/itinerary-api-v7) |
| **AXUS Travel App** | 고급여행 자문사 | Push/Pull API, 등록 파트너용 | 직접 생성보다 구조 입력 | **예** | 전체 일정 push/update 및 updated-at 조회 | **중간~높음**. 여행사 일정 허브, 자동 재계획 미확인 | [API 문서](https://axustravelapp.com/api/v1/docs), [Push](https://axustravelapp.com/api/v1/docs/push), [Pull](https://axustravelapp.com/api/v1/docs/pull) |
| **Simplified.Travel** | DMO·호텔·여행 브랜드 | API/SDK·위젯, 계약형 | **예** | CRM·예약엔진 연동 주장 | Live Itinerary, 디지털 컨시어지 | **중간**. 관광 웹사이트 내 일정 생성·추천 | [공식 제품](https://www.simplified.travel/) |
| **Jettova** | 개발자용 여행 AI | REST API, 키 기반 | **예** | 비용·예약링크 포함 | 지속 이벤트·재계획 미확인 | **중간 이하**. 생성 API가 주된 중복 | [개발자 문서](https://www.jettova.com/developers) |
| **Plantrip** | 개발자·AI 에이전트 | REST + MCP, 셀프서비스 키 | **예** | 비용·날씨·가이드 | 저장·변경 감시 미확인 | **중간 이하**. 저비용 생성 도구 경쟁 | [Agent API](https://plantrip.io/developers) |
| **JourneyBay** | AI 에이전트 여행 도구 | MCP + API 문서, 운영 표방 | 예 | 여행 생성·대화 | 지속관리 범위 미확인 | **중간 이하**, 공개 실적 검증 필요 | [개발자 문서](https://mcp.journeybay.co/) |
| **Travel Compositor** | 글로벌 여행사·투어 사업자 | B2B 플랫폼/API 통합 | AItrips·Tripplanner | **예** | Repricing·Rebooking 기능 | **높음** 상업 패키징·재예약, 외부 일정 API 명세는 비공개 | [Tour Operator 솔루션](https://travelcompositor.com/en/solutions/tour-operators/) |
| **TRIPS/Umapped** | Flight Centre 계열 여행사 일정 배포 | 제휴·내부 통합, 공개 API 명세 미확인 | 아니오 | 예 | 출발 24시간 전부터 지연·취소 알림 | **중간**. 변화 알림·동기화가 중복 | [공식 지원/릴리스](https://support-trips.umapped.com/portal/en/kb/articles/2025-trips-release-notes) |

## 예약·공급 MCP/API 인접군

다음 업체는 외부 AI가 실제 여행상품을 검색·예약·취소할 수 있게 하지만, 전체 여행 일정의 제약·상태를 지속적으로 관리한다는 근거가 부족하다. 우리 서비스의 직접 대체재보다는 데이터·거래 파트너이자 향후 수직 통합 경쟁자다.

| 업체 | 제공 범위 | 상태·접근 | 직접 경쟁도 | 근거 |
|---|---|---|---|---|
| **Dida** | 200만+ 호텔 검색·비교·예약 MCP | 승인된 B2B 파트너, 2026-07 출시 | 중간 | [Dida MCP](https://www.dida.com/news/dida-mcp---turning-ai-travel-advice-into-confirmed-hotel-bookings) |
| **GetOffers** | 항공·호텔·이동·활동·차·요트 검색, 예약·조회·취소 | 베타, 파트너 API 키 | 중간 | [MCP](https://www.getoffers.com/integrations) |
| **FareEagle** | 인도 항공·호텔·버스 검색·예약·취소 | 공개 MCP, 검색은 무인증 표방 | 중간 이하 | [AI Travel API/MCP](https://www.fareeagle.com/ai-travel-api) |
| **Stayker/1Stay** | 호텔 검색·요금·예약·상태·취소 | MCP + REST, 샌드박스/월 과금 | 중간 이하 | [Developer Platform](https://stayker.com/build/) |
| **Valyzen** | 항공 검색·운임 잠금·결제·예약 조회 | MCP, 계정·토큰·지출한도 | 중간 이하 | [Developers](https://flyvalyzen.ai/developers) |
| **Gondola** | 포인트/현금 항공·호텔·렌터카 검색, 일부 체크아웃 | MCP, 사용자 승인·계정 연결 | 중간 이하 | [Gondola MCP](https://www.gondola.ai/mcp) |
| **TravelCode** | 항공·호텔 검색·예약관리·상태 | 오픈소스 MCP + 기업 API 연결 | 중간 이하 | [MCP 저장소](https://github.com/Travel-Code-Inc/mcp-travelcode) |
| **WorldAirfares** | 항공 검색·페이지·여정 상세 | 공식 Registry 등록 로컬 MCP | 낮음 | [Registry](https://registry.modelcontextprotocol.io/?q=com.worldairfares%2Fflights-mcp) |
| **Bitvoya** | 고급 호텔 검색·요금비교·견적·체크아웃 | 공식 Registry 등록 | 낮음 | [Registry](https://registry.modelcontextprotocol.io/?q=com.bitvoya%2Fbitvoya-mcp) |
| **Travelpayouts MCP** | 항공 검색·인기노선·가격 달력 | 비공식 커뮤니티 MCP/공식 Registry 등록 | 낮음 | [Registry](https://registry.modelcontextprotocol.io/?q=io.github.theYahia%2Ftravelpayouts-mcp) |
| **Autonomad** | 항공·호텔·활동·이벤트 예약 | 공식 Registry 등록 | 중간 이하, 실적 별도 검증 | [Registry](https://registry.modelcontextprotocol.io/?q=ai.autonomad%2Ftravel) |
| **Augworlds Travel World** | 항공·호텔·브랜드 정보 조회 | 읽기 전용 MCP·OAuth | 낮음 | [Registry 목록](https://prod.registry.modelcontextprotocol.io/) |
| **Expedia Group** | 기존 여행 API에 MCP 계층 연결 구상 | **탐색 단계** | 잠재적으로 높음 | [AI Solutions](https://developers.expediagroup.com/docs/ai-solutions) |
| **NOL/Swallow API** | 상품조회, 사전주문·결제·취소·주문조회, 가격·재고 콜백 | Proprietary B2B API 운영 | 중간 이하; 8종 MCP와 동일성 미확인 | [NOL API 문서](https://open-api.swallow.goglobal.travel/) |

## 우리 제품과의 기능 중복 지도

| 기능 층 | 이미 강한 업체 | 시장 상태 | 우리 차별화 여지 |
|---|---|---|---|
| AI 일정 생성 | Nezasa, Mindtrip, NOL, Simplified.Travel, Jettova, Plantrip | 이미 보편화 | 낮음. 생성 자체를 핵심 가치로 삼기 어려움 |
| 예약 가능한 일정 조합 | Nezasa, Sabre 기반 Mindtrip/BizTrip, Travel Compositor | 상용화 | 공급계약 없이 정면승부 어려움 |
| 외부 개인 AI 연결 | Nezasa MCP, Vibe MCP, Perk MCP, 마이리얼트립 MCP, 다수 예약 MCP | 빠르게 확산 | ‘API/MCP 제공’만으로 차별화 불가 |
| 여러 예약을 하나의 일정으로 통합 | TripIt, Concur, mTrip, Travefy, AXUS, Wetu | 성숙시장 | 데이터 정규화 품질·권한·한국어에 한정된 여지 |
| 일정 변경을 여러 화면에 즉시 반영 | mTrip, WeTravel, Travefy, Wetu | 상용화 | 단순 동기화는 차별화 약함 |
| 운항·예약 변화 알림 | TripIt, mTrip, TRIPS, GDS/TMC 플랫폼 | 상용화 | 알림 이후 전체 영향 분석이 필요 |
| 예약 변경·취소·재발권 | Sabre, Travelport, Vibe, Perk, BizTrip AI | 기업여행 중심 상용화 | 계약·거래권한이 핵심 진입장벽 |
| 전체 일정 제약 검증 | Nezasa Itinerary Checker가 가장 근접 | 일부 상용화 | 식사·보행·동행·예산·필수경험을 일관되게 보존하는 검증 품질 |
| 고객 요청 전 선제 재계획 | BizTrip AI의 disruption 재예약, Sabre agentic servicing이 근접 | 항공·기업여행부터 시작 | 레저여행 전체 요소로 확장하고 근거·승인 범위를 명시 |
| 변경 후 실제 수행 확인 | 공개 제품 근거 희박 | 공백 가능성 | 제안만 하지 않고 승인·예약·도달·미해결 상태까지 닫는 운영 루프 |

## 업체별 핵심 판정

### 1. mTrip

mTrip은 단순 일정표 제작기가 아니다. 예약 데이터를 GDS·중간/백오피스·이메일·문서·API에서 통합하고, REST API로 예약을 넣거나 상세 일정을 가져오며, 연결된 모바일·웹 앱에 변경을 실시간 전달한다. 기업여행 제품은 PNR 변경을 추적해 푸시 알림을 보내고, 운항중단 알림·여행자 메시징·선택형 위험관리까지 제공한다.[^1][^2]

따라서 **일정 데이터 허브 + 변화 알림 + 고객 전달** 구간은 우리와 직접 겹친다. 다만 공개 자료는 변경된 항공편이 뒤의 식사·관광·이동·필수예약에 미치는 영향을 자동 계산하고, 제약을 보존한 대안을 만든 뒤 실제 수행까지 확인한다고 입증하지 않는다.

### 2. Nezasa TripBuilder

Nezasa는 2026년 7월 공개 API 전반에 MCP 지원을 발표했다. 외부 AI는 Discovery API로 상품·재고를 검색하고, Itinerary API로 선호·예산·여행 스타일에 맞는 다중 상품 일정을 만들며, Booking API로 실시간 예약 데이터를 분석할 수 있다. Itinerary API의 `from-prompt` 엔드포인트는 자연어 설명을 예약 가능한 일정으로 변환한다.[^3][^4]

또한 Booking API Webhooks와 Notification API가 개발자 문서 목록에 있으며, Tai Workbench의 Itinerary Checker는 일정 일관성·미확정 서비스·시간 공백·숙박 누락·승객·가격 문제를 심각도별로 찾는다.[^12] 이는 우리의 ‘계획 검증’과 가장 가깝다. 다만 공개 자료상 Tai 에이전트는 읽기 중심이고, 여행 중 소비자에게 자동으로 전체 대안을 실행하는 폐루프는 확인되지 않았다.

### 3. Sabre와 BizTrip AI

Sabre는 2025년 에이전트용 API와 자체 MCP 서버를 발표했고, 2026년에는 운영 파트너에서 재발권·동적 교환·사후 서비스가 실제로 작동한다고 발표했다.[^5][^6] BizTrip AI는 Sabre 기반으로 기업정책·선호를 반영해 여행을 예약하고, 운임 하락과 disruption을 감시해 항공·호텔·차량을 재예약한다고 설명한다.[^13]

이 조합은 우리의 ‘지속 관리’ 주장에 가장 큰 위협이다. 차이는 기업여행·예약거래 중심이라는 점이다. 우리가 레저여행의 식사, 관광지 휴무, 보행 제약, 동행자 조건까지 다룬다면 범위는 다르지만, ‘AI가 여행 중에도 계속 관리한다’는 문구 자체는 더 이상 독점적이지 않다.

### 4. Vibe MCP

Vibe는 ChatGPT·Claude·Microsoft Copilot에서 기업여행을 검색·예약하고, 기존 예약과 일정을 조회하며, 변경·취소·서비스 요청을 할 수 있는 MCP를 제공한다. 실제 TMC 고객이 실환경에서 운영·시험하고 있다는 근거도 있다.[^14]

외부 개인 AI가 여행 플랫폼을 호출한다는 구조가 우리와 정확히 겹친다. 다만 사용자 요청 없이 변화가 발생했을 때 전체 레저 일정을 선제 재구성하는 기능은 공개 자료에서 확인되지 않는다.

### 5. TripIt과 SAP Concur

TripIt API는 항공·숙박·철도·차량·활동·식당 등 여행 객체를 생성·조회·교체·삭제할 수 있고, Notification API는 여행 객체가 바뀌었을 때 HTTPS 알림을 보낸다. Pro 데이터에는 항공편 지연·취소·우회 상태가 포함된다.[^15][^16] SAP Concur의 Itinerary API는 여러 공급원의 예약을 통합 일정으로 만들고 여행·예약 리소스를 CRUD할 수 있다.[^17]

기술적으로 이들은 우리 지속 관리 루프의 **상태 저장과 이벤트 입력층**을 이미 제공한다. 하지만 이벤트 이후 생활 일정 전체를 재설계하는 판단층은 아니다.

### 6. 국내 업체

마이리얼트립 개발자센터는 파트너 API로 실시간 항공·숙소·투어티켓 가격을 조회하고, API 키를 발급받아 MCP에서 상품을 검색하며, 링크에서 발생한 예약과 수익을 확인한다고 안내한다.[^9] 과거의 MCP PoC 수준을 넘어 정식 개발자센터가 존재하므로 경쟁자료는 수정해야 한다. 단, 일정 전체 CRUD·웹훅·선제 재계획 근거는 없다.

놀유니버스는 기존 NOL 앱에서 AI 일정 생성과 예약 데이터 연동을 운영한다. 별도의 정부사업에서 외부 호출 가능한 여행 AI 에이전트와 MCP 8종을 2026년 말까지 만들 예정이지만, 현재는 각 도구의 이름·스키마·인증·요금·출시 주소가 공개되지 않았다.[^10][^11] 기존 Swallow API는 주문·재고 B2B 채널 API이며 새 MCP 8종과 동일하다고 볼 수 없다.[^18]

## 경쟁전략 권고

### 제품 정의 수정

‘외부 개인 에이전트에 여행 API를 제공한다’는 문장은 이미 Nezasa, Vibe, Perk, 마이리얼트립, Sabre 계열과 겹친다. 다음처럼 범위를 좁혀야 한다.

> 여러 출처의 여행 조건을 하나의 버전 상태로 유지하고, 예약·운영·현장 변화가 생기면 남은 전체 일정의 시간·이동·예산·동행 제약을 검증하여, 근거와 변경 영향을 제시하고 승인된 조치의 실제 수행까지 추적하는 레저여행 지속관리 API.

### 반드시 비교시험할 5개 업체

1. **Nezasa TripBuilder:** 동일 자연어 요청으로 예약 가능한 일정 생성과 Itinerary Checker 결과 비교
2. **mTrip:** PNR 변경 후 앱·API 업데이트 속도, 알림 범위, 후속 일정 영향 처리 확인
3. **Vibe MCP:** 외부 AI에서 예약 조회·변경·취소와 승인 흐름 재현
4. **TripIt:** Notification API 이벤트를 입력원으로 사용할 수 있는지 파트너 조건 확인
5. **BizTrip AI/Sabre:** disruption 재예약 범위, 사용자 승인 방식, 항공 외 요소와 후속 수행 확인 범위 확인

### 90일 검증 과제

- 휴무, 항공 지연, 식당 예약 취소, 동행자 피로, 우천 등 동일한 10개 사건을 경쟁제품에 주입한다.
- 고객 추가 지시 없이 감지하는지, 고정 예약과 조건을 보존하는지, 전체 남은 일정의 충돌을 다시 계산하는지 측정한다.
- ‘알림만 함’, ‘단일 예약만 변경’, ‘전체 일정 대안 제시’, ‘승인 후 거래 실행’, ‘실제 수행 확인’의 다섯 단계로 결과를 분리한다.
- MCP/API가 있어도 일반 공개, 유료 셀프서비스, 계약형, 특정 TMC 고객 전용, 개발예정 상태를 각각 기록한다.
- 데이터 공급계약 없이 구현할 수 없는 예약 변경·재발권 기능은 MVP 약속에서 제외한다.

## Sources

[^1]: mTrip. “[Leisure Travel Solutions for Agencies and Tour Operators](https://www.mtrip.com/en/leisure-travel/).” Accessed 2026-09-11.
[^2]: mTrip. “[The Business Travel App for TMCs and Corporations](https://www.mtrip.com/en/business-travel/apps/).” Accessed 2026-09-11.
[^3]: Nezasa. “[TripBuilder MCP API Support](https://help.tripbuilder.app/en/articles/746057-tripbuilder-mcp-api-support).” 2026-07-14.
[^4]: Nezasa. “[Planner Copilot](https://help.tripbuilder.app/en/articles/414843-planner-copilot).” Updated 2026.
[^5]: Sabre. “[Sabre seizes first-mover position with comprehensive agentic APIs for travel](https://investors.sabre.com/news-releases/news-release-details/sabre-seizes-first-mover-position-comprehensive-agentic-apis).” 2025-09-23.
[^6]: Sabre. “[Sabre scales agentic AI deployment as Ultra Group expands globally under Linex](https://investors.sabre.com/node/19991/pdf).” 2026-06-17.
[^7]: Sabre, PayPal, Mindtrip. “[End-to-end agentic AI experience for travel](https://investors.sabre.com/news-releases/news-release-details/sabre-paypal-and-mindtrip-partner-deliver-industrys-first-end).” 2026-02-12.
[^8]: Mindtrip. “[Mindtrip launches all-in-one agentic AI flight booking](https://mindtrip.ai/press/mindtrip-launches-travels-first-all-in-one-agentic-ai-flight-booking-e-2026-05-06).” 2026-05-06.
[^9]: 마이리얼트립. “[마이리얼트립 API 사용 가이드](https://docs.myrealtrip.com/).” Accessed 2026-09-11.
[^10]: 놀유니버스. “[여행 특화 AI 에이전트 개발 발표](https://nol-universe.com/ko/newsroom/pressRelease/detail?prNo=2535).” 2026-08-18.
[^11]: 한국지능정보사회진흥원. “[고수요·체감형 대표 AI 에이전트 및 에이전트 도구 개발·육성 지원 공모](https://www.nia.or.kr/site/nia_kor/ex/bbs/View.do?bcIdx=29494&cbIdx=78336).” 2026-06-08.
[^12]: Nezasa. “[Tai Workbench](https://nezasa.com/tai-workbench/).” Accessed 2026-09-11.
[^13]: BizTrip AI. “[The Intelligent Corporate Travel Agent](https://www.biztrip.ai/).” Accessed 2026-09-11.
[^14]: Vibe. “[MCP for TMCs and Corporate Travel](https://www.vibe.travel/mcp/).” Accessed 2026-09-11.
[^15]: TripIt. “[TripIt API Documentation v1](https://tripit.github.io/api/doc/v1/).” Accessed 2026-09-11.
[^16]: TripIt. “[Notification API](https://tripit.github.io/api/doc/v1/notification.html).” Accessed 2026-09-11.
[^17]: SAP Concur. “[Itinerary Service v1](https://github.com/concur/developer.concur.com/blob/preview/src/api-reference/travel/itinerary/itinerary.markdown).” Accessed 2026-09-11.
[^18]: NOL. “[NOL API Documentation 1.2.0](https://open-api.swallow.goglobal.travel/).” Accessed 2026-09-11.

