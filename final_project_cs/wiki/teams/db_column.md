# activity_total_data.csv 컬럼 정의

`[2026-10-12]` 최종 데이터셋 컬럼(30개). 채우는 코드는 `fill_tourapi_details.py` 다.

`[2026-10-11 사용자]` 옛 판(2026-10-01, [activity.md](activity.md#인원예약-확인용-컬럼--tourapi-상세-수집-구현-2026-10-01))의 `age_limit`(연령 제한, 26번)과 `experience_guide`(체험 안내, 27번)를 **둘 다 남긴다.** (처음에는 `experience_guide` 를 빼기로 했다가 같은 날 정정했다.)
`[2026-10-11]` CSV 헤더·`fill_tourapi_details.py`·`sigungucode` 를 읽던 코드 4곳을 이 문서에 맞췄다 → [리포트](../records/reports/2026-10-11_1554_Activity_CSV_컬럼정리_db_column반영_리포트.md).
`[2026-10-11 사용자]` 실내외 판정 `indoor_outdoor`·`indoor_outdoor_source`(28·29번)도 남긴다 — TourAPI 가 아니라 `fill_indoor_outdoor.py`(LLM)와 사람이 채운다. 이 스크립트(`fill_tourapi_details.py`)는 두 칸을 건드리지 않는다.
`[2026-10-12 사용자]` 30번 `field_sources` 추가 — TourAPI 가 아닌 곳(공식 홈페이지 등)에서 **사람이** 채운 칸의 출처를 적는다(아래 「TourAPI 밖에서 채운 값」).
결정: ① JSON 칸 하나(컬럼마다 `_source` 칸을 두지 않는다) ② 나중에 TourAPI 가 값을 주면 **TourAPI 값으로 바꾼다** ③ 허용 출처는 공식 홈페이지 · 지자체 · 공공기관 페이지.
지도 API(카카오 · 네이버 · 구글) 값과 웹 자동 수집 값은 넣지 않는다 — 약관 검토 → [리포트](../records/reports/2026-10-11_1554_Activity_CSV_컬럼정리_db_column반영_리포트.md).

## 원칙

- **타입마다 TourAPI 필드 이름이 달라도 같은 뜻이면 컬럼 하나로 묶는다.** 예: 요금은 문화시설 `usefee`, 행사 `usetimefestival`, 레포츠 `usefeeleports` 로 이름이 다르지만 모두 `fee` 에 담는다.
- 그 타입 응답에 해당 필드가 없으면 칸을 비운다(`–`). 다른 필드로 억지로 채우지 않는다.
- 같은 뜻 필드가 둘 이상이면 ` / ` 로 이어 붙인다(예: 행사 예약처 / 예약 링크).
- 값은 **원문 그대로** 옮기고 파싱하지 않는다.
- **빈 칸만 채운다.** 이미 값이 있는 칸은 새 응답으로 덮어쓰지 않는다. ★예외: `field_sources` 에 출처가 적힌 칸(사람이 TourAPI 밖에서 채운 값)은 TourAPI 응답에 값이 있으면 **TourAPI 값으로 바꾸고** 그 출처를 `field_sources` 에서 지운다(`[2026-10-12 사용자]`).
- 브랜드 행(`contentid` 가 숫자가 아님 — 올리브영·다이소 등)은 TourAPI 에 없어 호출하지 않는다. `lDongSignguCd` 만 같은 구 TourAPI 행의 코드로 채운다. 한 구에 코드가 여럿이면 한 코드가 95% 이상일 때만 쓴다(`[2026-10-11 사용자]` 다수 규칙 — 중구에 경계 장소 「서울로 7017」(용산구 코드 170) 한 곳이 끼어 명동 매장 32곳이 막혔다).

## 전체 컬럼

| # | 컬럼 | 뜻 | 출처 |
|---|---|---|---|
| 1 | `contentid` | 장소 ID (TourAPI 는 숫자, 브랜드는 접두어) | 목록 수집 |
| 2 | `contenttypeid` | 관광타입 (12 관광지 · 14 문화시설 · 15 행사 · 28 레포츠 · 38 쇼핑) | 목록 수집 |
| 3 | `title` | 장소명 | 목록 수집 |
| 4 | `addr1` | 주소 | 목록 수집 |
| 5 | `addr2` | 상세주소 | 목록 수집 |
| 6 | `lDongSignguCd` | 법정동 시군구 코드 (옛 `sigungucode` 자리. 코드 체계가 달라 옛 값은 옮기지 않았다) | `detailCommon2` / 브랜드 행은 같은 구 코드 |
| 7 | `mapx` | 경도 | 목록 수집 |
| 8 | `mapy` | 위도 | 목록 수집 |
| 9 | `lclsSystm1` | 대분류 | 목록 수집 |
| 10 | `lclsSystm2` | 중분류 | 목록 수집 |
| 11 | `lclsSystm3` | 소분류 | 목록 수집 |
| 12 | `overview` | 개요 | `detailCommon2` |
| 13 | `business_hours` | 영업시간 | `detailIntro2` (타입별) |
| 14 | `closed_days` | 휴무일 | `detailIntro2` (타입별) |
| 15 | `fee` | 요금 | `detailIntro2` (타입별) |
| 16 | `brand` | 브랜드명 | 수기 큐레이션 |
| 17 | `tel` | 연락처 | `detailCommon2`. 비면 `detailIntro2` 문의처(아래 표) |
| 18 | `homepage` | 홈페이지 | `detailCommon2` |
| 19 | `modifiedtime` | TourAPI 수정일시 | `detailCommon2` |
| 20 | `capacity` | 수용 인원 | `detailIntro2` (타입별) |
| 21 | `reservation_info` | 예약 안내 | `detailIntro2` (타입별) |
| 22 | `spendtime` | 소요 시간 | `detailIntro2` (타입별) |
| 23 | `eventstartdate` | 행사 시작일 | `detailIntro2` (행사만) |
| 24 | `eventenddate` | 행사 종료일 | `detailIntro2` (행사만) |
| 25 | `pet` | 반려동물 동반 | `detailIntro2` (타입별) |
| 26 | `age_limit` | 연령 제한(체험 가능 연령 포함) | `detailIntro2` (타입별) |
| 27 | `experience_guide` | 체험 안내(자유 문장 — 예약·인원이 섞일 수 있다) | `detailIntro2` (관광지만) |
| 28 | `indoor_outdoor` | 실내외 — `indoor` · `outdoor` · `mixed` · 빈칸(모름) | `fill_indoor_outdoor.py`(LLM) · 사람 |
| 29 | `indoor_outdoor_source` | 28번 값의 출처 — `llm:<모델>:<프롬프트>:<날짜>` 또는 `human:<날짜>`(사람이 고친 값은 LLM 이 덮어쓰지 않는다) | 위와 같음 |
| 30 | `field_sources` | TourAPI 밖에서 채운 칸의 출처(JSON). **비면 그 행의 값은 모두 이 표의 「출처」 그대로다** | 사람 |

`detailCommon2` 필드는 타입과 상관없이 이름이 같아 TourAPI 필드 이름 = 컬럼 이름이다.

## TourAPI 밖에서 채운 값 — `field_sources` (`[2026-10-12 사용자]`)

TourAPI 응답이 비었거나 그 타입에 필드가 없어 빈 칸을, 사람이 공식 페이지를 보고 채울 때 쓴다.

```json
{"closed_days": {"by": "human", "url": "https://www.example.go.kr/info", "checked": "2026-10-12"}}
{"tel": {"by": "claude", "url": "https://www.example.go.kr/info", "checked": "2026-10-12", "quote": "문의 02-000-0000"}}
```

| 키 | 뜻 | 규칙 |
|---|---|---|
| `by` | 누가 채웠나 | `human`(사람이 확인) · `claude`(`[2026-10-12 사용자]` Claude 가 검색으로 공식 페이지를 찾아 **그 페이지 본문을 열어** 확인 — 검색 요약문만 보고 적지 않는다). 사람이 검토하면 `human` 으로 바꾼다. 페이지를 대량으로 긁는 자동 수집은 쓰지 않는다 |
| `url` | 확인한 페이지 | `http(s)://`. 그 장소의 **공식 홈페이지 · 지자체 · 공공기관** 페이지만(언론 기사 · 블로그 · 지도 서비스는 안 된다). `claude` 는 **필수**. `human` 은 `[2026-10-12 사용자]` 선택 — 사용자가 직접 확인해 값만 준 경우 url 없이 `note` 에 「사용자 확인」을 적는다 |
| `checked` | 확인한 날 | `YYYY-MM-DD` |
| `note` | (선택) 메모 — url 없는 `human` 값은 「사용자 확인」 등 어떻게 확인했는지 |
| `quote` | (선택) 페이지에서 그 값의 근거가 된 문구 | `claude` 는 **반드시** 적는다 — 검토하는 사람이 페이지를 다시 열지 않고 대조할 수 있게 |

- **「해당 없음」**(`[2026-10-12 사용자]` — 거리 · 골목 · 상권 · 광장 · 공원 · 산 · 계곡처럼 휴무일 · 대표 전화 · 영업시간이 **원래 없는** 곳):
  칸은 **비워 둔 채** `{"by": "human", "na": true, "checked": "YYYY-MM-DD", "note": "왜 없나"}` 를 적는다(`url` 없음).
  빈 칸 = 「모른다」, 빈 칸 + `na` = 「원래 없다」. 칸에 「해당 없음」 글자를 넣지 않는다 — 다른 코드가 그 글자를 전화번호 · 영업시간 글로 읽는다.
  나중에 TourAPI 가 그 칸에 값을 주면 값이 들어가고 `na` 표시는 지워진다. DB 적재는 `na` 를 옮기지 않는다(빈 칸이라 옮길 값이 없다).
- **적어도 되는 컬럼**: `business_hours` · `closed_days` · `fee` · `tel` · `homepage` · `reservation_info` · `spendtime` · `capacity` · `pet` · `age_limit`.
  1~11번(식별자 · 좌표 · 분류)은 목록 수집이 정본이고, `overview` · `experience_guide` 는 남의 글이라(저작권 · 소개글 저장 안 함 결정) 넣지 않는다. `indoor_outdoor` 는 29번이 출처다.
- **사실만 짧게** 쓴다(예: 「매주 월요일 · 1월 1일」). 웹 문장을 그대로 붙이지 않는다.
- **빈 칸에만** 쓴다. TourAPI 값이 있는 칸은 사람이 고치지 않는다.
- 값을 넣으면 **같은 행 `field_sources` 에 그 컬럼의 출처를 반드시 함께** 적는다. `fill_tourapi_details.py` 가 돌 때 검사해서, 허용 밖 컬럼 · 빈 칸에 붙은 출처 · `url`/`checked` 형식 오류가 있으면 **CSV 를 쓰지 않고 멈춘다.**
- 나중에 TourAPI 응답에 그 칸 값이 있으면 TourAPI 값으로 바뀌고 출처가 지워진다(바뀐 수를 실행 결과에 센다).
- **DB 적재**(`scripts/enrich_place_catalog_from_csv.py`): DB 로 가는 사람 값은 영업시간 글 두 칸(`business_hours` · `closed_days` → `catalog_hours`)뿐이다.
  그 행은 `hours_read.source = "official_web"` 에 `hours_read.field_sources`(칸별 url · 확인한 날)를 함께 적는다 — 관광공사 원문(`activity_csv`)으로 적지 않는다.
  `field_sources` 형식이 틀리면 DB 에 쓰지 않고 멈춘다. 다른 사람 값(`tel` · `fee` 등)은 이 스크립트가 원래 DB 로 옮기지 않는 칸이다.
- **새벽 작업**(`catalog_hours.prefill`, 관광공사 목록 수정 시각이 바뀐 곳을 다시 읽는다): `official_web` 행은 **관광공사 응답이 채워진 칸만** 관광공사 값으로 바꾸고 그 칸의 출처를 지운다.
  두 칸 다 비어 오면 사람 값을 그대로 두고 목록 수정 시각만 맞춘다(다음 틱이 또 읽지 않게). 관광공사 원문 행은 전처럼 응답으로 덮어쓴다.
- **보이는 곳**: 일정 장소 정보(`place_info`)의 `source_note` 에 「운영시간 · 휴무일: 공식 페이지(확인한 날)」를 덧붙이고 `hours_evidence` 에 url 을 싣는다([rest-endpoints.md](../external/rest-endpoints.md)). 채팅의 「저장된 값」 줄도 같은 표시를 붙인다.

## 타입별 `detailIntro2` 필드 → 통일 컬럼

| 컬럼 | 12 관광지 | 14 문화시설 | 15 행사 | 28 레포츠 | 38 쇼핑 |
|---|---|---|---|---|---|
| `tel` (common 이 빌 때만) | infocenter | infocenterculture | sponsor1tel / sponsor2tel | infocenterleports | infocentershopping |
| `business_hours` | usetime | usetimeculture | playtime | usetimeleports | opentime |
| `closed_days` | restdate | restdateculture | – | restdateleports | restdateshopping |
| `fee` | – | usefee | usetimefestival | usefeeleports | – |
| `capacity` | accomcount | accomcountculture | – | accomcountleports | – |
| `reservation_info` | – | – | bookingplace / eventhomepage | reservation | – |
| `spendtime` | – | spendtime | spendtimefestival | – | – |
| `eventstartdate` | – | – | eventstartdate | – | – |
| `eventenddate` | – | – | eventenddate | – | – |
| `pet` | chkpet | chkpetculture | – | chkpetleports | chkpetshopping |
| `age_limit` | expagerange | – | agelimit | expagerangeleports | – |
| `experience_guide` | expguide | – | – | – | – |

## 캐시 — 지금 컬럼에 없는 정보

- 받은 응답은 `tourapi_details_cache.jsonl` 에 **응답 항목 전체**(위 표에 없는 필드 포함 — 예: `parking`, `discountinfo`, `useseason`, `openperiod`, `firstimage`, `zipcode`)가 한 줄씩 저장된다.
- 나중에 컬럼을 더하려면 매핑만 고치고 스크립트를 다시 돌리면 캐시에서 채운다. **다시 호출하지 않는다.**
- ★캐시는 `.gitignore` 에 있어 **이 PC 에만 있다.** 지우거나 PC 를 바꾸면 처음부터 다시 받아야 한다(11,302건, 하루 한도 기준 약 2주). 수집이 끝나면 따로 백업해 둔다.

## 필드 이름 확인

- `[2026-10-11]` 위 표의 모든 필드 이름을 실제 응답으로 확인했다(타입마다 1곳씩 시험 호출 10건). `pet`(`chkpet` · `chkpetculture` · `chkpetleports` · `chkpetshopping`) · `eventstartdate` · `eventenddate` 도 응답에 있다.
- `lDongSignguCd` 는 시군구 부분 3자리만 온다(예: 양천구 `470`). 시도 코드(`lDongRegnCd`, 서울 `11`)는 받지 않는다 — 데이터셋 전체가 서울이다.
- `homepage` 는 HTML 이 섞인 원문으로 온다(예: `공식 홈페이지 <a href="...">`). 원문 그대로 둔다.
