import { expect, test } from '@playwright/test';
import { mockServer } from './helpers';
import { openFinished, head } from './plan-check-kit';

for (const width of [375, 1280]) test(`시각 고정은 그림자 상자가 아닌 실제 날짜 버튼 아래 기준 (${width}px)`, async ({ page, request }, info) => {
  await page.setViewportSize({ width, height: 812 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await mockServer(request).reset();
  await openFinished(page, request, undefined, { intakeEvents: 'off' });
  await head(page, '경복궁 관람').click();
  const body = page.locator('div[class*=sheetBody]');
  const settle = () => body.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  const metrics = () => body.evaluate(element => {
    const row = element.querySelector('[data-entry-id="0-0"]')!;
    const time = row.querySelector('[data-stop-start]')!.getBoundingClientRect();
    const title = row.querySelector('[class*=cardTitle]')!.getBoundingClientRect();
    const strip = document.querySelector('[role=tablist]')!;
    const buttons = Array.from(strip.querySelectorAll('button')).map(button => button.getBoundingClientRect());
    return { top: time.top, center: time.top + time.height / 2, titleCenter: title.top + title.height / 2,
      stripBottom: strip.getBoundingClientRect().bottom, buttonBottom: Math.max(...buttons.map(rect => rect.bottom)), rowBottom: row.getBoundingClientRect().bottom };
  });
  await body.evaluate(element => { element.scrollTop = 0; });
  await settle();
  const original = await metrics();
  expect(Math.abs(original.center - original.titleCenter)).toBeLessThan(3);
  await body.evaluate((element, top) => { element.scrollTop = top; }, original.top - original.buttonBottom + 20);
  await settle();
  const stuck = await metrics();
  await info.attach('actual-boundary', { body: JSON.stringify({ original, stuck }), contentType: 'application/json' });
  expect(Math.abs(stuck.top - stuck.buttonBottom)).toBeLessThanOrEqual(4);
  await body.evaluate(element => { element.scrollTop += 20; });
  await settle();
  expect(Math.abs((await metrics()).top - stuck.top)).toBeLessThan(1);
  await page.screenshot({ path: info.outputPath(`time-boundary-${width}.png`), fullPage: true });
  await body.evaluate(element => { element.scrollTop = 0; });
  await settle();
  expect(Math.abs((await metrics()).top - original.top)).toBeLessThan(1);
});
