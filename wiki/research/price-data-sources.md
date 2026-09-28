---
type: reference
title: 가격 데이터 소스 실측
description: 식당·액티비티 가격을 TourAPI·OSM·카카오에서 불러 채움률을 재고, 상용 API와 공공 후보를 훑은 기록. 2026-09-22
status: draft
domain: travel
---

# 가격 데이터 소스 실측

`[실측 2026-09-22]` 예산을 설문으로 받으려면 **대안의 추가 비용**을 낼 수 있어야 한다(v11 §6-C 사전식 비교의 둘째 기준). 그 값이 실제로 오는지 부른 기록이다. 짝이 되는 문서는 [식이 제약](dietary-data-sources.md) · [무장애·이동 제약](accessibility-data-sources.md).

## 한 줄 결론

**무료로 가격을 얻을 길이 지금은 없다.** 식당은 공공 소스 전부 0%, 액티비티는 문화시설 10%다. 금액 비교를 포기하고 **가격대 비교 + 무료→유료 전환 판정**으로 가는 것이 현실적이다.

---

## 1. 불러서 잰 것

### 한국관광공사 TourAPI (KorService2) — [서비스 안내](https://www.data.go.kr/data/15101578/openapi.do) · 무료

종류별로 `detailIntro2` 필드를 전부 뽑고 서울 표본의 채움률을 셌다.

| 종류 | 가격 필드 | 서울 표본 |
|---|---|---|
| 음식점(39) | **없음** | 필드 자체가 없다 |
| 관광지(12) | **없음** | 경복궁·창덕궁·국립중앙박물관 `overview` 에도 금액 표기 **0개** |
| 문화시설(14) | `usefee` | 40건 중 무료 20 · **숫자 4** · 자연어 12 · 빈칸 4 |
| 행사·공연(15) | `usetimefestival` | 40건 중 무료 36 · 숫자 3 · 자연어 1 |
| 레포츠(28) | `usefeeleports` | **상세가 26/30 = 87% 비어 있다.** 요금은 1건, 그마저 「시설별 상이」 |
| 쇼핑(38) | `saleitemcost` | 빈칸 |

**금액을 숫자로 뽑을 수 있는 건 문화시설 4/40 = 10%다.** 나머지는 「※ 전시마다 상이」 · 「프로그램별 상이」 같은 자연어다.

★**경복궁 입장료를 TourAPI 에서 얻을 방법이 없다.** 필드도 없고 본문에도 금액이 없다. 이게 문제의 크기를 보여준다.

### OpenStreetMap ([Overpass API](https://overpass-api.de/), 미러 [private.coffee](https://overpass.private.coffee/)) — 키 없음 · 무료 · [ODbL](https://www.openstreetmap.org/copyright)

| 서울 | 전체 | `fee`(유무) | `charge`(금액) |
|---|---|---|---|
| `tourism=attraction` | 241 | 7건 = **2.9%** | **0건** |
| `tourism=museum` | 283 | 27건 = **9.5%** | **0건** |
| `amenity=restaurant` | 26,555 | — | `price_range` **0건** |

금액이 들어가는 `charge` 는 한 건도 없다. **가격 소스로는 탈락이다** — 채식 태그에서는 가장 좋았던 것과 대조된다.

### 그 밖에 이미 확인한 것

| 소스 (링크) | 비용 | 가격 필드 |
|---|---|---|
| [카카오 로컬](https://developers.kakao.com/docs/latest/ko/local/dev-guide) | 무료(일 한도) | 응답 필드 12개에 **없음** |
| 네이버 지역 검색 (`developers.naver.com/docs/serviceapi/search/local/local.md`) | 무료 | 응답 필드 9개에 **없음** (문서는 이 환경에서 열리지 않아 `[외부]`) |
| [한국문화정보원 전국 세계 음식점](https://www.data.go.kr/data/15111398/fileData.do) (9,502건) | **무료** | 28개 열에 **없음** |

---

## 2. 무료 공공 후보 — 신청하면 열릴 수 있다

`[외부 2026-09-22]` 공공데이터포털에서 「입장료」·「관람료」로 찾았다. **셋 다 아직 못 불렀다** — 별도 키나 활용신청이 필요하다.

| 서비스 (링크) | 무엇 | 비용 | 조건 |
|---|---|---|---|
| ★[한국문화정보원_전국문화기반시설총람 조회서비스](https://www.data.go.kr/data/15125097/openapi.do) | 전국 도서관·박물관·미술관·문예회관, **`관람료` 필드 포함** | **무료** | **자동승인** · 일일 10,000건 |
| [문화체육관광부_12개 기관 전시정보](https://www.data.go.kr/data/15105037/openapi.do) | 전시 관람료 | 무료 | 활용신청 |
| [예술경영지원센터_KOPIS 공연목록](https://www.data.go.kr/data/15097805/openapi.do) | 공연 티켓 가격 | 무료 | 활용신청 |
| [KOPIS 오픈API 안내](https://kopis.or.kr/por/cs/openapi/openApiList.do?menuId=MNU_00074) | 위의 원 제공처 | 무료 | 자체 키 |

★**첫째가 가장 유망하다.** 자동승인이고 무료이고 일일 한도가 10,000건이다. `api.kcisa.kr` 쪽은 **우리 `ACOP_DATA_GO_KR_KEY` 로 403**(`API Key is not valid`)이 떨어졌다 — KCISA 자체 키가 따로 필요하다.

지자체 단위 파일데이터(대구 북구 관광지, 제천시 관광지, 서대문형무소역사관 등)에는 입장료가 들어 있지만 **서울 전체나 전국을 덮는 것은 없었다.**

확인 범위는 `data.go.kr` 의 「입장료」·「관람료」 두 낱말이다. **놓칠 수 있는 것** — 「이용요금」·「요금」·「사용료」 등 다른 낱말, 서울 열린데이터광장 자체 공개분.

---

## 3. 상용 API

| 소스 (링크) | 주는 것 | 비용 | 접근 |
|---|---|---|---|
| **[구글 Places](https://developers.google.com/maps/documentation/places/web-service/data-fields)** | `priceLevel`(5단계) + `priceRange`(금액) | **Enterprise** SKU — [$20/1,000건](https://developers.google.com/maps/billing-and-pricing/pricing) = 건당 약 **30원** · **월 1,000건 무료** | [카드 등록된 Cloud Billing 계정 필수](https://developers.google.com/maps/billing-and-pricing/billing-overview) |
| **[Viator 파트너 API](https://docs.viator.com/partner-api/affiliate/technical/)** | 액티비티 **상품 가격** (단건) | **가입 비용 없음** (수수료 8~12%는 예약이 일어날 때) | ★[Basic 은 사전 승인·인증 없이 즉시 시작](https://partnerresources.viator.com/travel-commerce/levels-of-access/). **벌크와 실시간은 Full**(승인·인증 필요). ★★**§11-A 제휴 일곱 조건에 걸린다**(아래) |
| **[TripAdvisor Terra API](https://docs.terra.tripadvisor.com/docs/overview)** | 식당·관광지 price level | **첫 1,000콜 무료** · 이후 종량제(공개 단가 미확인) | 자율 가입 · 표시 의무(버블 평점·리뷰 날짜·크레딧) |
| [Klook Partner API](https://klook.gitbook.io/openapi) | 액티비티 가격·재고 | 공개 단가 없음 | 파트너 신청·심사. 아시아태평양 강세라 한국 상품이 많다 |
| [GetYourGuide Partner API](https://api.getyourguide.com/) | 동 | 공개 단가 없음 | 파트너 포털 문의 |
| ~~[Amadeus Tours & Activities](https://developers.amadeus.com/self-service/category/destination-experiences/api-doc/tours-and-activities)~~ | 액티비티 가격 | — | ❌**셀프서비스 티어가 2026년 중반 폐지**돼 기존 키가 비활성화됐다 |

★**구글과 Terra 가 주는 것은 「가격대」이고, Viator·Klook 이 주는 것은 「판매가」다.** 우리가 §6-C 에서 쓰려는 추가 비용은 후자에 가깝지만, 후자는 **그 플랫폼에서 파는 상품에 한정**된다. 경복궁 입장료는 어느 쪽도 주지 않는다.

### Viator Basic 이 정확히 무엇을 주나

`[외부 2026-09-22]` 접근 등급 비교표를 그대로 옮긴다.

| 기능 | Basic | Full | Full + Booking |
|---|---|---|---|
| 사전 승인 | **불필요** | 필요 | 필요 |
| 인증(certification) | **불필요** | 필요 | 필요 |
| 단건 상품 데이터 | ✓ | ✓ | ✓ |
| 검색 조건으로 상품 요약 | ✓ | ✓ | ✓ |
| ★**단건 가용·가격 조회** | **✓** | ✓ | ✓ |
| 벌크 상품 데이터 | ✗ | ✓ | ✓ |
| 벌크 가용·가격 | ✗ | ✓ | ✓ |
| **실시간** 가용·가격 | ✗ | ✓ | ✓ |
| 리뷰 평점·개수 | ✓ | ✓ | ✓ |
| 여행자 리뷰 본문·사진 | ✗ | ✓ | ✓ |
| 결제·예약 | ✗ | ✗ | ✓ |
| 거래가 일어나는 곳 | viator.com | viator.com | 우리 사이트 |

★**Basic 으로 단건 가격 조회가 된다.** 우리가 필요한 건 대안 후보 몇 개의 가격이라 단건이면 족하다. 대신 **벌크도 실시간도 아니므로 감시 루프의 2분 폴링에는 못 쓴다** — 값을 읽는 시점과 고객이 여는 시점이 벌어진다.

### ★그런데 계획서 §11-A 에 걸린다

v11 §11-A 는 **「판정에 개입하는 광고·제휴」**를 넣으려면 일곱 가지를 다 지키라고 적었다 — ①판정과 분리 ②표시 ③거부해도 대안이 남을 것 ④후보 생성은 비상업 기준 ⑤같은 재검증 ⑥개입 감사 ⑦제휴 끄기.

Viator Basic 은 **제휴(affiliate) 프로그램**이고 전제가 「고객을 viator.com 으로 보내 거래를 마치게 한다」다. 우리가 예약 수수료를 받는 상품을 대안으로 내밀면 **④ 후보 생성이 비상업 기준이 아니게 된다.**

**두 갈래로 갈린다.**

| 쓰는 법 | §11-A 와의 관계 |
|---|---|
| 가격 **참고값으로만** 읽고 제휴 링크를 안 붙인다 | 판정과 분리(①)는 지켜진다. 단 **제휴 목적 외 사용이라 약관 확인이 필요하다** `[미확보]` |
| 대안 카드에 Viator 상품과 링크를 싣는다 | 일곱 조건을 **전부** 설계에 넣어야 한다. MVP 기간에 감당하기 어렵다 |

→ **가격만 읽는 쪽이 현실적이다.** 다만 그것이 약관상 허용되는지를 가입 전에 확인해야 한다 — 확인 전에는 「쓸 수 있다」고 적지 않는다.

---

## 4. 크롤링은 어디까지 되나

| 경로 | 판정 |
|---|---|
| [공공데이터포털](https://www.data.go.kr/) 파일데이터 직접 내려받기 | **정당하다.** 이미 그렇게 받았다(세계 음식점 9,502건) |
| [Overpass API](https://overpass-api.de/) | **정당하다.** OSM 의 공식 질의 창구다. 단 ODbL |
| 관광공사 공개 PDF | **정당하다.** 공개 배포물이다 |
| 네이버 플레이스 · 카카오맵 상세 · 캐치테이블 | ❌ 화면에는 가격이 있지만 공식 API 에 없다. **약관 위반 소지 + 기술적 차단.** 산출물에 「긁었다」가 남는다 |
| [Apify](https://apify.com/) 등의 Klook · [HappyCow](https://www.happycow.net/) · TripAdvisor 스크래퍼 | ❌ 같은 문제. 제3자가 남의 약관을 대신 지켜 주지 않는다 |

---

## 5. 그래서 어떻게 설계하나

지금 커버리지로는 **원래 항목과 대안 둘 다 가격이 있는 경우가 드물어서 「추가 비용」 기준이 대부분 건너뛰어진다.** 예산을 설문으로 받아 놓고 판정에 못 쓰는 상태가 된다 — 알러지에서 걸렸던 것과 같은 함정이다.

**권고 — 둘을 겹쳐 쓴다.**

1. **금액 대신 가격대로 비교한다.** 「같은 가격대 / 한 단 올라감 / 내려감」만 판정한다. 예산도 금액이 아니라 씀씀이 구간으로 받는다
2. **무료 → 유료 전환은 자동 적용에서 뺀다.** 무료였던 항목이 유료 대안으로 바뀌면 물어본다. 행사·공연은 36/40 = 90% 가 「무료」로 명시돼 있어 **이 판정은 지금 데이터로도 돌아간다**

## 6. 해 볼 순서

| # | 할 일 | 링크 | 비용 | 사람이 할 일 | 걸리는 시간 |
|---|---|---|---|---|---|
| 1 | 전국문화기반시설총람 → `관람료` 채움률 측정 | [data.go.kr/data/15125097](https://www.data.go.kr/data/15125097/openapi.do) | **무료** · 개발계정 일 10,000건 | 로그인 후 **활용신청** 한 번 (개발·운영 **둘 다 자동승인**) | 분 단위 |
| 2 | Viator Basic → 서울 액티비티 가격 확인 | [levels-of-access](https://partnerresources.viator.com/travel-commerce/levels-of-access/) · [API 문서](https://docs.viator.com/partner-api/affiliate/technical/) · [약관](https://www.viator.com/support/termsAndConditions) | **가입 0원** (수수료 8~12%는 예약 발생 시) | 제휴 가입. **사전 승인·인증 없음.** ★**가입 전에 「가격만 읽고 링크는 안 붙이는 것」이 약관상 되는지 확인** | 시간 단위 |
| 3 | 구글 → 서울 식당 30곳 `priceLevel`·`priceRange` 채움률 | [billing-overview](https://developers.google.com/maps/billing-and-pricing/billing-overview) · [요금](https://developers.google.com/maps/billing-and-pricing/pricing) | Place Details **Enterprise $20/1,000** = 건당 30원 · **월 1,000건 무료** → 30곳 측정은 **0원** | **카드 등록**된 Cloud Billing 계정 | 시간 단위 |
| 4 | TripAdvisor Terra | [docs.terra.tripadvisor.com](https://docs.terra.tripadvisor.com/docs/overview) | **첫 1,000콜 무료** · 이후 종량제(단가 비공개) | 자율 가입 + 표시 의무 준수 | 위가 막힐 때 |
| 5 | KOPIS · 문체부 전시정보 | [KOPIS](https://www.data.go.kr/data/15097805/openapi.do) · [전시정보](https://www.data.go.kr/data/15105037/openapi.do) | 무료 | 활용신청 | 공연·전시로 범위가 좁다 |

★**1 번은 새 키가 필요 없다.** Base URL 이 `apis.data.go.kr/B553457/rgnCltrFcltExmnv1` 라서 **지금 있는 `ACOP_DATA_GO_KR_KEY` 를 그대로 쓴다.** 그 서비스에 활용신청이 안 돼 있을 뿐이다 — `[실측 2026-09-22]` 세 오퍼레이션 모두 `SERVICE_KEY_IS_NOT_REGISTERED_ERROR`(코드 30)가 떨어졌다.

오퍼레이션 10개 — `clifMsmv1`(박물관) · `clifArglv1`(미술관) · `clifClcnv1`(문예회관) · `clifLbrryv1`(공공도서관) · `clifNtnLbrryv1`(국립도서관) · `clifLtrm1`(문학관) · `clifLvclCntrv1`(생활문화센터) · `clifLclcv1`(지방문화원) · `clifClhsv1`(문화의집) · `clifLcclFndtv1`(지역문화재단).

신청이 끝났는지 확인하는 한 줄:

```
GET https://apis.data.go.kr/B553457/rgnCltrFcltExmnv1/clifMsmv1?serviceKey=<키>&numOfRows=1&pageNo=1&type=json
```

★**1·2·3 은 모두 사람이 가입·신청해야 한다.** AI 세션은 계정 생성과 카드 등록을 하지 않는다.

## 출처 링크 — 이 문서가 부르거나 읽은 곳

**공공데이터포털** — 검색은 `https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=<낱말>` 형식이다.

| 무엇 | 링크 | 비용 |
|---|---|---|
| 전국문화기반시설총람 조회서비스 (`관람료` 필드) | https://www.data.go.kr/data/15125097/openapi.do | 무료 · 자동승인 · 일 10,000건 |
| 문체부 12개 기관 전시정보 | https://www.data.go.kr/data/15105037/openapi.do | 무료 · 활용신청 |
| KOPIS 공연목록 (티켓 가격) | https://www.data.go.kr/data/15097805/openapi.do | 무료 · 활용신청 |
| 전국 세계 음식점 데이터 (9,502건, 가격 없음) | https://www.data.go.kr/data/15111398/fileData.do | 무료 |
| 무장애 여행 정보 | https://www.data.go.kr/data/15101897/openapi.do | 무료 · 개발단계 자동승인 · 일 1,000건 |
| 서울 지하철역 엘리베이터 위치정보 (파일) | https://www.data.go.kr/data/15098148/fileData.do | 무료 · 2022-01-11 기준 |
| 서울 지하철역 엘리베이터 위치정보 (API, LINK 방식) | https://www.data.go.kr/data/15098158/openapi.do | 무료 · 서울 열린데이터광장 키 필요 |
| 코레일 역별 엘리베이터 이동경로 | https://www.data.go.kr/data/15041689/openapi.do | 무료 · 활용신청 |
| 경기도 무슬림 친화 음식점 | https://www.data.go.kr/data/15099378/fileData.do | 무료 · 경기도만 |

**상용·해외 API**

| 무엇 | 링크 | 비용 |
|---|---|---|
| 구글 Places 데이터 필드 | https://developers.google.com/maps/documentation/places/web-service/data-fields | — |
| 구글 Maps Platform 요금 | https://developers.google.com/maps/billing-and-pricing/pricing | Place Details Enterprise $20/1,000 · E+Atmosphere $25/1,000 |
| 구글 결제 계정 안내 | https://developers.google.com/maps/billing-and-pricing/billing-overview | 카드 등록 필수 · SKU별 월 무료 한도 + $300 체험 |
| Viator 파트너 API 문서 | https://docs.viator.com/partner-api/affiliate/technical/ | 가입 비용 없음 |
| Viator 접근 등급 (Basic/Full/Full+Booking) | https://partnerresources.viator.com/travel-commerce/levels-of-access/ | Basic 사전 승인 없음 |
| TripAdvisor Terra API | https://docs.terra.tripadvisor.com/docs/overview | 첫 1,000콜 무료 · 이후 종량제 |
| Klook Open API | https://klook.gitbook.io/openapi | 공개 단가 없음 · 심사 |
| GetYourGuide Partner API | https://api.getyourguide.com/ | 공개 단가 없음 · 심사 |
| Amadeus Tours & Activities ❌ | https://developers.amadeus.com/self-service/category/destination-experiences/api-doc/tours-and-activities | 셀프서비스 티어 2026년 중반 폐지 |
| 카카오 로컬 | https://developers.kakao.com/docs/latest/ko/local/dev-guide | 무료(일 한도) |
| 네이버 지역 검색 | `https://developers.naver.com/docs/serviceapi/search/local/local.md` ★검사기가 `.md` 를 상대 경로로 읽어 링크로 걸지 않는다 | 무료 · 한 번에 최대 5건 |
| Overpass API (OSM) | https://overpass-api.de/ · 미러 https://overpass.private.coffee/ | 무료 · 키 없음 · 호출 제한 빡빡 |
| OSM 라이선스 (ODbL) | https://www.openstreetmap.org/copyright | 출처 표시 의무 |
| KOPIS 오픈API 안내 | https://kopis.or.kr/por/cs/openapi/openApiList.do?menuId=MNU_00074 | 무료 · 자체 키 |
| 문화빅데이터플랫폼 — 무슬림 친화 식당 데이터 | https://www.bigdata-culture.kr/bigdata/user/data_market/detail.do?id=38970490-3b91-11eb-af9a-4b03f0a582d6 | **유료 11,000,000원** (맛보기 0원) |
| HappyCow (공개 API 없음) | https://www.happycow.net/ | `/api` 404 |

**우리가 직접 부르는 엔드포인트**

```
TourAPI        https://apis.data.go.kr/B551011/KorService2
무장애          https://apis.data.go.kr/B551011/KorWithService2
카카오 로컬      https://dapi.kakao.com/v2/local/search/keyword.json
Overpass       https://overpass-api.de/api/interpreter
KCISA          https://api.kcisa.kr/openapi/...   ← 자체 키 필요(우리 키로 403)
```

## 관련

- [dietary-data-sources.md](dietary-data-sources.md) · [accessibility-data-sources.md](accessibility-data-sources.md)
- [../product/traveler-profile.md](../product/traveler-profile.md) — 무엇을 받고 무엇을 안 받는가
- `program/plan/A-COP_구현계획서_v11.md` §6-C(사전식 비교) · §11-A(가격·상한)
