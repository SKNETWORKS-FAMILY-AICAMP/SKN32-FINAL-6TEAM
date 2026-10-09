import { expect, test } from "@playwright/test";
import { mockServer, noHorizontalScroll, start } from "./helpers";

// 실제 OAuth 요청 없이 공식 자산 표시·관리 UI·키보드 경계를 보는 mock 서버 시험입니다.
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("375px 화면의 네 소셜 버튼은 같은 크기와 정렬로 공식 아이콘·회사명을 보여 준다", async ({ page }) => {
  await page.route("**/v1/web/auth/providers", (route) => route.fulfill({ json: { providers: ["google", "kakao", "naver", "discord"].map((id) => ({ id })) } }));
  await page.setViewportSize({ width: 375, height: 812 });
  await start(page);
  await page.goto("/mypage");
  const group = page.getByRole("group", { name: "소셜 계정" });
  const companies = ["Google", "Kakao", "Naver", "Discord"];
  const boxes: { x: number; width: number; height: number }[] = [];
  for (const company of companies) {
    const button = group.getByRole("button", { name: `${company} 계정으로 계속` });
    await expect(button).toBeVisible();
    const box = (await button.boundingBox())!;
    boxes.push(box);
    if (company === "Google") await expect(button.locator("svg")).toBeVisible();
    else {
      const image = button.locator("img");
      await expect(image).toBeVisible();
      expect(await image.evaluate((node: HTMLImageElement) => node.complete && node.naturalWidth > 0)).toBe(true);
    }
  }
  expect(boxes.map((box) => box.height)).toEqual([48, 48, 48, 48]);
  expect(new Set(boxes.map((box) => box.x)).size).toBe(1);
  expect(new Set(boxes.map((box) => box.width)).size).toBe(1);
  await noHorizontalScroll(page);
  await group.scrollIntoViewIfNeeded();
  if (process.env.ACCOUNT_SHOTS) await page.screenshot({ path: `${process.env.ACCOUNT_SHOTS}/social-official-mobile.png` });
});

test("연결된 계정에도 공식 아이콘과 회사 이름이 남고 연결 해제 후 같은 버튼으로 돌아온다", async ({ page }) => {
  await start(page);
  await page.goto("/mypage");
  const group = page.getByRole("group", { name: "소셜 계정" });
  await group.getByRole("button", { name: "Kakao 계정으로 계속" }).click();
  await expect(page.getByRole("heading", { name: "카카오 계정으로 로그인했어요" })).toBeVisible();
  await page.getByRole("link", { name: "계속하기" }).click();
  const row = group.locator('li[data-provider="kakao"]');
  await expect(row).toContainText("Kakao");
  await expect(row.locator('[data-provider-icon="kakao"] img')).toBeVisible();
  await row.getByRole("button", { name: "풀기", exact: true }).click();
  await row.getByRole("button", { name: "연결 풀기", exact: true }).click();
  await expect(row.getByRole("button", { name: "Kakao 계정으로 계속" })).toBeVisible();
});

test("필수 약관 전문은 두 문서를 읽는 대화창이며 탭 초점·닫기·초점 복귀가 동작한다", async ({ page, request }) => {
  await mockServer(request).scenario({ consents: "on" });
  await page.setViewportSize({ width: 375, height: 812 });
  await start(page);
  await page.goto("/mypage");
  const trigger = page.getByRole("button", { name: "약관 전문 확인" });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "약관 전문", exact: true });
  const close = dialog.getByRole("button", { name: "약관 닫기" });
  await expect(close).toBeFocused();
  const choices = dialog.getByRole("navigation", { name: "필수 약관 선택" }).getByRole("button");
  await expect(choices).toHaveCount(2);
  await expect(choices.nth(0)).toHaveAttribute("aria-pressed", "true");
  await choices.nth(1).click();
  await expect(choices.nth(1)).toHaveAttribute("aria-pressed", "true");
  await expect(dialog.locator("article > h3").first()).toContainText("개인정보");
  await expect(dialog.getByRole("checkbox")).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: /철회|동의하기/ })).toHaveCount(0);
  await close.focus();
  for (let index = 0; index < 9; index += 1) {
    await page.keyboard.press("Tab");
    expect(await dialog.evaluate((node) => node.contains(document.activeElement))).toBe(true);
  }
  await close.focus();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.locator("article")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();
  for (let index = 0; index < 9; index += 1) {
    await page.keyboard.press("Shift+Tab");
    expect(await dialog.evaluate((node) => node.contains(document.activeElement))).toBe(true);
  }
  await noHorizontalScroll(page);
  if (process.env.ACCOUNT_SHOTS) await page.screenshot({ path: `${process.env.ACCOUNT_SHOTS}/required-full-text-mobile.png` });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test("관리 화면에서 선택 항목만 수정하고 기존 필수 동의 두 개는 보존한다", async ({ page, request }) => {
  const mock = mockServer(request);
  await mock.scenario({ consents: "on" });
  await start(page);
  await page.goto("/mypage");
  await page.getByRole("button", { name: "선택 약관 동의", exact: true }).click();
  const list = page.getByRole("list", { name: "선택 동의 항목" });
  await expect(list.locator(":scope > li")).toHaveCount(3);
  await expect(page.locator('[data-doc="service_terms"], [data-doc="privacy"]')).toHaveCount(0);
  const location = list.locator('[data-doc="location"]');
  await location.getByRole("button", { name: "동의하기", exact: true }).click();
  await expect(location.getByRole("status")).toContainText("동의를 기록했어요");
  const posts = await mock.received("POST", "/v1/web/consents");
  const items = posts.at(-1)!.body!.items as { code: string; agreed: boolean }[];
  for (const code of ["service_terms", "privacy", "location"]) expect(items.find((item) => item.code === code)?.agreed).toBe(true);
  await page.locator("#consents").scrollIntoViewIfNeeded();
  if (process.env.ACCOUNT_SHOTS) await page.screenshot({ path: `${process.env.ACCOUNT_SHOTS}/consent-optional-manager.png` });
});
