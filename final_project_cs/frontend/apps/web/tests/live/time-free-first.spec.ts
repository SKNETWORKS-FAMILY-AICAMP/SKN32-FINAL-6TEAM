import { expect, test, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { openFinished, toast } from "./plan-check-kit";

/**
 * `[2026-10-05 사용자 지시]` 시간을 끌 때 「여유부터 줄이고 · 여유를 다 쓰면 한 번 멈춰 안내하고 · 더 끌면 다음 일정이 하나씩 밀린다」, 이동 출발 시각도 같은 방식, 끄는 동안 하루 전체 미니맵.
 * mock 서버 시험이다 — 화면 반응을 본다(서버가 시각을 어떻게 받아들이는지는 실서버 확인이 따로 본다).
 * 장면: 경복궁 09:00–10:30 → 이동 9분 → 올리브영 11:00–12:00 → 이동 16분 → 광장시장 12:30–13:30. 경복궁 뒤의 여유는 21분이라 시작은 09:21 까지(출발은 10:51 까지) 아무도 안 민다.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const editsOf = async (server: ReturnType<typeof mockServer>) => (await server.received("POST", "/edits")).map((entry) => entry.body as { revision: number; edits: { field: string; value: unknown }[] });
const fieldsOf = (body: { edits: { field: string; value: unknown }[] }) => Object.fromEntries(body.edits.map((edit) => [edit.field, edit.value]));
const overlay = (page: Page) => page.locator('[data-overlay="time"]');

async function openStart(page: Page, title: string) {
  await page.getByRole("button", { name: new RegExp(`^${title} 시간 고치기`) }).click();
  return page.getByRole("form", { name: `${title} 시간 고치기` });
}
async function openLeave(page: Page, title: string) {
  await page.getByRole("button", { name: new RegExp(`^${title}에서 나서는 시각 고치기`) }).click();
  return page.getByRole("form", { name: `${title}에서 나서는 시각 고치기` });
}

test("끌어서 늦추면 여유를 다 쓸 때 한 번 멈춰 알리고(알림은 하나), 더 끌어야 뒤 일정이 밀리며, 끄는 동안 하루 미니맵이 뜬다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const form = await openStart(page, "경복궁 관람");
  const grip = form.getByRole("button", { name: /끌어서 시작 시각 바꾸기/ });
  const box = (await grip.boundingBox())!;
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  await expect(overlay(page)).toHaveCount(0);                                                       // 끌지 않을 때는 없다
  await page.mouse.move(x, y);
  await page.mouse.down();

  await page.mouse.move(x, y + 30, { steps: 5 });                                                  // 30px = 15분: 여유 안(09:15)
  await expect(form.getByLabel("시작", { exact: true })).toHaveValue("09:15");
  await expect(overlay(page)).toBeVisible();
  await expect(overlay(page)).toContainText("경복궁 관람");
  await expect(overlay(page)).toContainText("09:00 → 09:15 (+15분)");
  await expect(overlay(page)).toContainText("다른 일정은 그대로예요");                                  // 여유부터 쓰니 아무도 안 밀린다
  await expect(overlay(page)).toContainText("여유 6분");
  await expect(overlay(page).getByText("여유를 다 썼어요")).toHaveCount(0);
  await expect(toast(page, "여유를 다 썼어요")).toHaveCount(0);

  await page.mouse.move(x, y + 60, { steps: 5 });                                                  // 60px = 30분: 여유 끝(09:21)을 9분 넘었다 → 거기서 멈춘다
  await expect(form.getByLabel("시작", { exact: true })).toHaveValue("09:21");
  await expect(overlay(page)).toContainText("여유를 다 썼어요 · 더 늦추면 뒤 일정이 밀려요");
  await expect(overlay(page)).toContainText("다른 일정은 그대로예요");
  await expect(toast(page, "여유를 다 썼어요")).toHaveCount(0);                                      // `[2026-10-07 사용자 지시]` 끄는 동안은 알림이 아니라 미니맵 안의 문구만(알림이 미니맵을 가렸다)

  await page.mouse.move(x, y + 96, { steps: 6 });                                                  // 96px = 48분 → 5분 칸으로 50분(09:50): 여유 끝을 29분 넘었고 멈춤은 10분 → 09:40, 뒤 일정이 밀린다
  await expect(form.getByLabel("시작", { exact: true })).toHaveValue("09:40");
  await expect(overlay(page)).toContainText("다른 일정 2곳이 움직여요");
  await expect(overlay(page)).toContainText("여유를 다 썼어요 · 뒤 일정이 밀리고 있어요");              // 멈춤은 풀렸지만 일정이 밀리는 동안은 문구가 계속 있다
  await expect(overlay(page).getByText("더 늦추면")).toHaveCount(0);                                  // 「더 늦추면 …」은 멈춰 있던 때의 문구
  await expect(toast(page, "여유를 다 썼어요")).toHaveCount(0);                                      // 알림은 쌓이지 않는다
  expect(await server.received("POST", "/edits")).toHaveLength(0);                                  // 끄는 동안은 아무것도 안 보낸다

  await page.mouse.up();
  await expect(overlay(page)).toHaveCount(0);
  await expect(toast(page, "3개 일정의 시간을 바꿨어요")).toBeVisible();
  const fields = fieldsOf((await editsOf(server))[0]);
  expect(fields["items[0].starts_at"]).toBe("09:40");
  expect(fields["items[1].starts_at"]).toBe("11:19");                                              // 09:40 + 90분 + 이동 9분
  expect(fields["items[2].starts_at"]).toBe("12:35");                                              // 11:19 + 60분 + 이동 16분
});

test("위로 끌어도 같다: 앞 일정과 붙는 곳에서 한 번 멈추고, 멈춤을 넘어야 앞 일정이 당겨진다", async ({ page, request }) => {
  await openFinished(page, request);
  const form = await openStart(page, "광장시장");                                                   // 올리브영(12:00 끝) + 이동 16분 = 12:16 이 여유의 앞 끝
  const grip = form.getByRole("button", { name: /끌어서 시작 시각 바꾸기/ });
  await grip.scrollIntoViewIfNeeded();                                                              // 끌개는 폼의 둘째 줄이라 아래 단추 줄에 가려질 수 있다
  const box = (await grip.boundingBox())!;
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x, y - 40, { steps: 5 });                                                  // 40px = 20분: 12:10 이 아니라 여유 끝 12:16 에서 멈춤
  await expect(form.getByLabel("시작", { exact: true })).toHaveValue("12:16");
  await expect(overlay(page)).toContainText("앞 일정과 붙었어요 · 더 당기면 앞 일정이 당겨져요");
  await page.mouse.move(x, y - 100, { steps: 6 });                                                 // 100px = 50분: 멈춤을 넘어 계속 → 앞 일정이 당겨진다
  await expect(overlay(page)).toContainText("다른 일정 2곳이 움직여요");                                 // 올리브영과 경복궁이 당겨진다
  await expect(overlay(page)).toContainText("앞 일정과 붙었어요 · 앞 일정이 당겨지고 있어요");             // 당겨지는 동안 문구가 계속 있다
  await expect(form.getByLabel("시작", { exact: true })).not.toHaveValue("12:16");
  await page.mouse.up();
});

test("−5분 · +5분 단추도 여유 끝에서 한 번 멈춰 알린 뒤 다음 단추부터 민다", async ({ page, request }) => {
  await openFinished(page, request);
  const form = await openStart(page, "경복궁 관람");
  for (let at = 0; at < 4; at += 1) await form.getByRole("button", { name: "+5분" }).click();       // 09:20
  await expect(form.getByLabel("시작", { exact: true })).toHaveValue("09:20");
  await expect(toast(page, "여유를 다 썼어요")).toHaveCount(0);
  await form.getByRole("button", { name: "+5분" }).click();                                          // 09:25 이 되려다 여유 끝 09:21 에서 멈춘다
  await expect(form.getByLabel("시작", { exact: true })).toHaveValue("09:21");
  await expect(toast(page, "여유를 다 썼어요")).toHaveCount(1);
  await form.getByRole("button", { name: "+5분" }).click();                                          // 다음 단추는 넘어간다(밀기 시작)
  await expect(form.getByLabel("시작", { exact: true })).toHaveValue("09:26");
  await expect(form.getByText(/함께 바뀌는 일정/)).toBeVisible();
});

test("이동의 「출발」 시각을 눌러 같은 방식으로 고친다: 늦게 나서면 여유가 줄고, 여유를 다 쓰면 멈춘 뒤 다음 일정이 밀린다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const form = await openLeave(page, "경복궁 관람");
  await expect(form.getByLabel("출발", { exact: true })).toHaveValue("10:30");
  for (let at = 0; at < 4; at += 1) await form.getByRole("button", { name: "+5분" }).click();       // 10:50
  await expect(form.getByLabel("출발", { exact: true })).toHaveValue("10:50");
  await expect(form.getByText(/함께 바뀌는 일정/)).toHaveCount(0);                                    // 여유(21분) 안: 아무도 안 밀린다
  await form.getByRole("button", { name: "+5분" }).click();                                          // 10:55 가 되려다 여유 끝 10:51 에서 멈춘다
  await expect(form.getByLabel("출발", { exact: true })).toHaveValue("10:51");
  await expect(toast(page, "여유를 다 썼어요 · 더 늦추면 다음 일정이 밀려요")).toHaveCount(1);
  await form.getByRole("button", { name: "+5분" }).click();                                          // 10:56: 올리브영이 밀린다
  await expect(form.getByLabel("출발", { exact: true })).toHaveValue("10:56");
  await expect(form.getByText(/함께 바뀌는 일정 1개 · 올리브영 \+5분/)).toBeVisible();
  await form.getByRole("button", { name: "적용" }).click();
  await expect.poll(async () => (await editsOf(server)).length).toBe(1);
  const fields = fieldsOf((await editsOf(server))[0]);
  expect(fields["items[0].ends_at"]).toBe("10:56");
  expect(fields["items[0].starts_at"]).toBeUndefined();                                            // 경복궁의 시작은 그대로
  expect(fields["items[1].starts_at"]).toBe("11:05");                                              // 10:56 + 이동 9분
});

test("고정한 일정에서 나서는 시각은 못 바꾸고 이유를 말한다", async ({ page, request }) => {
  await openFinished(page, request);
  await page.getByRole("button", { name: "경복궁 관람 꼭 넣을 일정으로 고정" }).click();
  await expect(page.getByRole("button", { name: "경복궁 관람 고정 풀기" })).toBeVisible();
  await page.getByRole("button", { name: /^경복궁 관람에서 나서는 시각 고치기/ }).click({ force: true });          // 못 쓰는 단추(aria-disabled)라 눌러서 이유를 듣는다
  await expect(toast(page, "고정한 일정에서 나서는 시각이라 바꿀 수 없어요")).toBeVisible();
});
