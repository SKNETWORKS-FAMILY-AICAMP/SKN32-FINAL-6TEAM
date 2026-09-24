import { expect, test } from "@playwright/test";
import { noHorizontalScroll, registerExampleTrip, useKorean } from "./helpers/app";

test.beforeEach(async ({ page }) => { await useKorean(page); });

test("여행 화면은 일차·일정·방문 순서 선택을 연결하고 대화와 수정 원본을 보존한다", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { source, tripId } = await registerExampleTrip(page);
  const timeline = page.locator("#trip-pane-schedule");
  const map = page.locator("#trip-pane-map");
  const tab = (name: string) => page.getByRole("button", { name, exact: true });

  await page.getByRole("button", { name: /2일차/ }).click();
  await expect(page.getByRole("button", { name: /2일차/ })).toHaveAttribute("aria-pressed", "true");
  await expect(timeline.getByRole("heading", { name: "2일차 일정" })).toBeVisible();
  await expect(timeline.getByRole("button", { name: /성수동 쇼핑/ })).toHaveCount(0);

  const museum = timeline.getByRole("button", { name: /국립중앙박물관/ });
  await museum.click();
  await expect(museum).toHaveAttribute("aria-expanded", "true");
  await expect(timeline.locator("dl")).toContainText("다음 일정12:00 · 이촌동 점심 식당");
  await timeline.getByRole("button", { name: "방문 순서 보기" }).click();
  await expect(map).toBeVisible();
  await expect(timeline).toBeHidden();
  await expect(map.getByRole("button", { name: "2. 국립중앙박물관" })).toHaveAttribute("aria-pressed", "true");
  await expect(map.getByRole("button", { name: "2. 국립중앙박물관" })).toBeFocused();

  await map.getByRole("button", { name: "7. 호텔 복귀" }).click();
  await expect(map.getByRole("heading", { name: "호텔 복귀" })).toBeVisible();
  await map.getByRole("button", { name: "일정 상세 보기" }).click();
  const lastStop = timeline.getByRole("button", { name: /호텔 복귀/ });
  await expect(lastStop).toHaveAttribute("aria-expanded", "true");
  await expect(lastStop).toBeFocused();
  await expect(lastStop).toBeInViewport();
  await expect(timeline.locator('article[data-selected="true"]')).toContainText("호텔 복귀");

  await tab("채팅").click();
  const log = page.getByRole("log", { name: "여행 대화 이력" });
  await expect(log).toContainText("등록한 일정에서 궁금한 내용을 골라 주세요.");
  await page.getByRole("button", { name: "하루 요약", exact: true }).click();
  await expect(page.getByText("답변을 준비하고 있어요…", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "메시지 전송" })).toBeDisabled();
  const lastReply = log.locator('article[data-role="assistant"]').last();
  await expect(lastReply).toContainText("2026-09-16");
  await expect(lastReply).toContainText("1. 09:00 · 호텔 조식");
  await expect(lastReply).not.toContainText("성수동 쇼핑");
  await expect(page.getByRole("button", { name: "메시지 전송" })).toBeEnabled();
  await page.getByRole("button", { name: "다음 일정", exact: true }).click();
  await expect(lastReply).toContainText("호텔 복귀는 이날 마지막으로 등록한 일정이에요.");

  const question = "국립중앙박물관 일정 알려 주세요.";
  await page.getByLabel("여행 메시지", { exact: true }).fill(question);
  await page.getByRole("button", { name: "메시지 전송" }).click();
  await expect(page.getByLabel("여행 메시지", { exact: true })).toHaveValue("");
  await expect(log.locator('article[data-role="assistant"]').last()).toContainText("국립중앙박물관");
  await page.reload();
  await tab("채팅").click();
  await expect(page.getByRole("log").getByText(question, { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "일정 수정", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/new\\?from=${tripId}$`));
  await expect(page.getByLabel("나의 여행 계획")).toHaveValue(source);
});

test("375px와 320px에서 하단 탭으로 일정·방문 순서·채팅을 바꾸고 전송 실패를 다시 보낸다", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await registerExampleTrip(page);
  for (const width of [375, 320]) {
    await page.setViewportSize({ width, height: 812 });
    for (const [label, id] of [["일정", "schedule"], ["방문 순서", "map"], ["채팅", "chat"]]) {
      const button = page.getByRole("button", { name: label, exact: true });
      await button.click();
      await expect(button).toHaveAttribute("aria-pressed", "true");
      await expect(page.locator(`#trip-pane-${id}`)).toBeVisible();
      for (const other of ["schedule", "map", "chat"].filter((item) => item !== id)) await expect(page.locator(`#trip-pane-${other}`)).toBeHidden();
      await noHorizontalScroll(page);
    }
  }

  await page.getByRole("button", { name: "메시지 전송" }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("메시지를 입력해 주세요.");
  await page.evaluate(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key: string, value: string) {
      if (key.startsWith("tripilot.web-mvp.trip:")) {
        Storage.prototype.setItem = original;
        throw new DOMException("Storage unavailable for this attempt", "QuotaExceededError");
      }
      return original.call(this, key, value);
    };
  });
  const question = "예약 표시를 알려 주세요.";
  await page.getByLabel("여행 메시지", { exact: true }).fill(question);
  await page.getByRole("button", { name: "메시지 전송" }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("메시지를 보내지 못했어요.");
  await expect(page.getByLabel("여행 메시지", { exact: true })).toHaveValue(question);
  await page.getByRole("button", { name: "다시 보내기", exact: true }).click();
  await expect(page.getByLabel("여행 메시지", { exact: true })).toHaveValue("");
  await expect(page.getByRole("log").locator('article[data-role="user"]')).toHaveCount(1);
  await expect(page.getByRole("log").locator('article[data-role="assistant"]').last()).toContainText("성수 예약 식당");
  await expect(page.locator("#main-content").getByRole("alert")).toHaveCount(0);
});

test("이 탭에 없는 여행 주소에서는 오류와 다시 등록할 경로를 제공한다", async ({ page }) => {
  await page.goto(`/trips/${crypto.randomUUID()}`);
  await expect(page.getByRole("heading", { name: "여행 정보를 불러오지 못했어요" })).toBeVisible();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("이 탭에 저장된 여행을 찾을 수 없어요.");
  await page.getByRole("button", { name: "다시 불러오기", exact: true }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("이 탭에 저장된 여행을 찾을 수 없어요.");
  await expect(page.getByRole("heading", { name: "여행 채팅", exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "여행 계획 등록", exact: true }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.getByRole("heading", { name: "이제, 여행을 담아볼까요?" })).toBeVisible();
});
