import { expect, test } from "@playwright/test";
import { noHorizontalScroll, registerExampleTrip, useKorean } from "./helpers/app";

test("소개에서 약관을 끝까지 읽고 동의한 뒤 취향 9문항을 마치면 등록 화면에 취향이 이어진다", async ({ page }) => {
  await useKorean(page);
  await page.goto("/");
  await expect(page.locator("#intro-title")).toHaveText("계획부터 여행까지,당신 곁의 triPilot.");
  await page.getByRole("button", { name: "다음 화면" }).first().click();
  await expect(page.locator("#how-title")).toBeInViewport();
  await page.getByRole("button", { name: "3. 일정 시작" }).click();
  await page.getByRole("button", { name: "내 일정 시작하기" }).click();
  await expect(page).toHaveURL(/\/start$/);

  await expect(page.getByRole("button", { name: /여행 취향 알아보기/ })).toBeDisabled();
  await page.getByRole("button", { name: /약관 동의/ }).click();
  const cardCheck = page.locator("#terms-check");
  await expect(cardCheck).toBeDisabled();
  await page.getByRole("button", { name: /전체 약관 읽기/ }).click();
  const reader = page.getByRole("dialog", { name: "서비스 이용 및 개인정보 안내" });
  await expect(reader).toBeVisible();
  await expect(reader.getByRole("checkbox")).toBeDisabled();
  await reader.getByRole("article").evaluate((element) => { element.scrollTop = element.scrollHeight; });
  await expect(reader.getByRole("status")).toHaveText("내용을 확인했어요. 동의 여부를 선택해 주세요.");
  await reader.getByText(/^\[필수\]/).click();
  await expect(reader).toHaveCount(0);
  await expect(cardCheck).toBeChecked();
  await expect(cardCheck).toBeFocused();
  await page.getByRole("button", { name: "동의하고 다음으로" }).click();

  const heading = (name: string) => page.getByRole("heading", { name, exact: true });
  await expect(heading("어떤 여행을 좋아하세요?")).toBeVisible();
  const next = page.getByRole("button", { name: "다음", exact: true });
  await expect(next).toBeDisabled();
  await page.getByRole("button", { name: "맛집 탐방" }).click();
  await expect(page.getByRole("progressbar", { name: "답변한 질문" })).toHaveAttribute("aria-valuenow", "1");
  await page.getByRole("button", { name: "맛집 탐방" }).press("ArrowRight");
  await expect(heading("누구와 함께 떠나나요?")).toBeVisible();

  await page.getByRole("button", { name: "가족" }).click();
  await expect(next).toBeEnabled();
  await page.getByRole("button", { name: "성인 인원 줄이기" }).click();
  await expect(page.getByText("동행하는 여행은 총인원을 2명 이상으로 설정해 주세요.")).toBeVisible();
  await expect(next).toBeDisabled();
  await page.getByRole("button", { name: "어린이 인원 늘리기" }).click();
  await next.click();

  const progress = page.getByRole("progressbar", { name: "답변한 질문" });
  const skip = page.getByRole("button", { name: "응답하지 않고 넘어가기" });
  await expect(heading("피하고 싶은 음식이 있나요?")).toBeVisible();
  await expect(page.getByText("선택", { exact: true })).toHaveCount(0);
  await expect(next).toBeDisabled();
  await skip.click();
  await expect(progress).toHaveAttribute("aria-valuenow", "3");
  for (const [question, choice] of [["어떻게 이동하고 싶나요?", "도보"], ["여행 예산은 얼마인가요?", "30–60만 원"]]) {
    await expect(heading(question)).toBeVisible();
    await page.getByRole("button", { name: choice, exact: true }).click();
    await next.click();
  }
  await expect(heading("한국 국적이신가요?")).toBeVisible();
  await page.getByRole("button", { name: "외국인", exact: true }).click();
  await skip.click();
  await expect(progress).toHaveAttribute("aria-valuenow", "6");
  await page.getByRole("button", { name: "이전", exact: true }).click();
  await expect(heading("한국 국적이신가요?")).toBeVisible();
  await expect(page.getByRole("button", { name: "외국인", exact: true })).toHaveAttribute("aria-pressed", "false");
  await expect(next).toBeDisabled();
  await skip.click();
  await expect(heading("가장 중요한 것은 무엇인가요?")).toBeVisible();
  await page.getByRole("button", { name: "활동", exact: true }).click();
  await next.click();
  await expect(heading("어떤 점을 더 중요하게 보나요?")).toBeVisible();
  for (const choice of ["맛", "힐링", "도보"]) await page.getByRole("button", { name: choice, exact: true }).click();
  await next.click();
  await expect(heading("종교적 고려가 필요한가요?")).toBeVisible();
  await expect(page.getByRole("button", { name: "설정 완료" })).toBeDisabled();
  await skip.click();

  await expect(heading("여행 취향을 모두 알아봤어요.")).toBeVisible();
  await expect(page.getByText("맛집 탐방", { exact: true })).toBeVisible();
  await expect(page.getByText("2명", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "여행 계획 등록하기" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.getByText("함께 고른 여행 취향")).toBeVisible();
  await expect(page.getByText("2명과 함께")).toBeVisible();

  await page.getByRole("banner").getByRole("link", { name: "홈으로", exact: true }).click();
  await expect(page).toHaveURL(/\/start$/);
  await expect(heading("여행 취향을 모두 알아봤어요.")).toBeVisible();
});

test("설정 메뉴에서 언어와 여행 화면 내비게이션을 바꾸면 새로고침 후에도 유지된다", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("#intro-title")).toContainText("From plans to memories");
  await noHorizontalScroll(page);

  const menu = page.getByRole("button", { name: "Settings menu" });
  await menu.click();
  const settings = page.getByRole("dialog", { name: "Settings" });
  await settings.getByText("한국어").click();
  await expect(page.locator("html")).toHaveAttribute("lang", "ko");
  await expect(page.locator("#intro-title")).toContainText("계획부터 여행까지");
  await expect(page).toHaveTitle("triPilot · 당신다운 여행의 시작");
  await page.getByRole("dialog", { name: "설정" }).getByText("플로팅 버튼").click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "설정 메뉴" })).toBeFocused();

  await page.reload();
  await expect(page.locator("#intro-title")).toContainText("계획부터 여행까지");
  await registerExampleTrip(page);
  await expect(page.locator("#trip-pane-button-schedule")).toBeHidden();
  const toggle = page.getByRole("button", { name: "일정 · 메뉴 열기 또는 닫기" });
  await toggle.click();
  await expect(toggle).toBeHidden();
  await page.getByRole("button", { name: "채팅", exact: true }).click();
  await expect(page.locator("#trip-pane-chat")).toBeVisible();
  const chatToggle = page.getByRole("button", { name: "채팅 · 메뉴 열기 또는 닫기" });
  await expect(chatToggle).toHaveAttribute("aria-expanded", "false");
  await expect(chatToggle).toBeFocused();
  await noHorizontalScroll(page);
});

test("소개 첫 화면의 언어 카드로 언어를 고르면 카드가 접히고, 이용 방법 캡처를 마우스로 끌거나 버튼으로 넘겨 볼 수 있다", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  const card = page.getByRole("button", { name: /LANGUAGE/ });
  await expect(card).toHaveAttribute("aria-expanded", "false");
  await card.click();
  await expect(card).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("button", { name: "한국어", exact: true }).click();
  await expect(card).toHaveAttribute("aria-expanded", "false");
  await expect(card).toBeFocused();
  await expect(page.locator("html")).toHaveAttribute("lang", "ko");
  await expect(page.locator("#intro-title")).toContainText("계획부터 여행까지");
  await page.reload();
  await expect(page.getByRole("button", { name: /LANGUAGE/ })).toContainText("한국어");

  await page.getByRole("button", { name: "다음 화면" }).first().click();
  const guide = page.getByRole("region", { name: "triPilot 이용 방법" });
  const firstShot = guide.getByRole("group", { name: "1 / 4" }).getByRole("img");
  await expect(firstShot).toHaveAccessibleName("앱 화면: 나의 여행 취향 알려주기");
  await expect.poll(() => firstShot.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);

  const track = guide.getByRole("group", { name: "1 / 4" }).locator("..");
  // Measure only after the page has finished snapping to the second screen.
  await expect.poll(() => page.locator("main").evaluate((main) => Math.abs(main.scrollTop - (main.children[1] as HTMLElement).offsetTop))).toBeLessThan(2);
  const dragBy = async (distance: number) => {
    const box = (await track.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + distance, box.y + box.height / 2, { steps: 8 });
    await page.mouse.up();
  };
  const offsetFromCard = (index: number) => track.evaluate((element, card) => {
    const cards = [...element.children] as HTMLElement[];
    return Math.abs(element.scrollLeft - (cards[card].offsetLeft - cards[0].offsetLeft));
  }, index);
  await dragBy(-150);
  await expect(guide.getByText("2 / 4", { exact: true })).toBeVisible();
  await expect.poll(() => offsetFromCard(1)).toBeLessThan(2);
  await dragBy(-20);
  await expect.poll(() => offsetFromCard(1)).toBeLessThan(2);
  await dragBy(200);
  await expect(guide.getByText("1 / 4", { exact: true })).toBeVisible();
  await expect.poll(() => offsetFromCard(0)).toBeLessThan(2);

  const next = guide.getByRole("button", { name: "다음 단계" });
  for (const step of [2, 3, 4]) {
    await next.click();
    await expect(guide.getByText(`${step} / 4`, { exact: true })).toBeVisible();
  }
  await expect(next).toHaveAttribute("aria-disabled", "true");
  await noHorizontalScroll(page);
});
