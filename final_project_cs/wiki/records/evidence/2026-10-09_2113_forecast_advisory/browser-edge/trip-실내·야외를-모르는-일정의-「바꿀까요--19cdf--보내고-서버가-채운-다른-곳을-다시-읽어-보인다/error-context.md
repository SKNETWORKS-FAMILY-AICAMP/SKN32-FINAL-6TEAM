# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: trip.spec.ts >> 실내·야외를 모르는 일정의 「바꿀까요?」: 「바꿔 줘」가 key change 를 보내고, 서버가 채운 다른 곳을 다시 읽어 보인다
- Location: tests\live\trip.spec.ts:122:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('region', { name: /선택이 필요해요/ }).getByRole('button', { name: '바꿔 줘 — 다른 곳 보기' })
Expected: visible
Timeout: 12000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('region', { name: /선택이 필요해요/ }).getByRole('button', { name: '바꿔 줘 — 다른 곳 보기' }) with timeout 12000ms
  - waiting for getByRole('region', { name: /선택이 필요해요/ }).getByRole('button', { name: '바꿔 줘 — 다른 곳 보기' })

```

```yaml
- alert
- banner:
  - link "triPilot — 소개 화면으로 돌아가기":
    - /url: /
    - text: triPilot
  - heading "계획 이름 · 내 여행 여행계획서 열기 · 공유하기 펼치기" [level=1]:
    - button "계획 이름 · 내 여행": 내 여행
    - button "여행계획서 열기 · 공유하기 펼치기"
  - button "알림 센터 열기" [expanded]
  - button "메뉴"
- main:
  - region "여행 지도":
    - button "1"
    - button "2"
    - button "3"
    - link "Leaflet":
      - /url: https://leafletjs.com
    - text: ©
    - link "OpenStreetMap":
      - /url: https://www.openstreetmap.org/copyright
    - text: contributors ·
    - link "지도 오류 신고":
      - /url: https://www.openstreetmap.org/fixthemap
    - group "지도 단추":
      - button "지도 단추 펼치기"
      - img "거리 눈금 500m"
  - region "일정 목록":
    - button "목록 높이 바꾸기"
    - tablist "일차 고르기":
      - tab "전체"
      - tab "1일차 10.01 목" [selected]
      - tab "2일차 10.02 금"
    - tablist "일정과 채팅 바꾸기":
      - tab "일정" [selected]
      - tab "채팅"
    - tabpanel "일정":
      - region "1일차 10.01 목":
        - heading "1일차 10.01 목" [level=3]:
          - button "1일차 10.01 목" [pressed]
        - list:
          - listitem:
            - time: 08:00
            - text: 09:00
            - article "아침 식당":
              - button "아침 식당 예약 정보 없음":
                - strong: 아침 식당
                - text: 예약 정보 없음
          - listitem:
            - paragraph:
              - text: 다음 일정으로 ·
              - link "지도 앱에서 길찾기":
                - /url: https://www.google.com/maps/dir/?api=1&origin=a&destination=b&travelmode=transit
          - listitem:
            - time: 09:30
            - text: 11:00
            - article "경복궁 관람":
              - button "경복궁 관람 예약 있음 고정한 일정":
                - strong: 경복궁 관람
                - text: 예약 있음 고정한 일정
          - listitem:
            - text: 11:10 출발
            - button "이동 20분 여유 30분"
          - listitem:
            - time: 12:00
            - text: 13:00
            - article "점심 식당":
              - button "점심 식당 예약 정보 없음":
                - strong: 점심 식당
                - text: 예약 정보 없음
      - paragraph:
        - text: "예약 표시는 입력한 정보 기준입니다. · 장소 정보 출처 : ⓒ한국관광공사 ·"
        - link "저작권 정책":
          - /url: https://api.visitkorea.or.kr/#/useServiceGuide/2
      - paragraph: 옆으로 밀면 2일차 10.02 금 일정이 나와요
    - tabpanel "채팅":
      - log "여행 대화 이력":
        - strong: 1일차 · 2026-10-01
        - text: 선택한 일정이 없어요.
        - article:
          - paragraph: triPilot
          - paragraph: 등록한 일정에서 궁금한 내용을 골라 주세요. 하루 요약, 선택한 장소와 다음 일정을 함께 살펴볼 수 있어요.
      - button "하루 요약"
      - button "선택 일정" [disabled]
      - button "다음 일정" [disabled]
      - button "예약 표시"
      - paragraph: 보낸 문장은 여행 상담으로 접수돼요. 일정을 바꾸면 여행계획서에 새 버전이 생기고, 예약이 걸린 일정은 바꾸기 전에 물어봐요.
  - button "채팅 입력 열기"
  - dialog "알림":
    - button "알림 센터 닫기"
    - heading "알림" [level=2]
    - region "할 일":
      - heading "할 일" [level=3]
      - paragraph: 지금 처리할 일은 없어요.
    - tablist "알림 종류":
      - tab "살펴볼 점 1"
      - tab "받은 알림 2" [selected]
      - tab "변경 이력 1"
    - tabpanel "받은 알림 2":
      - list:
        - listitem:
          - text: 안내
          - time: 2026-10-01 07:30
          - img "새 알림"
          - paragraph: 오늘 첫 일정은 08:00 아침 식당이에요.
        - listitem:
          - text: 변경 알림
          - time: 2026-10-01 07:00
          - img "새 알림"
          - paragraph: 여행 일정이 준비되었습니다 — 내 여행.
```

# Test source

```ts
  28  |   await move.getByRole("button").click();
  29  |   await expect(move).toContainText("경복궁 관람 → 점심 식당");                                    // 서버의 문장 그대로
  30  |   await expect(move).toContainText("11:10 출발 → 11:30 도착");
  31  |   // 이동 항목이 없는 구간(아침 식당 → 경복궁)은 서버가 그린 선(버스 · 직선)과, 서버가 준 길찾기 링크
  32  |   const leg = schedule.locator('[data-entry-id="i-a>i-b"]');
  33  |   await expect(leg).toContainText("버스 · 640m");
  34  |   await leg.getByRole("button").click();
  35  |   await expect(leg).toContainText("길을 몰라 두 곳을 직선으로 이은 구간이에요.");
  36  |   await expect(schedule.getByRole("link", { name: "지도 앱에서 길찾기" })).toHaveCount(1);
  37  |   await expect(schedule.getByRole("link", { name: "지도 앱에서 길찾기" })).toHaveAttribute("href", "https://www.google.com/maps/dir/?api=1&origin=a&destination=b&travelmode=transit");
  38  | 
  39  |   // 고정한 일정 표시와 서버가 남겨 둔 다른 안
  40  |   await expect(page.locator("#stop-button-i-b").getByText("고정한 일정")).toBeVisible();
  41  |   await page.locator("#stop-button-i-b").click();
  42  |   await expect(page.locator("#stop-detail-i-b")).toContainText("다른 안");
  43  |   await expect(page.locator("#stop-detail-i-b")).toContainText("창덕궁");
  44  |   await expect(page.locator("#stop-detail-i-b")).not.toContainText("주소");           // 서버가 장소 사실을 안 보냈으면 줄 자체가 없다
  45  |   await expect(page.locator("#stop-detail-i-b").getByRole("button", { name: "이 일정 질문하기" })).toBeVisible();   // 상세가 열려 있는데
  46  |   await expect(page.locator("#stop-detail-i-b").getByRole("link", { name: "지도 앱으로 열기" })).toHaveCount(0);  // 지도 링크가 없으면 단추도 없다
  47  | 
  48  |   // 서버가 보낸 장소 사실(요식 원장) — 주소·전화·분류·영업시간·미쉐린·편의
  49  |   await page.locator("#stop-button-i-a").click();
  50  |   const detail = page.locator("#stop-detail-i-a");
  51  |   for (const text of ["서울특별시 종로구 율곡로1길 7", "02-000-0000", "한식", "월 08:00–21:00", "셀렉티드 (2026)", "카드 결제"]) await expect(detail).toContainText(text);
  52  |   await expect(detail).not.toContainText("michelin_selected");
  53  |   // 지도 앱으로 열기 — 서버가 준 구글 지도 링크를 새 창으로(서버가 링크를 안 준 일정에는 단추가 없다)
  54  |   await expect(detail.getByRole("link", { name: "지도 앱으로 열기" })).toHaveAttribute("href", "https://www.google.com/maps/search/?api=1&query=%EC%95%84%EC%B9%A8");
  55  |   await expect(detail.getByRole("link", { name: "지도 앱으로 열기" })).toHaveAttribute("target", "_blank");
  56  | 
  57  |   // 종 — 알림 센터: 할 일 · 탭 셋(서버가 찾은 것 · 보낸 것 · 바꾼 것)
  58  |   const notices = await openNotices(page);
  59  |   const tabs = notices.getByRole("tablist", { name: "알림 종류" }).getByRole("tab");
  60  |   await expect(tabs).toHaveText([/^살펴볼 점 \d+$/, "받은 알림 2", /^변경 이력 \d+$/]);
  61  |   const list = notices.getByRole("tabpanel");
  62  |   await expect(notices.getByRole("tab", { name: /받은 알림/ })).toHaveAttribute("aria-selected", "true");   // 안 읽은 알림이 있으면 받은 알림부터
  63  |   await expect(list).toContainText("오늘 첫 일정은 08:00 아침 식당이에요.");
  64  |   await expect(list.getByRole("img", { name: "새 알림" })).toHaveCount(2);
  65  |   await notices.getByRole("tab", { name: /살펴볼 점/ }).click();
  66  |   await expect(list).toContainText("하루가 빡빡해요");
  67  |   await expect(list).toContainText("일정을 줄이세요");
  68  |   await notices.getByRole("tab", { name: /변경 이력/ }).click();
  69  |   await expect(list).toContainText("처음 등록");
  70  |   // 여행계획서 — 제목을 펼친 줄(목업 C안 B)
  71  |   await notices.getByRole("button", { name: "알림 센터 닫기" }).click();
  72  |   const plan = (await openTitle(page)).getByRole("link", { name: "여행계획서 열기" });
  73  |   await expect(plan).toHaveAttribute("href", new RegExp(`/plan/${TRIP_ID}\\?t=`));
  74  |   await expect(plan).toHaveAttribute("target", "_blank");
  75  |   // 데모 잔재가 없다
  76  |   await expect(page.getByRole("link", { name: "일정 수정" })).toHaveCount(0);
  77  |   await expect(page.getByRole("link", { name: "검증 결과 다시 보기" })).toHaveCount(0);
  78  | });
  79  | 
  80  | test("서버가 경로선을 주지 않으면 이동 줄은 수단·거리를 지어내지 않는다 — 출발 시각 · 걸리는 시간 · 여유만, 이동 항목이 없는 구간은 길찾기 링크만", async ({ page }) => {
  81  |   await openTrip(page);                                                                          // 기본 장면: route-shapes 404
  82  |   const schedule = tripScreen(page);
  83  |   const move = schedule.locator('[data-entry-id="i-m"]');
  84  |   await expect(move).toContainText("이동 20분");
  85  |   await expect(move).toContainText("여유 30분");
  86  |   await expect(move).not.toContainText("도보");
  87  |   await expect(move).not.toContainText("km");
  88  |   await expect(schedule.locator('[data-entry-id="i-a>i-b"]')).toContainText("다음 일정으로");
  89  |   await expect(schedule.locator('[data-entry-id="i-a>i-b"]')).not.toContainText("버스");
  90  | });
  91  | 
  92  | test("경고와 알림이 없으면 탭은 0 과 「없어요」만 말하고 줄을 지어내지 않으며, 종에는 수가 없다", async ({ page, request }) => {
  93  |   await mockServer(request).scenario({ warnings: "none", notices: "none" });
  94  |   await openTrip(page);
  95  |   await expect(page.getByRole("button", { name: "알림 센터 열기", exact: true })).toBeVisible();     // 읽지 않은 알림이 없다
  96  |   const notices = await openNotices(page);
  97  |   await expect(notices.getByRole("tab", { name: /살펴볼 점/ })).toHaveText("살펴볼 점 0");
  98  |   await expect(notices.getByRole("tab", { name: /받은 알림/ })).toHaveText("받은 알림 0");
  99  |   await expect(notices.getByRole("tabpanel")).toHaveText("살펴볼 점이 없어요.");
  100 |   await expect(notices.getByRole("tabpanel").getByRole("listitem")).toHaveCount(0);
  101 |   await expect(notices.getByText("지금 처리할 일은 없어요.")).toBeVisible();
  102 | });
  103 | 
  104 | test("서버가 기다리는 선택이 있으면 「선택이 필요해요」가 뜨고, 고르면 그 안의 key 가 서버로 가고 칸이 사라진다", async ({ page, request }) => {
  105 |   const server = mockServer(request);
  106 |   await server.scenario({ proposals: "open" });
  107 |   await openTrip(page);
  108 |   await openNotices(page);
  109 |   const ask = page.getByRole("region", { name: /선택이 필요해요/ });
  110 |   await expect(ask).toBeVisible();
  111 |   await expect(ask).toContainText("점심 식당이 문을 닫았어요. 대체 식당을 골라 주세요.");   // 서버 통지 문장 그대로
  112 |   await expect(ask).toContainText("12:00 · 점심 식당");
  113 |   await ask.getByRole("button", { name: /대체 식당 A/ }).click();
  114 | 
  115 |   await expect.poll(async () => (await server.received("POST", "/choose")).length).toBe(1);
  116 |   const [choose] = await server.received("POST", "/choose");
  117 |   expect(choose.body).toEqual({ key: "o-1" });
  118 |   await expect(page.getByRole("region", { name: /선택이 필요해요/ })).toHaveCount(0);
  119 |   await expect(page.getByText("고르신 곳으로 일정을 바꿨어요.")).toBeVisible();          // 칸이 사라져도 결과는 말한다
  120 | });
  121 | 
  122 | test("실내·야외를 모르는 일정의 「바꿀까요?」: 「바꿔 줘」가 key change 를 보내고, 서버가 채운 다른 곳을 다시 읽어 보인다", async ({ page, request }) => {
  123 |   const server = mockServer(request);
  124 |   await server.scenario({ proposals: "consent" });
  125 |   await openTrip(page);
  126 |   await openNotices(page);
  127 |   const ask = page.getByRole("region", { name: /선택이 필요해요/ });
> 128 |   await expect(ask.getByRole("button", { name: "바꿔 줘 — 다른 곳 보기" })).toBeVisible();
      |                                                                     ^ Error: expect(locator).toBeVisible() failed
  129 |   await ask.getByRole("button", { name: "바꿔 줘 — 다른 곳 보기" }).click();
  130 |   await expect.poll(async () => (await server.received("POST", "/choose")).length).toBe(1);
  131 |   expect((await server.received("POST", "/choose"))[0].body).toEqual({ key: "change" });
  132 |   await expect(ask.getByRole("button", { name: /실내 박물관/ })).toBeVisible();              // 같은 제안을 다시 읽었다
  133 |   await expect(ask.getByRole("button", { name: "바꿔 줘 — 다른 곳 보기" })).toHaveCount(0);  // 선택지가 생기면 물음은 사라진다
  134 |   await expect(page.getByText("다른 곳을 찾았어요 — 위에서 골라 주세요.")).toBeVisible();
  135 | });
  136 | 
  137 | test("예보 주의 알림은 외부 발송을 건너뛰어도 변경 버튼을 보이고 누르면 대체안을 요청한다", async ({ page, request }) => {
  138 |   const server = mockServer(request);
  139 |   await server.scenario({ proposals: "forecast" });
  140 |   await openTrip(page);
  141 |   await openNotices(page);
  142 |   const ask = page.getByRole("region", { name: /선택이 필요해요/ });
  143 |   await expect(ask).toContainText("예보 주의사항이 있어요(강수확률 80% · 풍속 35km/h)");
  144 |   await expect(ask).toContainText("답이 없으면 원래 일정을 그대로 둡니다.");
  145 |   await ask.getByRole("button", { name: "예보에 맞게 일정 변경", exact: true }).click();
  146 |   await expect.poll(async () => (await server.received("POST", "/choose")).length).toBe(1);
  147 |   expect((await server.received("POST", "/choose"))[0].body).toEqual({ key: "change" });
  148 |   await expect(ask.getByRole("button", { name: /실내 박물관/ })).toBeVisible();
  149 |   await expect(ask.getByRole("button", { name: "예보에 맞게 일정 변경", exact: true })).toHaveCount(0);
  150 |   await ask.getByRole("button", { name: /실내 박물관/ }).click();
  151 |   await expect(page.getByText("고르신 곳으로 일정을 바꿨어요.")).toBeVisible();
  152 | });
  153 | 
  154 | test("「바꿔 줘」에 다른 곳이 없으면 원래 일정을 그대로 둔다고 알린다", async ({ page, request }) => {
  155 |   const server = mockServer(request);
  156 |   await server.scenario({ proposals: "consent", choose: "no_alternate" });
  157 |   await openTrip(page);
  158 |   await openNotices(page);
  159 |   await page.getByRole("button", { name: "바꿔 줘 — 다른 곳 보기" }).click();
  160 |   await expect(page.getByText("바꿀 수 있는 다른 곳을 찾지 못했어요 — 원래 일정을 그대로 둡니다.")).toBeVisible();
  161 | });
  162 | 
  163 | test("자동으로 바꾼 일정은 「되돌리기」로 서버가 준 값 그대로 되돌리고, 서버의 답을 보인다", async ({ page, request }) => {
  164 |   const server = mockServer(request);
  165 |   await server.scenario({ undo: "open" });
  166 |   await openTrip(page);
  167 |   await openNotices(page);
  168 |   const card = page.getByRole("region", { name: "자동으로 바꾼 일정" });
  169 |   await expect(card).toContainText("비 소식이 있어 09:30 경복궁 관람을 실내 박물관으로 바꿨어요.");
  170 |   await card.getByRole("button", { name: "되돌리기" }).click();
  171 |   await expect.poll(async () => (await server.received("POST", "/rollback")).length).toBe(1);
  172 |   expect((await server.received("POST", "/rollback"))[0].body).toEqual({ request_id: "rollback:v1->v0", base_version: 1, to_version: 0 });
  173 |   await expect(page.getByText("09:30 일정을 원래대로(경복궁 관람) 되돌렸어요.")).toBeVisible();
  174 |   await expect(page.getByRole("region", { name: "자동으로 바꾼 일정" })).toHaveCount(0);   // 되돌린 뒤엔 칸이 없다
  175 | });
  176 | 
  177 | test("그 사이 일정이 또 바뀌어 되돌리기가 거절되면(409) 아무것도 안 바뀌었다고 알린다", async ({ page, request }) => {
  178 |   const server = mockServer(request);
  179 |   await server.scenario({ undo: "stale" });
  180 |   await openTrip(page);
  181 |   await openNotices(page);
  182 |   await page.getByRole("region", { name: "자동으로 바꾼 일정" }).getByRole("button", { name: "되돌리기" }).click();
  183 |   await expect(page.getByText("그 사이 일정이 다시 바뀌어 되돌리지 않았어요. 지금 상태를 다시 불러왔어요.")).toBeVisible();
  184 | });
  185 | 
  186 | test("「지금 일정 그대로 두기」는 key 를 null 로 보낸다", async ({ page, request }) => {
  187 |   const server = mockServer(request);
  188 |   await server.scenario({ proposals: "open" });
  189 |   await openTrip(page);
  190 |   await openNotices(page);
  191 |   await page.getByRole("button", { name: "지금 일정 그대로 두기" }).click();
  192 |   await expect.poll(async () => (await server.received("POST", "/choose")).length).toBe(1);
  193 |   expect((await server.received("POST", "/choose"))[0].body).toEqual({ key: null });
  194 | });
  195 | 
  196 | test("이미 정해진 선택(409)은 「아무것도 바뀌지 않았다」고 알리고 서버 상태를 다시 읽는다", async ({ page, request }) => {
  197 |   const server = mockServer(request);
  198 |   await server.scenario({ proposals: "open", choose: "conflict" });
  199 |   await openTrip(page);
  200 |   await openNotices(page);
  201 |   await page.getByRole("button", { name: /대체 식당 B/ }).click();
  202 |   await expect(page.getByRole("alert").filter({ hasText: "이미 정해졌거나" })).toContainText("아무것도 바뀌지 않았고");
  203 |   // 알림 뒤에 화면이 서버를 다시 읽는다
  204 |   await expect.poll(async () => (await server.received("GET", "/proposals")).length).toBeGreaterThan(1);
  205 | });
  206 | 
  207 | test("지도는 서버 좌표가 있는 그날의 일정만 실제 지도(OpenStreetMap)에 핀으로 그린다", async ({ page }) => {
  208 |   await openTrip(page);
  209 |   const map = page.locator("main .leaflet-container");
  210 |   // 번호는 그날 일정의 순서이고, 핀의 title 에는 날짜와 시각이 붙는다(접근성 이름은 핀 안의 번호라 title 의 앞부분으로 찾는다). 이동 항목(i-m)은 일정이 아니라 번호를 차지하지 않는다.
  211 |   await expect(map.locator('.leaflet-marker-icon[title^="1. 아침 식당"]')).toBeVisible();
  212 |   await expect(map.locator('.leaflet-marker-icon[title^="2. 경복궁 관람"]')).toBeVisible();
  213 |   await expect(map.locator('.leaflet-marker-icon[title^="3. 점심 식당"]')).toBeVisible();
  214 |   await expect(map.locator('.leaflet-marker-icon[title*="둘째 날 박물관"]')).toHaveCount(0);       // 다음 날 일정은 그날 지도에 없다
  215 |   await expect(map.getByRole("link", { name: "OpenStreetMap" })).toBeVisible();            // 출처 표시는 늘 보인다
  216 |   await expect(map.getByText(/개념도|실제 위치·거리·이동 경로를 표시하지 않습니다/)).toHaveCount(0);
  217 | });
  218 | 
  219 | test("채팅: 빠른 질문 세 개와 일정 상세가 화면 문장 그대로 서버로 가고, 서버 답이 그대로 보인다", async ({ page, request }) => {
  220 |   const server = mockServer(request);
  221 |   await openTrip(page);
  222 |   await paneTab(page, "채팅").click();
  223 |   const chat = page.locator("#trip-pane-chat");
  224 |   const last = () => chat.locator("article[data-role=assistant]").last();
  225 | 
  226 |   await chat.getByRole("button", { name: "하루 요약" }).click();
  227 |   await expect(last()).toContainText("서버 답: 2026-10-01 하루 일정을 요약해 주세요.");
  228 |   await chat.getByRole("button", { name: "예약 표시" }).click();
```