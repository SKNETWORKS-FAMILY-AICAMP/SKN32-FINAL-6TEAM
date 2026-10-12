import { expect, test } from "@playwright/test";
import { mockServer, paneTab, start, TRIP_ID, tripScreen } from "./helpers";

test("채팅 선택지는 화면 선택 대신 자기 일정 ID를 보내고 새로고침 뒤에도 복구된다", async ({ page, request }, testInfo) => {
  await mockServer(request).reset();
  await start(page);
  const sent: Record<string, unknown>[] = [];
  await page.route(url => url.pathname.endsWith(`/trips/${TRIP_ID}/chat`), route => route.fulfill({
    contentType: "application/json", body: JSON.stringify({ turns: [
      { role: "customer", text: "다른 일정 어디야?", case_id: "context-case" },
      { role: "assistant", text: "일정의 주소예요.", case_id: "context-case", reply: {
        choices: [{ label: "자세히 알려줘", message: "자세히 알려줘", item_id: "i-c" }] } },
    ] }),
  }));
  await page.route(url => url.pathname.endsWith(`/trips/${TRIP_ID}/messages`), async route => {
    sent.push(route.request().postDataJSON());
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ status: "answered", answer: "상세를 조회했어요." }) });
  });
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await paneTab(page, "일정").click();
  await page.locator("#stop-button-i-b").click();
  await paneTab(page, "채팅").click();
  await page.getByRole("button", { name: "자세히 알려줘", exact: true }).click();
  await expect.poll(() => sent.length).toBe(1);
  expect(sent[0]).toMatchObject({ item_id: "i-c", message: "자세히 알려줘" });
  // A received request is not a completed response. Wait for the pending
  // mutation to store its reply before deliberately removing the local copy.
  await expect(page.getByRole("log", { name: "여행 대화 이력" })).toContainText("상세를 조회했어요.");
  await expect(page.getByRole("log", { name: "여행 대화 이력" })).toHaveAttribute("aria-busy", "false");
  // A full reload gets the structured choices from the API, without relying on tab extras.
  await page.evaluate(() => sessionStorage.clear());
  await page.reload();
  await paneTab(page, "채팅").click();
  await expect(page.getByRole("button", { name: "자세히 알려줘", exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("restored-chat.png"), fullPage: true });
  await page.getByRole("button", { name: "자세히 알려줘", exact: true }).click();
  await expect.poll(() => sent.length).toBe(2);
  expect(sent[1]).toMatchObject({ item_id: "i-c" });
});
