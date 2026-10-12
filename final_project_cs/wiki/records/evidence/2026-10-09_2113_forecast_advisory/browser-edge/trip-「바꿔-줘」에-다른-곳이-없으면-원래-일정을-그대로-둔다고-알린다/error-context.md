# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: trip.spec.ts >> 「바꿔 줘」에 다른 곳이 없으면 원래 일정을 그대로 둔다고 알린다
- Location: tests\live\trip.spec.ts:154:1

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: locator.click: Test timeout of 45000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: '바꿔 줘 — 다른 곳 보기' })

```

# Page snapshot

```yaml
- generic [ref=e1]:
  - alert [ref=e2]
  - generic [ref=e4]:
    - banner:
      - link "triPilot — 소개 화면으로 돌아가기" [ref=e5] [cursor=pointer]:
        - /url: /
        - generic [aria-hidden] [ref=e6]: t
        - text: triPilot
      - heading [level=1] [ref=e9]:
        - button "계획 이름 · 내 여행" [ref=e10] [cursor=pointer]:
          - generic [ref=e11]: 내 여행
        - button "여행계획서 열기 · 공유하기 펼치기" [ref=e12] [cursor=pointer]
      - generic [ref=e15]:
        - button "알림 센터 열기" [expanded] [ref=e16] [cursor=pointer]
        - button "메뉴" [ref=e20] [cursor=pointer]
    - main [ref=e22]:
      - generic [ref=e23]:
        - region "여행 지도" [ref=e26]:
          - generic "OpenStreetMap 지도" [ref=e27]:
            - generic [ref=e28]:
              - generic:
                - generic:
                  - button "1":
                    - generic "1. 아침 식당 · 2026-10-01 08:00–09:00": "1"
                  - button "2":
                    - generic "2. 경복궁 관람 · 2026-10-01 09:30–11:00": "2"
                  - button "3":
                    - generic "3. 점심 식당 · 2026-10-01 12:00–13:00": "3"
              - generic [ref=e32]:
                - link "Leaflet" [ref=e33] [cursor=pointer]:
                  - /url: https://leafletjs.com
                - text: "| ©"
                - link "OpenStreetMap" [ref=e38] [cursor=pointer]:
                  - /url: https://www.openstreetmap.org/copyright
                - text: contributors ·
                - link "지도 오류 신고" [ref=e39] [cursor=pointer]:
                  - /url: https://www.openstreetmap.org/fixthemap
          - group "지도 단추" [ref=e40]:
            - button "지도 단추 펼치기" [ref=e41] [cursor=pointer]
            - img "거리 눈금 500m" [ref=e44]:
              - generic [aria-hidden] [ref=e46]: 500m
        - region "일정 목록" [ref=e47]:
          - button "목록 높이 바꾸기" [ref=e48]
          - generic [ref=e50]:
            - tablist "일차 고르기" [ref=e51]:
              - tab "전체" [ref=e52] [cursor=pointer]
              - tab "1일차 10.01 목" [selected] [ref=e53] [cursor=pointer]:
                - text: 1일차
                - generic [ref=e54]: 10.01 목
              - tab "2일차 10.02 금" [ref=e55] [cursor=pointer]:
                - text: 2일차
                - generic [ref=e56]: 10.02 금
            - tablist "일정과 채팅 바꾸기" [ref=e58]:
              - tab "일정" [selected] [ref=e59] [cursor=pointer]
              - tab "채팅" [ref=e60] [cursor=pointer]
          - generic [ref=e62]:
            - tabpanel "일정" [ref=e63]:
              - generic [ref=e64]:
                - region [ref=e67]:
                  - heading [level=3] [ref=e68]:
                    - button "1일차 10.01 목" [pressed] [ref=e69] [cursor=pointer]:
                      - text: 1일차
                      - generic [ref=e70]: 10.01 목
                  - list [ref=e71]:
                    - listitem [ref=e72]:
                      - generic [ref=e73]:
                        - time [ref=e74]: 08:00
                        - generic [ref=e75]: 09:00
                      - article [ref=e78]:
                        - generic [ref=e79]:
                          - button "아침 식당 예약 정보 없음" [ref=e80] [cursor=pointer]:
                            - generic [ref=e81]:
                              - strong [ref=e82]: 아침 식당
                              - generic [ref=e83]: 예약 정보 없음
                          - button [aria-hidden] [ref=e85] [cursor=pointer]:
                            - generic [ref=e86]: +
                    - listitem [ref=e87]:
                      - paragraph [ref=e92]:
                        - text: 다음 일정으로 ·
                        - link "지도 앱에서 길찾기" [ref=e96] [cursor=pointer]:
                          - /url: https://www.google.com/maps/dir/?api=1&origin=a&destination=b&travelmode=transit
                    - listitem [ref=e101]:
                      - generic [ref=e102]:
                        - time [ref=e103]: 09:30
                        - generic [ref=e104]: 11:00
                      - article [ref=e107]:
                        - generic [ref=e108]:
                          - button "경복궁 관람 예약 있음 고정한 일정" [ref=e109] [cursor=pointer]:
                            - generic [ref=e110]:
                              - strong [ref=e111]: 경복궁 관람
                              - generic [ref=e112]:
                                - generic [ref=e113]: 예약 있음
                                - generic [ref=e114]: 고정한 일정
                          - button [aria-hidden] [ref=e115] [cursor=pointer]:
                            - generic [ref=e116]: +
                    - listitem [ref=e117]:
                      - generic [ref=e118]:
                        - generic [ref=e119]: 11:10
                        - generic [ref=e120]: 출발
                      - button "이동 20분 여유 30분" [ref=e125] [cursor=pointer]:
                        - generic [ref=e129]: 이동 20분
                        - generic [ref=e130]: 여유 30분
                    - listitem [ref=e132]:
                      - generic [ref=e133]:
                        - time [ref=e134]: 12:00
                        - generic [ref=e135]: 13:00
                      - article [ref=e138]:
                        - generic [ref=e139]:
                          - button "점심 식당 예약 정보 없음" [ref=e140] [cursor=pointer]:
                            - generic [ref=e141]:
                              - strong [ref=e142]: 점심 식당
                              - generic [ref=e143]: 예약 정보 없음
                          - button [aria-hidden] [ref=e145] [cursor=pointer]:
                            - generic [ref=e146]: +
                - paragraph [ref=e147]:
                  - text: "예약 표시는 입력한 정보 기준입니다. · 장소 정보 출처 : ⓒ한국관광공사 ·"
                  - link "저작권 정책" [ref=e148] [cursor=pointer]:
                    - /url: https://api.visitkorea.or.kr/#/useServiceGuide/2
                - paragraph [ref=e149]: 옆으로 밀면 2일차 10.02 금 일정이 나와요
            - tabpanel "채팅" [ref=e153]:
              - log "여행 대화 이력" [ref=e154]:
                - generic [ref=e155]:
                  - strong [ref=e156]: 1일차 · 2026-10-01
                  - generic [ref=e157]: 선택한 일정이 없어요.
                - article [ref=e158]:
                  - paragraph [ref=e159]: triPilot
                  - paragraph [ref=e160]: 등록한 일정에서 궁금한 내용을 골라 주세요. 하루 요약, 선택한 장소와 다음 일정을 함께 살펴볼 수 있어요.
              - generic [ref=e161]:
                - button "하루 요약" [ref=e162] [cursor=pointer]
                - button "선택 일정" [disabled] [ref=e163]
                - button "다음 일정" [disabled] [ref=e164]
                - button "예약 표시" [ref=e165] [cursor=pointer]
              - paragraph [ref=e166]: 보낸 문장은 여행 상담으로 접수돼요. 일정을 바꾸면 여행계획서에 새 버전이 생기고, 예약이 걸린 일정은 바꾸기 전에 물어봐요.
      - button "채팅 입력 열기" [ref=e168] [cursor=pointer]
      - dialog [ref=e171]:
        - generic [ref=e172]:
          - button "알림 센터 닫기" [ref=e173] [cursor=pointer]
          - heading "알림" [active] [level=2] [ref=e176]
        - generic [ref=e178]:
          - region [ref=e179]:
            - heading "할 일" [level=3] [ref=e180]
            - paragraph [ref=e181]: 지금 처리할 일은 없어요.
          - tablist "알림 종류" [ref=e182]:
            - tab "살펴볼 점 1" [ref=e183] [cursor=pointer]
            - tab "받은 알림 2" [selected] [ref=e184] [cursor=pointer]
            - tab "변경 이력 1" [ref=e185] [cursor=pointer]
          - tabpanel "받은 알림 2" [ref=e186]:
            - list [ref=e187]:
              - listitem [ref=e188]:
                - generic [ref=e189]: 안내
                - time [ref=e190]: 2026-10-01 07:30
                - img "새 알림" [ref=e191]
                - paragraph [ref=e192]: 오늘 첫 일정은 08:00 아침 식당이에요.
              - listitem [ref=e193]:
                - generic [ref=e194]: 변경 알림
                - time [ref=e195]: 2026-10-01 07:00
                - img "새 알림" [ref=e196]
                - paragraph [ref=e197]: 여행 일정이 준비되었습니다 — 내 여행.
```

# Test source

```ts
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
  128 |   await expect(ask.getByRole("button", { name: "바꿔 줘 — 다른 곳 보기" })).toBeVisible();
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
> 159 |   await page.getByRole("button", { name: "바꿔 줘 — 다른 곳 보기" }).click();
      |                                                              ^ Error: locator.click: Test timeout of 45000ms exceeded.
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
  229 |   await expect(last()).toContainText("서버 답: 2026-10-01 예약 표시를 알려 주세요.");
  230 | 
  231 |   // 일정을 고른 뒤: 「선택 일정」(상세)·「다음 일정」
  232 |   await paneTab(page, "일정").click();
  233 |   await page.locator("#stop-button-i-b").click();
  234 |   await paneTab(page, "채팅").click();
  235 |   await chat.getByRole("button", { name: "선택 일정" }).click();
  236 |   await expect(last()).toContainText("서버 답: 2026-10-01 09:30 경복궁 관람 일정의 상세를 알려 주세요.");
  237 |   await chat.getByRole("button", { name: "다음 일정" }).click();
  238 |   await expect(last()).toContainText("서버 답: 2026-10-01 09:30 경복궁 관람 다음 일정을 알려 주세요.");
  239 | 
  240 |   const sent = (await server.received("POST", "/messages")).map((entry) => entry.body?.message);
  241 |   expect(sent).toEqual([
  242 |     "2026-10-01 하루 일정을 요약해 주세요.", "2026-10-01 예약 표시를 알려 주세요.",
  243 |     "2026-10-01 09:30 경복궁 관람 일정의 상세를 알려 주세요.", "2026-10-01 09:30 경복궁 관람 다음 일정을 알려 주세요.",
  244 |   ]);
  245 |   // 요청마다 다른 request_id — 서버가 「같은 요청」으로 착각하지 않는다
  246 |   const ids = (await server.received("POST", "/messages")).map((entry) => entry.body?.request_id);
  247 |   expect(new Set(ids).size).toBe(4);
  248 |   // ★서버가 대화를 기록하고 화면이 그 기록을 읽어도 답은 한 번씩만 보인다(기록 시각이 받은 시각보다 이르다) —
  249 |   //   2026-09-29 실서버에서 모든 답이 두 번 보였다. 새로고침 뒤에도 같다.
  250 |   const answers = async () => chat.locator("article[data-role=assistant] p:nth-child(2)").allInnerTexts();
  251 |   expect((await answers()).filter((text) => text.startsWith("서버 답:"))).toHaveLength(4);
  252 |   await page.reload();
  253 |   await paneTab(page, "채팅").click();
  254 |   await expect.poll(async () => (await answers()).filter((text) => text.startsWith("서버 답:")).length).toBe(4);
  255 | });
  256 | 
  257 | test("직접 쓴 질문도 보내고, 옛 서버처럼 answer 없이 escalated 만 오면 화면이 「담당자에게 넘겼어요」를 지어내지 않는다", async ({ page, request }) => {
  258 |   await mockServer(request).scenario({ chat: "escalated_bare" });
  259 |   await openTrip(page);
```