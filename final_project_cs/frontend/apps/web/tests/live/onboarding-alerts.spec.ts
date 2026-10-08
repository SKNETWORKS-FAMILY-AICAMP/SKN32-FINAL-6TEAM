import { expect, test, type Page } from "@playwright/test";
import { agreeTerms, hydrated, mockServer, noHorizontalScroll, useKorean, checkPlan } from "./helpers";

/** Write a plan and press 「계획 확인하기」: the app goes to the plan-check screen of the mock server's intake. */
async function sendPlan(page: Page) {
  await hydrated(page);
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
}


test.beforeEach(async ({ page, request }) => { await mockServer(request).reset(); await useKorean(page); });

// `[2026-10-03 user decision]` The recovery email is gone; the first card of the start screen asks only for the Discord webhook.
const alertsHead = (page: Page) => page.getByRole("button", { name: /디스코드 알림/ });
const termsHead = (page: Page) => page.getByRole("button", { name: /약관 동의/ });
const preferencesHead = (page: Page) => page.getByRole("button", { name: /여행 취향 알아보기/ });
const webhook = (page: Page) => page.getByRole("textbox", { name: "디스코드 웹훅 URL" });
const WEBHOOK_ERROR = "디스코드 웹훅 주소를 확인해 주세요. 예: https://discord.com/api/webhooks/…";
const WEBHOOK = "https://discord.com/api/web" + "hooks/123456789012345678/AbC-def_123456789012345";   // the server's rule: a 20–120 char token

/**
 * 알림 카드가 다 펼쳐질 때까지(펼침 애니메이션 끝) 기다린다. ★펼친 카드는 **다음 프레임에** 카드 머리로 초점을 주고
 * Esc 를 듣기 시작한다(`onboarding.tsx`). 그 전에 누른 Tab 은 초점을 도로 빼앗기고 Esc 는 무시된다 — 열림 표시
 * (`aria-expanded`)만 보고 누르면 느린 CI 에서 실패했다(2026-09-28).
 */
async function alertsCardOpened(page: Page) {
  await expect(alertsHead(page)).toHaveAttribute("aria-expanded", "true");
  await page.locator("#card-0").evaluate((card) => Promise.all(card.getAnimations().map((animation) => animation.finished)));
}

/** Preferences open: skip all six questions, then add a plan and start its check. */
async function skipPreferencesAndRegister(page: Page) {
  await page.getByRole("button", { name: "시작하기" }).click();
  await expect(page.locator("#question-title-0")).toBeFocused();   // 「시작하기」의 넘김이 끝나야 다음 누름을 받는다
  const skip = page.getByRole("button", { name: "응답하지 않고 넘어가기" });
  // 설문은 6문항이다. ★카드가 넘어가는 동안의 누름은 화면이 일부러 무시하므로(두 번 넘김 방지), 넘김이 끝나 다음 카드 제목으로
  //   초점이 옮겨진 것을 보고 다음을 누른다 — 안 기다리면 부하가 있을 때 한 번이 사라진다(2026-09-28 실제로 그랬다).
  for (let question = 0; question < 6; question += 1) {
    await skip.click();
    if (question < 5) await expect(page.locator(`#question-title-${question + 1}`)).toBeFocused();
  }
  await expect(page.getByRole("heading", { name: "여행 취향 설정 완료", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "여행 계획 등록하기" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await sendPlan(page);
}

test("디스코드 알림 카드를 한 번도 열지 않고 약관 → 취향 → 여행 등록까지 가고, 번호는 약관 01·취향 02 그대로이며 알림 카드는 선택 표시만 있다", async ({ page, request }) => {
  await mockServer(request).scenario({ trips: "none" });   // [2026-10-06] 처음 동의하면 계획 화면을 거쳐 취향으로 돌아오므로, 그 사이 세션이 생긴다 - 그 세션에 여행은 아직 없다(첫 시험과 같다)
  await page.goto("/start");
  await expect(alertsHead(page)).toHaveAttribute("aria-expanded", "false");
  await expect(alertsHead(page)).toContainText("선택");
  await expect(alertsHead(page)).toContainText("여행 알림을 받을 디스코드 채널.");
  // no email input or label anywhere on the start screen (the terms boxes may MENTION an email address - the company's contact - so their text is left out)
  await expect(page.getByRole("textbox", { name: /이메일/ })).toHaveCount(0);
  expect(await page.locator("main").evaluate((main) => { const copy = main.cloneNode(true) as HTMLElement; copy.querySelectorAll('[role="region"]').forEach((box) => box.remove()); return (copy.textContent ?? "").includes("이메일"); })).toBe(false);
  await expect(termsHead(page)).toContainText("01");
  await expect(preferencesHead(page)).toContainText("02");
  // Collapsed and never asking: no focus is taken.
  expect(await page.evaluate(() => document.activeElement?.id)).not.toBe("discord-webhook");
  const tops = await Promise.all([alertsHead(page), termsHead(page), preferencesHead(page)].map(async (head) => (await head.boundingBox())!.y));
  expect([...tops].sort((a, b) => a - b)).toEqual(tops);

  await termsHead(page).click();
  await agreeTerms(page);
  await skipPreferencesAndRegister(page);
});

test("카드를 열고 비우거나 공백만 넣은 채 계속하면 약관으로 가고, 끝까지 진행할 수 있다", async ({ page, request }) => {
  await mockServer(request).scenario({ trips: "none" });   // [2026-10-06] 처음 동의하면 계획 화면을 거쳐 취향으로 돌아오므로, 그 사이 세션이 생긴다 - 그 세션에 여행은 아직 없다(첫 시험과 같다)
  await page.goto("/start");
  await alertsHead(page).click();
  await expect(webhook(page)).toHaveAttribute("type", "url");
  await expect(webhook(page)).toHaveAttribute("inputmode", "url");
  await expect(webhook(page)).toHaveAttribute("autocomplete", "off");
  await page.getByRole("button", { name: "계속" }).click();
  await expect(termsHead(page)).toHaveAttribute("aria-expanded", "true");
  await termsHead(page).click();

  await alertsHead(page).click();
  await webhook(page).fill("   ");
  await page.getByRole("button", { name: "계속" }).click();
  await expect(page.getByText(WEBHOOK_ERROR)).toHaveCount(0);
  await expect(termsHead(page)).toHaveAttribute("aria-expanded", "true");
  await agreeTerms(page);
  await skipPreferencesAndRegister(page);
});

test("디스코드 웹훅을 넣으면 앞뒤 공백을 지우고 받으며, 카드 머리는 입력했다고만 보인다", async ({ page }) => {
  await page.goto("/start");
  await alertsHead(page).click();
  await webhook(page).fill(`  ${WEBHOOK}  `);
  await page.getByRole("button", { name: "계속" }).click();
  await expect(termsHead(page)).toHaveAttribute("aria-expanded", "true");
  await termsHead(page).click();
  await expect(alertsHead(page)).toContainText("입력했어요 · 마이페이지에서 바꿀 수 있어요");
  await expect(alertsHead(page)).not.toContainText("discord.com");      // the URL carries a token: the head never shows it
  await alertsHead(page).click();
  await expect(webhook(page)).toHaveValue(WEBHOOK);
});

test("디스코드가 아닌 주소는 계속을 눌렀을 때만 오류를 보이고 막으며, 고치거나 지우면 진행된다", async ({ page }) => {
  await page.goto("/start");
  await alertsHead(page).click();
  for (const wrong of ["discord.com/api/web" + "hooks/1/x", "http://discord.com/api/web" + "hooks/1/x", "https://example.com/api/web" + "hooks/1/x", "https://discord.com/channels/1/2"]) {
    await webhook(page).fill("");                                  // an error shown once stays until the value is fixed or cleared
    await webhook(page).fill(wrong);
    await expect(page.getByText(WEBHOOK_ERROR)).toHaveCount(0);   // never while typing
    await page.getByRole("button", { name: "계속" }).click();
    await expect(page.getByText(WEBHOOK_ERROR)).toBeVisible();
    await expect(page.getByText("입력하지 않으려면 내용을 지우고 계속할 수 있어요.")).toBeVisible();
    await expect(webhook(page)).toBeFocused();
    await expect(webhook(page)).toHaveValue(wrong);
    await expect(webhook(page)).toHaveAttribute("aria-invalid", "true");
    await expect(webhook(page)).toHaveAttribute("aria-describedby", /discord-webhook-error/);
    await expect(termsHead(page)).toHaveAttribute("aria-expanded", "false");
  }
  // Correcting clears the error; so does clearing the field.
  await webhook(page).fill(WEBHOOK);
  await expect(page.getByText(WEBHOOK_ERROR)).toHaveCount(0);
  await webhook(page).fill("https://example.com/hook");
  await page.keyboard.press("Enter");
  await expect(page.getByText(WEBHOOK_ERROR)).toBeVisible();
  await webhook(page).fill("");
  await expect(page.getByText(WEBHOOK_ERROR)).toHaveCount(0);
  await expect(webhook(page)).toHaveAttribute("aria-invalid", "false");
  await page.keyboard.press("Enter");
  await expect(termsHead(page)).toHaveAttribute("aria-expanded", "true");
});

test("잘못된 값을 둔 채 카드를 접거나 약관·취향으로 가려 해도 막히고, 알림 카드가 열려 입력란에 포커스가 간다", async ({ page }) => {
  await page.goto("/start");
  await alertsHead(page).click();
  await webhook(page).fill("https://example.com/hook");
  await alertsHead(page).click();                                  // folding the card is allowed…
  await expect(alertsHead(page)).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByText(WEBHOOK_ERROR)).toHaveCount(0);
  await termsHead(page).click();                                   // …but not moving on
  await expect(alertsHead(page)).toHaveAttribute("aria-expanded", "true");
  await expect(termsHead(page)).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByText(WEBHOOK_ERROR)).toBeVisible();
  await expect(webhook(page)).toBeFocused();
  await expect(webhook(page)).toHaveValue("https://example.com/hook");

  // With terms agreed, going on to the preferences is checked the same way.
  await webhook(page).fill("");
  await page.getByRole("button", { name: "계속" }).click();
  await agreeTerms(page);
  await page.keyboard.press("Escape");
  await alertsHead(page).click();
  await webhook(page).fill("https://example.com/still-wrong");
  await page.keyboard.press("Escape");
  await expect(alertsHead(page)).toHaveAttribute("aria-expanded", "false");
  await preferencesHead(page).click();
  await expect(alertsHead(page)).toHaveAttribute("aria-expanded", "true");
  await expect(preferencesHead(page)).toHaveAttribute("aria-expanded", "false");
  await expect(webhook(page)).toBeFocused();
  await webhook(page).fill(WEBHOOK);
  await alertsHead(page).click();
  await preferencesHead(page).click();
  await expect(page.getByRole("heading", { name: "여행 취향 설문을 시작할게요", exact: true })).toBeVisible();
});

test("카드를 오가도 초안이 남는다 — 이 브라우저 저장소에는 어떤 모양으로도 쓰지 않는다", async ({ page }) => {
  await page.goto("/start");
  await alertsHead(page).click();
  await expect(page.getByText(/마이페이지에서 언제든 추가하거나 바꿀 수 있어요\. 첫 여행을 등록하면 서버에 저장돼요\./)).toBeVisible();
  await webhook(page).fill(WEBHOOK);
  await page.getByRole("button", { name: "계속" }).click();
  await agreeTerms(page, ["alert_channel"]);                         // ★입력한 주소는 알림 채널 동의를 해야 남는다(동의하지 않으면 버려진다 - consent.spec)
  await page.getByRole("button", { name: "시작하기" }).click();
  await expect(page.locator("#question-title-0")).toBeFocused();   // 「시작하기」의 넘김이 끝나야 다음 누름을 받는다
  await page.getByRole("button", { name: "응답하지 않고 넘어가기" }).click();
  await page.keyboard.press("Escape");
  await alertsHead(page).click();
  await expect(webhook(page)).toHaveValue(WEBHOOK);
  await expect(alertsHead(page)).toContainText("입력했어요");
  // ★A webhook is a secret: nothing of it reaches this browser's storage.
  expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain("AbC-def_123456789012345");
});

test("키보드로 열고 입력해 Enter로 계속하며 Esc로 접으면 카드 머리로 포커스가 돌아온다", async ({ page }) => {
  await page.goto("/start");
  await alertsHead(page).focus();
  await page.keyboard.press("Enter");
  await alertsCardOpened(page);
  await expect(alertsHead(page)).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(alertsHead(page)).toHaveAttribute("aria-expanded", "false");
  await expect(alertsHead(page)).toBeFocused();
  await page.keyboard.press("Enter");
  await alertsCardOpened(page);
  await page.keyboard.press("Tab");
  await expect(webhook(page)).toBeFocused();
  await page.keyboard.type(WEBHOOK);
  await page.keyboard.press("Enter");
  await expect(termsHead(page)).toHaveAttribute("aria-expanded", "true");
});

test("영어와 PC 기기 틀·375px·320px에서 세 카드와 펼친 알림 카드의 계속 버튼이 잘리지 않고 가로로 넘치지 않는다", async ({ page }) => {
  for (const [width, height] of [[1280, 900], [375, 812], [320, 640]]) {
    await page.setViewportSize({ width, height });
    await page.goto("/start");
    await noHorizontalScroll(page);
    await preferencesHead(page).scrollIntoViewIfNeeded();
    await expect(preferencesHead(page)).toBeInViewport();
    await alertsHead(page).click();
    await webhook(page).fill(`https://discord.com/api/web${"hooks"}/123456789012345678/${"AbC-def_1234567890".repeat(5)}`);
    const next = page.getByRole("button", { name: "계속" });
    await next.scrollIntoViewIfNeeded();
    await expect(next).toBeInViewport();
    const box = (await next.boundingBox())!;
    expect(box.height, `${width}x${height}`).toBeLessThan(60);
    await noHorizontalScroll(page);
    await next.click();
    await expect(termsHead(page)).toHaveAttribute("aria-expanded", "true");
  }

  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("button", { name: /LANGUAGE/ }).click();
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("button", { name: "English", exact: true }).click();
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  const english = page.getByRole("button", { name: /Discord alerts/ });
  await expect(english).toContainText("Optional");
  await english.click();
  await page.getByRole("textbox", { name: "Discord webhook URL" }).fill("https://example.com/hook");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByText("Please check the Discord webhook URL, e.g. https://discord.com/api/webhooks/…")).toBeVisible();
  await expect(page.getByText("To leave it out, clear the field and continue.")).toHaveCount(1);
  await expect(page.getByText(/You can add or change it on My page any time\. It is saved to the server when you register your first trip\./)).toBeVisible();
});
