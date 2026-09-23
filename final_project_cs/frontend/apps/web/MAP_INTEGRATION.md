# 지도 연동 · 백엔드 전달 계약

작성일: 2026-09-21. 웹 MVP 1차의 여행 홈에 적용한다. 지도 표시와 핀 선택은 프론트가 담당하고, 장소 식별·좌표 확정·방문 시간·이동 경로 계산은 백엔드/에이전트가 담당한다.

이 문서의 데이터 계약은 **현재 프론트가 받을 수 있는 형식과 백엔드 합의 제안**이다. 여행 조회 엔드포인트·접근 토큰·실제 에이전트 연동이 이미 구현되어 있다는 뜻은 아니다. 기존 전체 앱·웹 기획은 유지한다.

## 1. 지도 교체 방법

`TripMap`이 설정에 따라 `NaverMap` 또는 `GoogleMap`을 선택한다. 두 컴포넌트는 같은 장소 데이터와 선택 이벤트를 사용하므로 지도 교체 시 일정·채팅·백엔드 표시 계약을 바꾸지 않는다. 기본값 `demo`는 기존 시연 배치를 표시한다.

`.env.local`에 사용할 **한 가지** 설정을 입력한다. 환경변수 변경 후 개발 서버를 재시작하고, 배포에서는 다시 빌드한다.

### 네이버지도

```dotenv
NEXT_PUBLIC_MAP_PROVIDER=naver
NEXT_PUBLIC_NAVER_MAP_CLIENT_ID=발급받은_웹용_Client_ID
```

네이버 클라우드의 Maps Application에서 Dynamic Map을 선택하고 실제 접속 주소에 맞는 Web 서비스 URL을 등록한다. 개발 환경은 `http://127.0.0.1:3100`, 배포 환경은 실제 서비스 도메인을 등록 대상으로 확인한다. `localhost`로도 접속한다면 해당 주소도 확인한다. URL 형식과 등록 제한은 [현재 Application 가이드](https://guide.ncloud-docs.com/docs/application-maps-app-vpc)를 따른다. 어댑터는 웹 SDK의 `ncpKeyId` 파라미터에 Client ID를 전달한다. [공식 SDK 예제](https://github.com/navermaps/maps.js.ncp/blob/master/examples/map/1-map-simple.html)

### Google Maps

```dotenv
NEXT_PUBLIC_MAP_PROVIDER=google
NEXT_PUBLIC_GOOGLE_MAP_API_KEY=발급받은_웹용_API_KEY
NEXT_PUBLIC_GOOGLE_MAP_ID=발급받은_JavaScript_MAP_ID
```

Google Cloud 프로젝트에 결제 계정을 연결하고 Maps JavaScript API를 활성화한다. 이 구현은 Advanced Markers를 사용하므로 JavaScript용 Map ID도 필요하다. 개발 확인에 한해 `DEMO_MAP_ID`를 사용할 수 있으며 배포에는 프로젝트의 Map ID를 설정한다. [Advanced Markers 시작 안내](https://developers.google.com/maps/documentation/javascript/advanced-markers/start)

웹 키에 Websites 제한과 Maps JavaScript API 제한을 설정한다. 개발 referrer의 예는 `http://127.0.0.1:3100/*`이며 배포 도메인을 별도로 허용한다. [Google 키 제한 안내](https://developers.google.com/maps/api-security-best-practices)

### 기존 시연 지도

```dotenv
NEXT_PUBLIC_MAP_PROVIDER=demo
```

`NEXT_PUBLIC_DATA_MODE`와 `NEXT_PUBLIC_MAP_PROVIDER`는 별개다. 여행 데이터는 `demo`로 두고 지도만 `naver`/`google`로 확인할 수 있다. 선택한 제공자의 SDK만 필요할 때 불러오며, 실제 지도 로딩·인증 오류가 발생해도 시연 지도로 자동 전환하지 않는다. 키 누락·데이터 누락·로딩 실패를 화면에 안내한다.

`NEXT_PUBLIC_*`는 브라우저에 공개되는 값이다. 허용 사이트가 제한된 웹용 키/Client ID만 사용한다. Naver Client Secret, 서버용 지오코딩·경로 API 키, 여행 접근 비밀 토큰을 여기에 넣지 않는다. 실제 키를 문서나 소스에 커밋하지 않는다.

## 2. 백엔드에서 받아야 하는 최소 데이터

여행 조회 결과의 `stops`가 일정 목록과 지도의 공통 원본이다. 지도 전용으로 장소를 다시 추측하거나 채팅 답변에서 좌표를 추출하지 않는다. 실제 API 어댑터가 응답을 `Trip`/`TripStop`으로 변환하고, 지도는 선택한 날짜의 일정에서 핀 데이터를 만든다.

| 필드 | 지도 표시 기준 | 백엔드 전달 규칙 |
|---|---|---|
| `Trip.id` | 여행 구분 | 조회·채팅·갱신에서 동일한 여행 ID 사용 |
| `stops[].id` | 일정과 핀 선택 연결 | 여행 내 유일하고 갱신 후에도 안정적인 일정 ID. 장소명을 ID로 사용하지 않음 |
| `stops[].title` | 핀 이름·상세 표시 | 확정한 장소의 표시명. 같은 장소를 재방문해도 일정 ID는 각각 구분 |
| `stops[].date` | 일차별 필터 | `YYYY-MM-DD` 형태의 방문 날짜 |
| `stops[].time` | 방문 시간 표시 | `HH:mm` 형태의 방문 시작 시각 |
| `stops[].endTime` | 방문 종료 표시 | 선택 필드, `HH:mm`. 이동 소요시간을 여기에 넣지 않음 |
| `stops[].coordinates.lat` | 핀 위도 | WGS84 십진수, 유한 숫자, -90 이상 90 이하 |
| `stops[].coordinates.lng` | 핀 경도 | WGS84 십진수, 유한 숫자, -180 이상 180 이하 |
| `stops` 배열 순서 | 핀 방문 순서 번호 | 같은 날짜 안에서 실제 방문 순서대로 전달. 프론트가 일차별 1부터 번호를 붙임 |

현재 `TripStop.coordinates`는 선택 필드이며 `null`도 허용한다. 지도에 찍을 일정에는 유효한 좌표가 필요하다. 좌표가 없는 일정은 목록에는 남고 실제 지도 핀에서는 제외한다. 누락된 앞 일정 때문에 뒤 핀 번호를 당겨 쓰지 않아 목록의 방문 순서와 일치한다. 좌표를 임의 생성하거나 누락값을 `0, 0`으로 치환하지 않는다. 범위에 맞는 숫자라도 엉뚱한 장소인지는 백엔드가 확인해야 한다.

위도/경도 위치가 뒤바뀌지 않도록 배열 대신 이름 있는 `{ "lat": ..., "lng": ... }` 형식을 사용한다. 지도 제공자의 좌표 객체나 Place ID 자체를 공통 좌표 필드에 넣지 않는다. 현재 MVP 날짜·시간은 서울 현지 시간(`Asia/Seoul`)으로 해석한다. `Trip.timeZone` 필드는 아직 없으며 다른 시간대·자정 통과·절대 타임스탬프 지원은 별도 계약으로 확정한다.

다음은 **형식을 설명하기 위한 가상 일정**이다. 현재 `Trip` 응답 전체가 아닌 `id`와 `stops` 부분이며, `area`, `kind`, `booking`, `notes`는 기존 일정 상세에 필요한 필드다. 실제 엔드포인트 경로와 응답 래퍼는 미확정이다.

```json
{
  "id": "ebd8c74f-e27e-4d97-99bc-8b1e801de208",
  "stops": [
    {
      "id": "f3baa6ce-ed53-48e4-9f43-e7c4a4927b49",
      "date": "2026-10-10",
      "time": "10:00",
      "endTime": "11:00",
      "title": "좌표 확인용 장소 A",
      "area": "서울",
      "kind": "관광",
      "booking": "none",
      "notes": "형식 설명을 위한 가상 일정",
      "coordinates": { "lat": 37.5665, "lng": 126.978 }
    },
    {
      "id": "9d1c46dd-99d3-431f-b08c-729e1563bb1d",
      "date": "2026-10-10",
      "time": "12:00",
      "title": "좌표 확인용 장소 B",
      "area": "서울",
      "kind": "식사",
      "booking": "none",
      "notes": "형식 설명을 위한 가상 일정",
      "coordinates": { "lat": 37.57, "lng": 126.985 }
    }
  ]
}
```

## 3. 구현된 프론트의 책임

- `src/features/map/model.ts`: 제공자에 종속되지 않는 `Coordinates`, `MapPoint` 계약. `MapPoint`는 `id`, `title`, `date`, `time`, 선택적 `endTime`, 일차별 `order`, `coordinates`를 가진다.
- `TripMap`: 현재 날짜의 일정과 환경설정을 받아 지도 제공자를 선택하고 데이터·설정 상태를 안내한다.
- `NaverMap({ points, selectedId, onSelect, clientId })`: 네이버 지도와 번호 핀을 표시한다.
- `GoogleMap({ points, selectedId, onSelect, apiKey, mapId })`: Google 지도와 번호 핀을 표시한다.
- 공통 동작: 일차 전환에 따른 핀 변경, 일정 선택에 따른 핀 강조·지도 이동, 핀 선택에 따른 일정 선택, 장소명·방문 시간 표시. 장소명과 안내는 텍스트로 렌더링하며 API의 HTML을 그대로 삽입하지 않는다.

환경설정으로 선택하는 대신 다른 화면에 직접 넣을 때도 아래처럼 공통 props를 사용한다. `points`는 위 계약에서 만든 `MapPoint[]`이며 키는 각 컴포넌트의 웹용 인증 설정이다.

```tsx
import { NaverMap, GoogleMap } from "@/features/map";

// 필요한 컴포넌트 하나를 지도 영역에 배치한다.
<NaverMap points={points} selectedId={selectedId} onSelect={selectStop} clientId={naverClientId} />
<GoogleMap points={points} selectedId={selectedId} onSelect={selectStop} apiKey={googleApiKey} mapId={googleMapId} />
```

지도 영역의 부모에는 명시적인 높이를 준다(예: `height: 400px; display: flex`). 현재 여행 홈은 이 높이와 모바일 탭 전환 시 크기 재계산을 이미 처리한다. 웹 SDK 키를 실행 중 바꿀 경우에는 페이지를 새로고침한다.

일정 변경 응답은 일정과 지도가 같은 최신 `Trip.stops`를 사용하도록 여행 캐시를 갱신한다. 같은 일정의 시간이 바뀌면 ID를 유지하고, 일정 추가·삭제 시 해당 핀도 함께 바뀌어야 한다. 지도 SDK는 장소 검증·예약 변경·지오코딩·길찾기를 자동으로 수행하지 않는다.

## 4. 이동 수단·경로는 별도 계약

현재 구현 범위는 **실제 지도 바탕과 일정 핀**이다. `TripStop.movement`는 기존 선택적 안내 문자열이고, 구조화된 이동 구간·경로 선·실시간 교통은 이번 지도 어댑터의 입력이나 구현에 포함하지 않는다. 다음은 백엔드와 후속 합의할 권장 항목이다.

| 권장 항목 | 전달 목적 |
|---|---|
| `fromStopId`, `toStopId` | 어느 두 일정 사이의 이동인지 연결 |
| 이동 수단·경로 요약 | 도보/대중교통/자동차, 노선·환승 등의 설명 |
| `durationSeconds`, `distanceMeters` | 단위를 명확히 한 예상 소요시간·거리 |
| `departureAt`, `arrivalAt` | 오프셋이 포함된 출발·도착 시각. 방문 시각·소요시간과 구분 |
| 실제 경로 geometry와 좌표계/인코딩 | 지도에 이동 선을 그릴 때 필요. 두 핀의 직선을 실제 길찾기 결과로 표시하지 않음 |
| 조회 시각·출처·상태 | 경로의 신선도와 조회 실패 상태 구분 |
| 데이터 표시 가능 제공자·필수 출처 문구 | 사용할 지도에서 해당 경로/장소 데이터를 표시할 수 있는지 확인 |

이동 정보는 **일정 사이**에 한 번만 표시한다. 장소 상세에는 방문 시간·위치·예약·장소 안내를 둔다. 경로 계산과 검증은 백엔드/에이전트가 담당하고 프론트는 확정된 결과를 표시한다.

교체 가능한 컴포넌트가 있다고 해서 한 제공자에게 받은 장소·경로 데이터를 다른 지도에서 자유롭게 재사용할 권한까지 생기는 것은 아니다. 실제 데이터 출처의 사용 조건을 확인하고 각 SDK의 로고·저작권 표시를 유지한다. [Google Maps JavaScript API 표시 정책](https://developers.google.com/maps/documentation/javascript/policies)

## 5. 백엔드와 추가로 확정할 항목

1. 여행 조회·변경 API 경로, 로그인 없는 여행별 접근 권한·토큰 만료, 오류 응답.
2. 좌표 확정의 책임·출처·실패 처리. 프론트의 누락 안내는 데이터 파이프라인의 검증 완료 판정을 대신하지 않는다.
3. 일정 변경의 버전/이벤트 순서. `revision` 또는 동등한 순서 계약으로 늦게 온 응답이 최신 지도를 되돌리지 않게 한다. 현재 `Trip`에는 이 필드가 없다.
4. `timeZone`, 자정 통과, 시간 오프셋 표현. 현재 서울 MVP의 날짜·시각 문자열과 변환 규칙을 먼저 맞춘다.
5. 이동 구간 DTO와 geometry, 경로 조회 API·사용 조건. 현재 지도 핀 계약과 구분해 추가한다.

## 6. 키 연결 후 확인 방법

기본 예시 계획은 좌표를 자동 생성하지 않는다. 따라서 실제 지도를 선택해도 좌표가 없는 기존 여행에는 핀이 생기지 않으며 누락 안내가 나타난다. 실제 API 연결 전 수동 확인이 필요하면 **데모 모드에서만** 일정 줄에 다음과 같이 좌표를 명시할 수 있다.

```text
2026-10-10
10:00 좌표 확인용 장소 A [좌표: 37.5665, 126.9780]
12:00 좌표 확인용 장소 B [좌표: 37.5700, 126.9850]
```

이는 지도 UI 확인용 명시 입력이며 장소 검색·자연어 지오코딩 기능이 아니다. 실제 에이전트는 검증한 좌표를 API의 `coordinates`로 전달해야 한다.

키를 설정한 뒤 위 계획을 등록하고 검증 완료 → 여행 관리 시작 → 지도에서 다음을 확인한다: 바탕 지도와 두 핀, 일차 전환, 일정↔핀 선택, 이름·시간 일치, 모바일 탭 전환 후 지도 크기. 키 누락·잘못된 키·허용 도메인 불일치·네트워크 실패에서는 오류가 보이고 데모 지도로 바뀌지 않아야 한다.

코드·SDK 대역 테스트와 실제 제공자 인증 검증은 별개다. **실제 발급 키가 제공되지 않아 운영 키 인증·지도 타일·과금 프로젝트 설정을 포함한 실서비스 연결은 아직 확인하지 않았다.** 키 설정 후 네이버·Google 각각에서 위 확인을 수행한다.

## 7. 자동 검증 실행

`npm test`는 좌표 입력·범위·저장 보존·누락 처리와 지도 설정·SDK 로더의 공유 로딩/실패/시간 초과/인증 오류를 검사한다. 브라우저 지도 검사는 실제 공급자 인증 대신 SDK 계약 대역을 사용한다. 기본 데모 빌드에서는 지도 대역 테스트 3개를 건너뛴다.

PowerShell에서 다음 명령으로 공급자별 빌드와 브라우저 검사를 수행한다. 아래 값은 테스트 전용 가짜 키이며 실제 SDK 요청은 Playwright가 가로채어 대역으로 응답한다. 설치한 Chrome을 사용한다.

```powershell
$env:NEXT_PUBLIC_MAP_PROVIDER="naver"
$env:NEXT_PUBLIC_NAVER_MAP_CLIENT_ID="test-naver-key"
$env:MAP_TEST_PROVIDER="naver"
$env:PLAYWRIGHT_CHANNEL="chrome"
npm run build
npx playwright test tests/e2e/maps.spec.ts

$env:NEXT_PUBLIC_MAP_PROVIDER="google"
$env:NEXT_PUBLIC_GOOGLE_MAP_API_KEY="test-google-key"
$env:NEXT_PUBLIC_GOOGLE_MAP_ID="test-map-id"
$env:MAP_TEST_PROVIDER="google"
npm run build
npx playwright test tests/e2e/maps.spec.ts

# 테스트용 셸 환경을 지우고 .env.local 기준으로 다시 빌드한다.
Remove-Item Env:NEXT_PUBLIC_MAP_PROVIDER, Env:NEXT_PUBLIC_NAVER_MAP_CLIENT_ID, Env:NEXT_PUBLIC_GOOGLE_MAP_API_KEY, Env:NEXT_PUBLIC_GOOGLE_MAP_ID, Env:MAP_TEST_PROVIDER, Env:PLAYWRIGHT_CHANNEL -ErrorAction SilentlyContinue
npm run build
```

2026-09-21: 단위 검사 40/40(100%), 지도 브라우저 검사 네이버 3/3 및 Google 3/3(합계 6/6, 100%) 통과. 공급자별 프로덕션 빌드·린트·TypeScript 검사도 통과했다. 실제 공급자 계정 인증과 지도 타일 표시는 이 수치에 포함하지 않는다.
