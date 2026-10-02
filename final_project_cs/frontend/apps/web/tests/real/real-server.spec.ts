import { expect, test, type Page } from "@playwright/test";
import { finishOnboarding, start } from "../live/helpers";

/**
 * A brand-new customer on the REAL server: first visit → survey → plan → read → confirm → trip screen → chat → map.
 * Nothing is faked. Each test opens a fresh browser context, so each one is a new user with a new key.
 */

// ★화면 안내와 같은 형식(「1일차 · 날짜」 머리줄 + 「시각 제목」 줄). 줄마다 「날짜 시각 제목」으로 쓰면 서버가 날짜를 못 읽는다(2026-09-28 실측).
const PLAN = "1일차 · 2026-10-05\n09:00 경복궁 관람\n12:00 광장시장 점심\n15:00 북촌한옥마을 산책";
const READING = 240_000;

// ★서버는 한 주소에서 한 시간에 새 키 20개까지만 발급한다(429 too_many_sessions). 시험마다 새 사용자를 만들면 금방 막히므로,
//   이 묶음은 순서대로 돌면서 첫 시험이 받은 키를 다음 시험이 이어 쓴다(같은 사용자의 두 번째 여행).
test.describe.configure({ mode: "serial" });
let sharedKey: string | null = null;

/** 사람 확인(Turnstile)이 켜져 있으면 확인 표가 올 때까지 기다린다 — 표 없이 누르면 화면이 보내지 않는다. 꺼져 있으면 바로 끝난다. */
async function waitForHumanCheck(page: Page) {
  await page.waitForFunction(() => {
    if (!document.getElementById("cf-turnstile-api")) return true;
    return Boolean((document.querySelector('input[name="cf-turnstile-response"]') as HTMLInputElement | null)?.value);
  }, null, { timeout: 60_000 });
}

async function uploadAndOpenReview(page: Page, text: string) {
  // ★설문 답은 화면 메모리에만 있다 — 주소를 새로 열면 사라진다. 이미 등록 화면이면(설문 뒤 단추로 왔으면) 다시 열지 않는다.
  if (!page.url().endsWith("/trips/new")) await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(text);
  await waitForHumanCheck(page);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  // 읽는 동안은 「계획을 읽고 있어요」, 끝나면 「여행 등록」 또는 일정 짜기 칸이 나온다.
  // 읽기가 끝날 때까지(등록 단추나 일정 짜기 단추가 나올 때까지) 기다린다 — 서버가 글·사진을 읽는 시간이다
  await expect(page.getByRole("button", { name: /여행 등록|이 조건으로 짜서 등록/ })).toBeVisible({ timeout: READING });
}

test("새 사용자: 설문을 마치고 계획을 올려 서버가 읽은 것을 확인해 등록하면 여행이 만들어지고, 채팅·지도까지 실서버로 동작한다", async ({ page }) => {
  await start(page, null);                               // 이 브라우저에는 키가 없다 = 첫 방문
  await finishOnboarding(page);
  await page.getByRole("button", { name: "여행 계획 등록하기" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await uploadAndOpenReview(page, PLAN);

  // 서버가 읽은 항목이 확인 화면에 나온다
  await expect(page.getByRole("heading", { name: "경복궁 관람", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "광장시장", exact: true })).toBeVisible();
  const third = page.locator("section").filter({ has: page.getByRole("heading", { name: "북촌한옥마을 산책", exact: true }) });
  await expect(third).toBeVisible();

  // 서버가 장소를 못 찾은 항목이 있다(실측: 「북촌한옥마을 산책」) — 사용자가 「장소 없음」으로 고치면 서버가 반영하고 등록할 수 있게 된다
  const register = page.getByRole("button", { name: "여행 등록" });
  if (await page.getByText("장소를 정하지 못했습니다").count()) {
    await third.getByRole("button", { name: "장소 없음" }).click();
    await expect(page.getByText("장소를 정하지 못했습니다")).toHaveCount(0);
  }
  await expect(register).toBeEnabled();

  // 새 사용자라서 키가 방금 발급됐다: 안내가 한 번 보이고 닫힌다
  const keyNotice = page.getByRole("status").filter({ hasText: "내 여행 열쇠를 따로 보관해 주세요" });
  await expect(keyNotice).toBeVisible();
  await keyNotice.getByRole("button", { name: "따로 보관했어요" }).click();
  await expect(keyNotice).toHaveCount(0);
  sharedKey = await page.evaluate(() => localStorage.getItem("tripilot.web.user-key.v1"));
  expect(sharedKey).toMatch(/^acop_u_/);

  // 설문을 마쳤으니 등록 확인 요청에 설문이 실려 가야 한다(서버가 저장하는지는 DB 로 따로 본다)
  const confirmSent = page.waitForRequest((request) => request.url().endsWith("/confirm") && request.method() === "POST");
  await page.getByRole("button", { name: "여행 등록" }).click();
  const confirmBody = (await confirmSent).postDataJSON() as { survey?: { version?: string } };
  console.log("REAL_CONFIRM_SURVEY", JSON.stringify(confirmBody.survey ?? null));
  expect(confirmBody.survey?.version).toBe("2026-09-24.v1");
  await expect(page).toHaveURL(/\/trips\/[0-9a-f-]{36}$/, { timeout: 120_000 });
  const tripId = page.url().split("/").pop();
  console.log("REAL_TRIP_ID", tripId);
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();

  // 여행 화면: 서버가 등록한 일정과 서버가 보낸 통지
  const schedule = page.locator("#trip-pane-schedule");
  await expect(schedule.getByText("경복궁").first()).toBeVisible();
  await expect(schedule.getByText("광장시장").first()).toBeVisible();
  const notices = page.locator("details").filter({ hasText: "받은 알림" });
  await expect(notices).toBeVisible();
  await notices.locator("summary").click();
  await expect(notices).toContainText("여행 일정이 준비되었습니다");
  await expect(page.getByRole("link", { name: "여행계획서 열기" })).toHaveAttribute("href", /\/plan\/[0-9a-f-]{36}\?t=/);

  // 내 여행: 같은 브라우저(같은 키)로 첫 화면에 돌아오면 방금 만든 여행이 카드에 있다
  await page.goto("/");
  await expect(page.getByRole("region", { name: "내 여행", exact: true }).getByRole("link").first()).toBeVisible();
  await page.goto(`/trips/${tripId}`);
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();

  // 채팅: 화면의 빠른 질문 4개에 서버가 이 여행의 사실로 답한다(규정 검색으로 새지 않는다)
  await page.getByRole("button", { name: "채팅", exact: true }).click();
  const chat = page.locator("#trip-pane-chat");
  const last = () => chat.locator("article[data-role=assistant]").last();
  const notRule = /규정에서 이 질문에 맞는 내용은 찾지 못했어요|담당자에게 넘겼어요/;

  // ★버튼을 누른 뒤 「마지막 답」을 바로 읽으면 앞 질문의 답을 읽게 된다(2026-09-28 실제로 그랬다). 새 답이 올 때까지 기다린 뒤 그 답을 검사한다.
  async function ask(button: string): Promise<string> {
    const before = await last().innerText().catch(() => "");
    await chat.getByRole("button", { name: button }).click();
    await expect.poll(async () => last().innerText().catch(() => ""), { timeout: 60_000, message: `「${button}」 답이 오지 않았다` }).not.toBe(before);
    const answer = (await last().innerText()).replace(/\n+/g, " / ");
    console.log(`REAL_ANSWER[${button}]`, answer);
    expect(answer).not.toMatch(notRule);
    return answer;
  }

  const day = await ask("하루 요약");
  expect(day).toContain("경복궁");
  expect(day).toContain("광장시장");
  expect(day).toContain("09:00");

  const booking = await ask("예약 표시");
  expect(booking).toContain("예약 기록 없음");
  expect(booking).toContain("광장시장");

  await page.getByRole("button", { name: "일정", exact: true }).click();
  await schedule.getByText("경복궁").first().click();
  await page.getByRole("button", { name: "채팅", exact: true }).click();
  const detail = await ask("선택 일정");
  expect(detail).toContain("경복궁 관람");
  expect(detail).toMatch(/주소|운영시간/);            // 주소·운영시간 줄이 있다 — 값은 관광공사 식별자가 있어야 채워진다(2026-09-28 실측: 식별자 없는 장소는 「모름」)
  expect(detail).toContain("다음 일정");

  const next = await ask("다음 일정");
  expect(next).toContain("광장시장");

  // 지도: 실제 구글 지도가 서버 좌표로 그려진다
  await page.getByRole("button", { name: /지도|방문 순서/, exact: false }).first().click();
  const map = page.locator("#trip-pane-map");
  await expect(map.locator(".gm-style")).toHaveCount(1, { timeout: 60_000 });
  expect(await map.locator("img").count()).toBeGreaterThan(0);
});

test("같은 사용자의 두 번째 여행: 일정을 못 읽는 글이면 일정 짜기 칸으로 서버가 일정을 짜 등록하고, 하루는 08:00 아침 식사로 시작한다", async ({ page }) => {
  await start(page, sharedKey);                          // 앞 시험이 받은 키가 있으면 이어 쓰고, 이 시험만 따로 돌리면 새 키를 받는다
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("서울에서 이틀, 조용하고 걷기 좋은 곳 위주로 일정을 짜 주세요");
  await waitForHumanCheck(page);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);

  // 「여행 첫날」(읽은 결과 쪽 칸)과 「첫날」(일정 짜기 칸)이 둘 다 있어 id 로 가린다
  const first = page.locator("#plan-start");
  await expect(first).toBeVisible({ timeout: READING });
  if (!(await first.inputValue())) await first.fill("2026-10-12");
  if ((await page.locator("#plan-days").inputValue()) === "0") await page.locator("#plan-days").selectOption("2");
  if ((await page.locator("#plan-party").inputValue()) === "0") await page.locator("#plan-party").selectOption("2");
  await page.getByRole("button", { name: /이 조건으로 짜서 등록/ }).click();
  await expect(page).toHaveURL(/\/trips\/[0-9a-f-]{36}$/, { timeout: 240_000 });
  console.log("REAL_PLAN_TRIP_ID", page.url().split("/").pop());

  // 서버가 짠 일정: 첫날 첫 항목이 08:00 아침 식사, 첫 활동은 그 뒤(09:00 이후)
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(page.locator("#trip-pane-schedule time").first()).toBeVisible({ timeout: 60_000 });
  const times = await page.locator("#trip-pane-schedule time").allInnerTexts();
  console.log("REAL_PLAN_FIRST_DAY_TIMES", times.join(" "));
  expect(times[0]).toBe("08:00");
  expect(times.length).toBeGreaterThanOrEqual(3);
});
