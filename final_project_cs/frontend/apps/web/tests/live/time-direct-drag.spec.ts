import { expect, test, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { openFinished, toast } from "./plan-check-kit";

/**
 * `[2026-10-05 사용자 선택 — 시간 조정 합친 안]` 시간(또는 그 옆 원)을 탭 없이 바로 잡고 끌면 시간이 바뀐다(위 = 일찍, 아래 = 늦게). 끄는 동안 폼은 안 열리고 미니맵만 뜬다.
 * 탭(안 움직임)은 전처럼 폼을 연다. mock 서버 시험이다 — 화면 반응만 본다.
 * 장면: 경복궁 09:00–10:30 → 이동 9분 → 올리브영 11:00–12:00 → 이동 16분 → 광장시장 12:30–13:30(여유 21분).
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const editsOf = async (server: ReturnType<typeof mockServer>) => (await server.received("POST", "/edits")).map((entry) => entry.body as { revision: number; edits: { field: string; value: unknown }[] });
const fieldsOf = (body: { edits: { field: string; value: unknown }[] }) => Object.fromEntries(body.edits.map((edit) => [edit.field, edit.value]));
const overlay = (page: Page) => page.locator('[data-overlay="time"]');
const timeButton = (page: Page, title: string) => page.getByRole("button", { name: new RegExp(`^${title} 시간 고치기`) });

test("시간을 탭 없이 바로 잡고 아래로 끌면 늦춰지고, 끄는 동안 폼은 안 열리고 미니맵이 뜨며, 놓으면 한 번에 저장된다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const handle = timeButton(page, "경복궁 관람");
  const box = (await handle.boundingBox())!;
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x, y + 30, { steps: 6 });                                                   // 30px = 15분
  await expect(overlay(page)).toBeVisible();
  await expect(overlay(page)).toContainText("09:00 → 09:15 (+15분)");
  await expect(page.getByRole("form", { name: "경복궁 관람 시간 고치기" })).toHaveCount(0);              // 폼이 열려 목록이 밀리지 않는다
  await expect(page.getByRole("button", { name: /^경복궁 관람 시간 고치기 · 지금 09:15/ })).toBeVisible();   // 목록의 시간이 손가락을 따라간다
  expect(await server.received("POST", "/edits")).toHaveLength(0);                                   // 끄는 동안은 아무것도 안 보낸다
  await page.mouse.up();
  await expect(toast(page, "1개 일정의 시간을 바꿨어요")).toBeVisible();
  const fields = fieldsOf((await editsOf(server))[0]);
  expect(fields["items[0].starts_at"]).toBe("09:15");
  await expect(page.getByRole("form", { name: "경복궁 관람 시간 고치기" })).toHaveCount(0);              // 끝나고 폼이 열리지도 않는다
  await expect(overlay(page)).toHaveCount(0);
});

test("시간 옆의 원을 잡고 끌어도 같다 (위로 끌면 일찍 — 앞 일정과 붙는 곳에서 한 번 멈춘다)", async ({ page, request }) => {
  await openFinished(page, request);
  const row = page.getByRole("button", { name: /^광장시장 시간 고치기/ }).locator("xpath=ancestor::li[1]");
  const grab = row.locator("span[data-grab]");
  await grab.scrollIntoViewIfNeeded();                                                              // 목록 안에서 보이는 자리로 (가려진 자리를 누르지 않게)
  const box = (await grab.boundingBox())!;
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x, y - 40, { steps: 6 });                                                   // 40px = 20분: 12:10 이 아니라 여유 끝 12:16 에서 멈춤
  await expect(overlay(page)).toContainText("앞 일정과 붙었어요");
  await expect(page.getByRole("button", { name: /^광장시장 시간 고치기 · 지금 12:16/ })).toBeVisible();
  await page.mouse.up();
});

test("움직이지 않고 누르면(탭) 전처럼 폼이 열린다 — 끌기가 탭을 막지 않는다", async ({ page, request }) => {
  await openFinished(page, request);
  await timeButton(page, "경복궁 관람").click();
  await expect(page.getByRole("form", { name: "경복궁 관람 시간 고치기" })).toBeVisible();
  await timeButton(page, "경복궁 관람").click();                                                    // 한 번 더 누르면 닫힌다
  await expect(page.getByRole("form", { name: "경복궁 관람 시간 고치기" })).toHaveCount(0);
});

test("폼이 열린 뒤에는 한 줄의 아이콘(되돌리기 · 취소 · 적용)이 있고, 바꾼 시간이 있으면 되돌리기 아이콘이 함께 보인다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await timeButton(page, "경복궁 관람").click();
  const form = page.getByRole("form", { name: "경복궁 관람 시간 고치기" });
  await expect(form.getByRole("button", { name: "처음 시간으로 되돌리기" })).toHaveCount(0);       // 아직 안 바꿨다
  await form.getByRole("button", { name: "+5분" }).click();
  await form.getByRole("button", { name: "적용" }).click();
  await expect.poll(async () => (await editsOf(server)).length).toBe(1);
  await timeButton(page, "경복궁 관람").click();
  const again = page.getByRole("form", { name: "경복궁 관람 시간 고치기" });
  await expect(again.getByRole("button", { name: "처음 시간으로 되돌리기" })).toBeVisible();
  const [cancel, apply, undo] = await Promise.all(["취소", "적용", "처음 시간으로 되돌리기"].map((name) => again.getByRole("button", { name }).boundingBox()));
  expect(Math.abs(cancel!.y - apply!.y)).toBeLessThan(2);                                          // 한 줄이다
  expect(Math.abs(undo!.y - apply!.y)).toBeLessThan(2);
});

test("고정한 일정의 시간은 잡아도 안 움직이고 이유만 말한다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: "경복궁 관람 꼭 넣을 일정으로 고정" }).click();
  await expect(page.getByRole("button", { name: "경복궁 관람 고정 풀기" })).toBeVisible();
  const before = (await server.received("POST", "/edits")).length;                                   // 잠금 자체도 서버로 간 수정이다
  const handle = timeButton(page, "경복궁 관람");
  const box = (await handle.boundingBox())!;
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x, y + 30, { steps: 5 });
  await page.mouse.up();
  await expect(overlay(page)).toHaveCount(0);
  expect((await server.received("POST", "/edits")).length).toBe(before);                             // 시간은 하나도 안 보냈다
});
