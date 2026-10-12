import { expect, test } from "@playwright/test";
import { mockServer, TRIP_ID, useKorean } from "./helpers";
import { openFinished } from "./plan-check-kit";
import { allowLocation, countLocationAsks, locationAsks, startWithLocationConsent } from "./location-kit";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("최초 약관에서 고른 위치 동의를 지도까지 이어 받아 다시 동의를 묻지 않는다", async ({ page, context, request }) => {
  await mockServer(request).scenario({ consents: "on" });
  await allowLocation(context, { latitude: 37.5796, longitude: 126.977 });
  await countLocationAsks(page); await useKorean(page);
  await page.goto("/start?terms=required");
  const location = page.locator('#consent-location');
  await expect(location).not.toBeChecked();
  await expect(page.locator('li[data-doc="location"] label')).toContainText("[선택]");
  for (const code of ["service_terms", "privacy", "location"]) await page.locator(`li[data-doc="${code}"] label`).click();
  await page.getByRole("button", { name: "동의하고 다음으로", exact: true }).click();
  await expect.poll(async () => (await mockServer(request).received("POST", "/v1/web/consents")).some(row => {
    const items = row.body?.items as { code: string; agreed: boolean }[] | undefined;
    return items?.some(item => item.code === "location" && item.agreed);
  })).toBe(true);
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByRole("img", { name: "내 위치", exact: true })).toBeVisible();
  expect(await locationAsks(page)).toBeGreaterThan(0);
  await expect(page.getByRole("dialog", { name: "내 위치로 이동" })).toHaveCount(0);
});

for (const screen of ["trip", "check"]) test(`${screen}: 브라우저 권한 미결정 상태이면 지도 진입만으로 위치를 요청하고 앱 동의 창은 반복하지 않는다`, async ({ page, context, request }) => {
  await allowLocation(context, { latitude: 37.5796, longitude: 126.977 });
  await startWithLocationConsent(page, true); await countLocationAsks(page);
  // 미결정 권한 분기를 계측하되 좌표는 Chrome의 시험 위치 공급자가 반환한다.
  await page.addInitScript(() => {
    const original = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = descriptor => descriptor.name === "geolocation" ? Promise.resolve({ state: "prompt" } as PermissionStatus) : original(descriptor);
  });
  if (screen === "check") await openFinished(page, request);
  else await page.goto(`/trips/${TRIP_ID}`);
  await expect.poll(() => locationAsks(page)).toBeGreaterThan(0);
  await expect(page.getByRole("img", { name: "내 위치", exact: true })).toBeVisible();
  await expect(page.getByRole("dialog", { name: "내 위치로 이동" })).toHaveCount(0);
});
