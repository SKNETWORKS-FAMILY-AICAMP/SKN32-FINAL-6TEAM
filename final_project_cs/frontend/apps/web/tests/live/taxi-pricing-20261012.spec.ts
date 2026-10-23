import { expect, test } from "@playwright/test";
import { openFinished } from "./plan-check-kit";
import { mockServer } from "./helpers";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

for (const width of [375, 1280]) {
  test(`호출 상품 저장·새로고침과 오류 시 기존값 보존 ${width}px (mock 서버 화면 반응)`, async ({ page, request }, testInfo) => {
    await page.setViewportSize({ width, height: 850 });
    let product = "kakao_general";
    let refuse = false;
    const edits: unknown[] = [];
    await page.route(/\/v1\/web\/trip-intakes\/[^/]+(?:\/edits)?(?:\?.*)?$/, async (route) => {
      if (route.request().method() === "POST" && route.request().url().includes("/edits")) {
        const body = route.request().postDataJSON();
        edits.push(body);
        if (refuse) {
          await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ error: { code: "stale_revision", message: "그 사이 일정이 바뀌었어요. 다시 골라 주세요." } }) });
          return;
        }
        product = body.edits[0].value.product;
      }
      const response = await route.fetch();
      const body = await response.json();
      if (body.review) body.review.taxi_pricing = { product, quotes: [] };
      await route.fulfill({ response, json: body });
    });
    await openFinished(page, request);
    const summary = page.locator("summary").filter({ hasText: "이 여행의 택시 호출 상품" });
    await summary.click();
    const select = page.getByRole("combobox", { name: "호출 상품", exact: true });
    await expect(select).toHaveValue("kakao_general");
    await select.selectOption("capsi_immediate");
    // 저장 전 현재값을 새 상품으로 표시하지 않습니다.
    await expect(summary).toContainText("일반호출");
    await page.getByRole("button", { name: "저장하고 요금 다시 계산", exact: true }).click();
    await expect(summary).toContainText("캡시 블루파트너스");
    expect(edits[0]).toMatchObject({ revision: 1, edits: [{ field: "trip.taxi_pricing", value: { product: "capsi_immediate", quotes: [] } }] });
    await page.reload();
    await expect(summary).toContainText("캡시 블루파트너스");
    await summary.click();
    await expect(select).toHaveValue("capsi_immediate");
    refuse = true;
    await select.selectOption("km_blue_immediate");
    await page.getByRole("button", { name: "저장하고 요금 다시 계산", exact: true }).click();
    await expect(summary).toContainText("캡시 블루파트너스");
    await expect(page.getByRole("alert").filter({ hasText: "그 사이" }).first()).toBeVisible();
    await expect(select).toHaveValue("km_blue_immediate");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`taxi-product-${width}.png`), fullPage: true });
  });
}

for (const delayed of [false, true]) {
  test(`상품 변경 후 이전 요금 후보 폐기 ${delayed ? "늦게 도착한 응답" : "이미 읽은 응답"} (mock 서버 화면 반응)`, async ({ page, request }) => {
    let product = "kakao_general";
    let optionCalls = 0;
    let releaseOld: () => void = () => {};
    const oldGate = new Promise<void>((resolve) => { releaseOld = resolve; });
    await page.route(/\/v1\/web\/trip-intakes\/[^/]+(?:\/edits)?(?:\?.*)?$/, async (route) => {
      if (route.request().method() === "POST" && route.request().url().includes("/edits")) {
        product = route.request().postDataJSON().edits[0].value.product;
      }
      const response = await route.fetch();
      const body = await response.json();
      if (body.review) body.review.taxi_pricing = { product, quotes: [] };
      await route.fulfill({ response, json: body });
    });
    await page.route(/\/moves\/0-0~0-1\/options\?revision=\d+$/, async (route) => {
      const requestedProduct = product;
      optionCalls += 1;
      const response = await route.fetch();
      const body = await response.json();
      for (const option of body.options) {
        if (option.mode === "taxi") option.fare_krw = requestedProduct === "kakao_general" ? 9000 : 12000;
      }
      if (delayed && requestedProduct === "kakao_general") await oldGate;
      await route.fulfill({ response, json: body });
    });
    try {
      await openFinished(page, request, undefined, { moveOptions: "on" });
      const first = page.locator('li[data-type="move"][data-entry-id="0-0:0-1"]');
      await first.getByRole("button", { name: /지하철 3호선.*9분/ }).click();
      const box = first.getByRole("button", { name: /^이동 수단/ });
      const ways = first.getByRole("listbox", { name: "이동 수단 고르기" });
      await box.click();
      if (delayed) await expect.poll(() => optionCalls).toBe(1);
      else await expect(ways).toContainText("9,000원");
      const summary = page.locator("summary").filter({ hasText: "이 여행의 택시 호출 상품" });
      await summary.click();
      await page.getByRole("combobox", { name: "호출 상품", exact: true }).selectOption("capsi_immediate");
      await page.getByRole("button", { name: "저장하고 요금 다시 계산", exact: true }).click();
      await expect(summary).toContainText("캡시 블루파트너스");
      await expect(ways).toHaveCount(0);
      await box.click();
      await expect(ways).toContainText("12,000원");
      await expect(ways).not.toContainText("9,000원");
      expect(optionCalls).toBe(2);
      const oldResponse = delayed ? page.waitForResponse((r) => r.url().includes("/moves/0-0~0-1/options?revision=1")) : null;
      releaseOld();
      if (oldResponse) await oldResponse;
      await expect(ways).toContainText("12,000원");
      await expect(ways).not.toContainText("9,000원");
    } finally { releaseOld(); }
  });
}

