import { expect, test, type Page } from "@playwright/test";
import { agreeTerms, noHorizontalScroll, submitPlan, useKorean } from "./helpers/app";

test.beforeEach(async ({ page }) => { await useKorean(page); });

const emailHead = (page: Page) => page.getByRole("button", { name: /복구용 이메일/ });
const termsHead = (page: Page) => page.getByRole("button", { name: /약관 동의/ });
const preferencesHead = (page: Page) => page.getByRole("button", { name: /여행 취향 알아보기/ });
const field = (page: Page) => page.getByRole("textbox", { name: "이메일" });
const ERROR = "이메일 형식을 확인해 주세요. 예: name@example.com";

/** Preferences open: skip all six questions, then add a plan and start its check. */
async function skipPreferencesAndRegister(page: Page) {
  await page.getByRole("button", { name: "시작하기" }).click();
  await expect(page.locator("#question-title-0")).toBeFocused();   // 「시작하기」의 넘김이 끝나야 다음 누름을 받는다
  const skip = page.getByRole("button", { name: "응답하지 않고 넘어가기" });
  // 설문은 6문항이다(독립 이동수단·내국인 여부 문항을 뺐다). ★카드가 넘어가는 동안의 누름은 화면이 일부러 무시하므로(두 번 넘김 방지),
  //   넘김이 끝나 다음 카드 제목으로 초점이 옮겨진 것을 보고 다음을 누른다 — 안 기다리면 부하가 있을 때 한 번이 사라진다
  //   (2026-09-28 실제로 그랬다). 답한 수는 누른 즉시 바뀌므로 기다리는 신호가 되지 못한다.
  for (let question = 0; question < 6; question += 1) {
    await skip.click();
    if (question < 5) await expect(page.locator(`#question-title-${question + 1}`)).toBeFocused();
  }
  await expect(page.getByRole("heading", { name: "여행 취향을 모두 알아봤어요.", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "여행 계획 등록하기" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await page.getByRole("button", { name: "예시 불러오기" }).click();
  await submitPlan(page);
}

test("이메일 카드를 한 번도 열지 않고 약관 → 취향 → 여행 등록까지 가고, 번호는 약관 01·취향 02 그대로이며 이메일 카드는 선택 표시만 있다", async ({ page }) => {
  await page.goto("/start");
  await expect(emailHead(page)).toHaveAttribute("aria-expanded", "false");
  await expect(emailHead(page)).toContainText("선택");
  await expect(emailHead(page)).toContainText("입력하지 않아도 시작할 수 있어요.");
  await expect(termsHead(page)).toContainText("01");
  await expect(preferencesHead(page)).toContainText("02");
  // Collapsed and never asking: no focus is taken.
  expect(await page.evaluate(() => document.activeElement?.id)).not.toBe("recovery-email");
  const tops = await Promise.all([emailHead(page), termsHead(page), preferencesHead(page)].map(async (head) => (await head.boundingBox())!.y));
  expect([...tops].sort((a, b) => a - b)).toEqual(tops);

  await termsHead(page).click();
  await agreeTerms(page);
  await skipPreferencesAndRegister(page);
});

test("카드를 열고 비우거나 공백만 넣은 채 계속하면 약관으로 가고, 끝까지 진행할 수 있다", async ({ page }) => {
  await page.goto("/start");
  await emailHead(page).click();
  await expect(field(page)).toHaveAttribute("type", "email");
  await expect(field(page)).toHaveAttribute("autocomplete", "email");
  await expect(field(page)).toHaveAttribute("inputmode", "email");
  await page.getByRole("button", { name: "계속" }).click();
  await expect(termsHead(page)).toHaveAttribute("aria-expanded", "true");
  await termsHead(page).click();

  await emailHead(page).click();
  await field(page).fill("   ");
  await page.getByRole("button", { name: "계속" }).click();
  await expect(page.getByText(ERROR)).toHaveCount(0);
  await expect(termsHead(page)).toHaveAttribute("aria-expanded", "true");
  await agreeTerms(page);
  await skipPreferencesAndRegister(page);
});

test("정상 이메일과 앞뒤 공백이 붙은 정상 이메일은 앞뒤만 지우고 받는다", async ({ page }) => {
  await page.goto("/start");
  await emailHead(page).click();
  await field(page).fill("  Name.Tag+1@example.co.kr  ");
  await page.getByRole("button", { name: "계속" }).click();
  await expect(termsHead(page)).toHaveAttribute("aria-expanded", "true");
  await termsHead(page).click();
  await expect(emailHead(page)).toContainText("입력했어요");
  await emailHead(page).click();
  await expect(field(page)).toHaveValue("Name.Tag+1@example.co.kr");
});

test("가운데 공백·잘못된 형식은 계속을 눌렀을 때만 오류를 보이고 다음 단계로 못 가며, 고치거나 지우면 진행된다", async ({ page }) => {
  await page.goto("/start");
  await emailHead(page).click();
  for (const wrong of ["name example@site.com", "name@", "name@example", "name.example.com"]) {
    await field(page).fill("");                                    // an error shown once stays until the value is fixed or cleared
    await field(page).fill(wrong);
    await expect(page.getByText(ERROR)).toHaveCount(0);            // never while typing
    await page.getByRole("button", { name: "계속" }).click();
    await expect(page.getByText(ERROR)).toBeVisible();
    await expect(page.getByText("입력하지 않으려면 내용을 지우고 계속할 수 있어요.")).toBeVisible();
    await expect(field(page)).toBeFocused();
    await expect(field(page)).toHaveValue(wrong);
    await expect(field(page)).toHaveAttribute("aria-invalid", "true");
    await expect(field(page)).toHaveAttribute("aria-describedby", /recovery-email-error/);
    await expect(termsHead(page)).toHaveAttribute("aria-expanded", "false");
  }
  // Correcting clears the error; so does clearing the field.
  await field(page).fill("name@example.com");
  await expect(page.getByText(ERROR)).toHaveCount(0);
  await field(page).fill("name@");
  await page.keyboard.press("Enter");
  await expect(page.getByText(ERROR)).toBeVisible();
  await field(page).fill("");
  await expect(page.getByText(ERROR)).toHaveCount(0);
  await expect(field(page)).toHaveAttribute("aria-invalid", "false");
  await page.keyboard.press("Enter");
  await expect(termsHead(page)).toHaveAttribute("aria-expanded", "true");
});

test("잘못된 값을 둔 채 카드를 접거나 약관·취향으로 가려 해도 막히고, 이메일 카드가 열려 입력란에 포커스가 간다", async ({ page }) => {
  await page.goto("/start");
  await emailHead(page).click();
  await field(page).fill("wrong@");
  await emailHead(page).click();                                   // folding the card is allowed…
  await expect(emailHead(page)).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByText(ERROR)).toHaveCount(0);
  await termsHead(page).click();                                   // …but not moving on
  await expect(emailHead(page)).toHaveAttribute("aria-expanded", "true");
  await expect(termsHead(page)).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByText(ERROR)).toBeVisible();
  await expect(field(page)).toBeFocused();
  await expect(field(page)).toHaveValue("wrong@");

  // With terms agreed, going on to the preferences is checked the same way.
  await field(page).fill("");
  await page.getByRole("button", { name: "계속" }).click();
  await agreeTerms(page);
  await page.keyboard.press("Escape");
  await emailHead(page).click();
  await field(page).fill("still wrong@example.com");
  await page.keyboard.press("Escape");
  await expect(emailHead(page)).toHaveAttribute("aria-expanded", "false");
  await preferencesHead(page).click();
  await expect(emailHead(page)).toHaveAttribute("aria-expanded", "true");
  await expect(preferencesHead(page)).toHaveAttribute("aria-expanded", "false");
  await expect(field(page)).toBeFocused();
  await field(page).fill("fixed@example.com");
  await emailHead(page).click();
  await preferencesHead(page).click();
  await expect(page.getByRole("heading", { name: "여행 취향 설문을 시작할게요", exact: true })).toBeVisible();
});

test("카드를 오가도 초안이 남고, 저장되지 않는다고 안내하며 마이페이지에도 등록된 것처럼 보이지 않는다", async ({ page }) => {
  await page.goto("/start");
  await emailHead(page).click();
  await expect(page.getByText("지금은 이 화면에서만 기억하고 서버에 저장하지 않아요. 인증 메일도 보내지 않아요.")).toBeVisible();
  await field(page).fill("draft@example.com");
  await page.getByRole("button", { name: "계속" }).click();
  await agreeTerms(page);
  await page.getByRole("button", { name: "시작하기" }).click();
  await expect(page.locator("#question-title-0")).toBeFocused();   // 「시작하기」의 넘김이 끝나야 다음 누름을 받는다
  await page.getByRole("button", { name: "응답하지 않고 넘어가기" }).click();
  await page.keyboard.press("Escape");
  await emailHead(page).click();
  await expect(field(page)).toHaveValue("draft@example.com");
  await expect(emailHead(page)).toContainText("서버에는 아직 저장하지 않아요");
  await expect(page.getByText(/인증 완료|복구 설정 완료/)).toHaveCount(0);

  // My page reads the saved profile, which has no email: the draft is not shown as registered.
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: /마이페이지/ }).click();
  await expect(page.getByText("등록된 이메일이 없습니다.", { exact: true })).toBeVisible();
  await page.goBack();
  // The onboarding state lives across the app, so the card is still as it was left: open.
  await expect(emailHead(page)).toHaveAttribute("aria-expanded", "true");
  await expect(field(page)).toHaveValue("draft@example.com");
});

test("키보드로 열고 입력해 Enter로 계속하며 Esc로 접으면 카드 머리로 포커스가 돌아온다", async ({ page }) => {
  await page.goto("/start");
  await emailHead(page).focus();
  await page.keyboard.press("Enter");
  await expect(emailHead(page)).toHaveAttribute("aria-expanded", "true");
  await expect(emailHead(page)).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(emailHead(page)).toHaveAttribute("aria-expanded", "false");
  await expect(emailHead(page)).toBeFocused();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await expect(field(page)).toBeFocused();
  await page.keyboard.type("keyboard@example.com");
  await page.keyboard.press("Enter");
  await expect(termsHead(page)).toHaveAttribute("aria-expanded", "true");
});

test("영어와 PC 기기 틀·375px·320px에서 세 카드와 펼친 이메일 카드의 계속 버튼이 잘리지 않고 가로로 넘치지 않는다", async ({ page }) => {
  for (const [width, height] of [[1280, 900], [375, 812], [320, 640]]) {
    await page.setViewportSize({ width, height });
    await page.goto("/start");
    await noHorizontalScroll(page);
    await preferencesHead(page).scrollIntoViewIfNeeded();
    await expect(preferencesHead(page)).toBeInViewport();
    await emailHead(page).click();
    await field(page).fill(`${"very.long.recovery.address".repeat(3)}@example-travel-domain.com`);
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
  const english = page.getByRole("button", { name: /Recovery email/ });
  await expect(english).toContainText("Optional");
  await english.click();
  await page.getByRole("textbox", { name: "Email" }).fill("wrong@");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByText("Please check the email format, e.g. name@example.com")).toBeVisible();
  await expect(page.getByText("To leave it out, clear the field and continue.")).toBeVisible();
  await expect(page.getByText("For now it is kept on this screen only and not saved to the server. No verification email is sent.")).toBeVisible();
});
