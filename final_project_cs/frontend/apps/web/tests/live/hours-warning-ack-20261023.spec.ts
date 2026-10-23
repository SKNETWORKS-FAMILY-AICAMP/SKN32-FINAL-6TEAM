import { expect, test } from "@playwright/test";
import { mockServer, start } from "./helpers";

// Local mock-server check; the server marks only last-order uncertainty as acknowledgeable.
test("마지막 주문 주의를 읽고 계속해도 경고가 남고 같은 장소를 다시 고르지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ review: "on", board: "rich", readingPolls: 0 });
  await page.route(/\/v1\/web\/trip-intakes\/[^/?]+(\?.*)?$/, async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const response = await route.fetch();
    const body = await response.json();
    if (!body.review) return route.fulfill({ response });
    return route.fulfill({ response, json: { ...body, review: { ...body.review, moves: [], items: body.review.items.filter((item: { id: string }) => item.id === "0-1").map((item: object) => ({
      ...item, title: "566라멘", status: "review", place_state: "customer", place: { name: "566라멘", latitude: 37.57, longitude: 126.98, source: "customer", kind: "dining" },
      rows: [{ row: "place", result: "ok", text: "고객이 고른 장소" }, { row: "hours", result: "warn", text: "닫을 시각이 가까워 마지막 주문을 확인해 주세요", can_acknowledge: true }],
    })) } } });
  });
  await start(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/intakes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee");
  const question = page.locator("[data-stop-question]");
  await expect(question).toContainText("주문 가능 여부를 확인한 것은 아니에요");
  const writesBefore = (await server.log()).filter((entry) => entry.method === "POST" && /trip-intakes/.test(entry.path)).length;
  await question.getByRole("button", { name: /주의를 읽었어요 · 이 장소로 계속/ }).click();
  await expect(question).toHaveCount(0);
  const card = page.getByRole("article", { name: "566라멘" });
  await expect(card).toContainText("운영시간주의");
  await card.getByRole("button", { name: "566라멘", exact: true }).click();
  await expect(card).toContainText("닫을 시각이 가까워 마지막 주문을 확인해 주세요");
  expect((await server.log()).filter((entry) => entry.method === "POST" && /trip-intakes/.test(entry.path)).length).toBe(writesBefore);
  await page.screenshot({ path: "test-results/hours-warning-ack-20261023.png", fullPage: true });
  await page.reload();
  await expect(page.locator("[data-stop-question]")).toContainText("주의를 읽었어요 · 이 장소로 계속");
});
