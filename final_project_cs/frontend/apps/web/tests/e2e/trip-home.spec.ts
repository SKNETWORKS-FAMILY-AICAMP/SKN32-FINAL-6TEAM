import { expect, test, type Page } from "@playwright/test";

async function registerExampleTrip(page: Page) {
  await page.goto("/trips/new");
  await page.getByRole("button", { name: "예시 계획 불러오기" }).click();
  const source = await page.getByLabel("여행 계획 필수").inputValue();
  await page.getByRole("button", { name: "검증 하기" }).click();
  await page.getByRole("link", { name: "결과 확인" }).click();
  await page.getByLabel("전체 검증 결과와 일정 조정·안내 범위를 확인했어요.").check();
  await page.getByRole("button", { name: "여행 관리 시작", exact: true }).click();
  await expect(page.getByRole("heading", { name: "서울, 취향을 따라 걷는 이틀", exact: true })).toBeVisible();
  await expect(page.getByText("여행을 등록했어요 · 시작 대기", { exact: true })).toBeVisible();
  return { source, tripId: new URL(page.url()).pathname.split("/")[2] };
}

test("여행 홈은 날짜·일정·지도 선택을 연결하고 대화와 수정 원본을 보존한다", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { source, tripId } = await registerExampleTrip(page);
  const timeline = page.locator("#trip-pane-schedule");
  const map = page.locator("#trip-pane-map");
  const log = page.getByRole("log", { name: "여행 대화 이력" });

  const firstDay = page.getByRole("tab", { name: /1일차/ });
  await firstDay.focus();
  await firstDay.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /2일차/ })).toHaveAttribute("aria-selected", "true");
  await expect(timeline.getByRole("heading", { name: "2일차 일정" })).toBeVisible();
  await expect(timeline.getByRole("button", { name: /성수동 쇼핑/ })).toHaveCount(0);

  const museum = timeline.getByRole("button", { name: /국립중앙박물관/ });
  await museum.click();
  await expect(museum).toHaveAttribute("aria-expanded", "true");
  await expect(map.getByRole("button", { name: "2. 국립중앙박물관 지도에서 선택" })).toHaveAttribute("aria-pressed", "true");
  await expect(timeline.getByText("장소 상세", { exact: true })).toBeVisible();

  await map.getByRole("button", { name: "3. 이촌동 점심 식당 지도에서 선택" }).click();
  await expect(timeline.locator('article[data-selected="true"]')).toContainText("이촌동 점심 식당");
  await map.getByRole("button", { name: "일정 상세 보기", exact: true }).click();
  await expect(timeline.getByRole("button", { name: /이촌동 점심 식당/ })).toHaveAttribute("aria-expanded", "true");

  await map.getByRole("button", { name: "7. 호텔 복귀 지도에서 선택" }).click();
  await map.getByRole("button", { name: "일정 상세 보기", exact: true }).click();
  const lastStop = timeline.getByRole("button", { name: /호텔 복귀/ });
  await expect(lastStop).toHaveAttribute("aria-expanded", "true");
  await expect(lastStop).toBeFocused();
  await expect(lastStop).toBeInViewport({ ratio: 1 });
  await expect(timeline.getByRole("heading", { name: "장소 상세" })).toBeInViewport();

  await page.getByRole("button", { name: "하루 일정 요약", exact: true }).click();
  await expect(page.getByText("답변을 준비하고 있어요…", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "메시지 전송", exact: true })).toBeDisabled();
  await expect(log.locator('article[data-role="assistant"]').last()).toContainText("2026-09-16");
  await expect(log.locator('article[data-role="assistant"]').last()).not.toContainText("2026-09-15");
  await expect(page.getByRole("button", { name: "메시지 전송", exact: true })).toBeEnabled();

  const question = "국립중앙박물관 일정의 내용을 알려 주세요.";
  await page.getByLabel("여행 메시지", { exact: true }).fill(question);
  await page.getByRole("button", { name: "메시지 전송", exact: true }).click();
  await expect(page.getByLabel("여행 메시지", { exact: true })).toHaveValue("");
  await expect(log.locator('article[data-role="assistant"]').last()).toContainText("국립중앙박물관");
  await page.reload();
  await expect(page.getByRole("log").getByText(question, { exact: true })).toBeVisible();
  await expect(page.getByRole("log").locator('article[data-role="assistant"]').last()).toContainText("국립중앙박물관");

  await page.getByRole("link", { name: "일정 수정", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/new\\?from=${tripId}$`));
  await expect(page.getByLabel("여행 계획 필수")).toHaveValue(source);
  const edited = `${source}\n21:00 숙소에서 다음 날 준비`;
  await page.getByLabel("여행 계획 필수").fill(edited);
  await page.getByRole("link", { name: "← 내 여행", exact: true }).click();
  await page.getByRole("link", { name: "+ 첫 여행 등록하기" }).click();
  await expect(page.getByLabel("여행 계획 필수")).toHaveValue(edited);
});

test("375px와 320px에서 일정·지도·채팅이 전환되고 전송 실패를 재시도한다", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await registerExampleTrip(page);

  for (const width of [375, 320]) {
    await page.setViewportSize({ width, height: 812 });
    for (const [label, id] of [["일정", "schedule"], ["지도", "map"], ["채팅", "chat"]]) {
      await page.getByRole("tab", { name: label, exact: true }).click();
      await expect(page.locator(`#trip-pane-${id}`)).toBeVisible();
      for (const other of ["schedule", "map", "chat"].filter((item) => item !== id)) {
        await expect(page.locator(`#trip-pane-${other}`)).not.toBeVisible();
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    }
  }

  await page.getByRole("tab", { name: "지도", exact: true }).click();
  await page.getByRole("button", { name: "7. 롯데마트 서울역점 지도에서 선택" }).click();
  await page.getByRole("button", { name: "일정 상세 보기", exact: true }).click();
  await expect(page.getByRole("tab", { name: "일정", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#trip-pane-schedule").getByRole("button", { name: /롯데마트 서울역점/ })).toBeInViewport({ ratio: 1 });
  await expect(page.locator("#trip-pane-schedule").getByRole("heading", { name: "장소 상세" })).toBeInViewport();
  await page.getByRole("tab", { name: "채팅", exact: true }).click();

  await page.getByRole("button", { name: "메시지 전송", exact: true }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("메시지를 입력해 주세요.");
  await page.evaluate(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key: string, value: string) {
      if (key.startsWith("tripilot.web-mvp.trip:")) {
        Storage.prototype.setItem = original;
        throw new DOMException("Storage unavailable for this attempt", "QuotaExceededError");
      }
      return original.call(this, key, value);
    };
  });
  const question = "예약 일정 확인을 해 주세요.";
  await page.getByLabel("여행 메시지", { exact: true }).fill(question);
  await page.getByRole("button", { name: "메시지 전송", exact: true }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("메시지를 보내지 못했어요.");
  await expect(page.getByLabel("여행 메시지", { exact: true })).toHaveValue(question);
  await page.getByRole("button", { name: "다시 보내기", exact: true }).click();
  await expect(page.getByLabel("여행 메시지", { exact: true })).toHaveValue("");
  await expect(page.getByRole("log").locator('article[data-role="user"]')).toHaveCount(1);
  await expect(page.getByRole("log").locator('article[data-role="assistant"]').last()).toContainText("예약");
  await expect(page.locator("#main-content").getByRole("alert")).toHaveCount(0);
});

test("이 탭에 없는 여행 주소에서는 오류와 다시 등록할 경로를 제공한다", async ({ page }) => {
  await page.goto(`/trips/${crypto.randomUUID()}`);
  await expect(page.getByRole("heading", { name: "여행 정보를 불러오지 못했어요" })).toBeVisible();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("이 탭에 저장된 여행을 찾을 수 없어요.");
  await page.getByRole("button", { name: "다시 불러오기", exact: true }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("이 탭에 저장된 여행을 찾을 수 없어요.");
  await expect(page.getByRole("heading", { name: "여행 채팅", exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "여행 계획 등록", exact: true }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.getByRole("heading", { name: "준비한 여행 계획을 알려주세요" })).toBeVisible();
});
