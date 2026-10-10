import { expect, test, type Locator, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockServer, noHorizontalScroll } from './helpers';
import { head, openFinished } from './plan-check-kit';
import { useMapTiles } from './capture-map-tiles';

const shots = process.env.DATE_DIVIDER_SHOTS;
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
async function snap(page: Page, name: string) {
  if (!shots) return;
  await mkdir(shots, { recursive: true });
  await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}
async function phase(target: Locator, time: number) {
  await target.evaluate((e, t) => {
    const a = e.getAnimations({ subtree: true }).find(a => a instanceof CSSAnimation && /dayFloat|insertLineBreathe/.test(a.animationName));
    if (!a) throw new Error(`반복 애니메이션을 찾지 못했습니다: ${getComputedStyle(e, '::after').animationName}`);
    a.pause(); a.currentTime = t;
  }, time);
}
async function restart(target: Locator) {
  await target.evaluate(e => {
    // Discard test-only Web Animations overrides and restore the real CSS playback controls.
    const node = e as HTMLElement;
    if (node.hasAttribute('data-insert-near')) {
      node.removeAttribute('data-insert-near'); void node.offsetWidth; node.setAttribute('data-insert-near', '');
    } else {
      node.style.animation = 'none'; void node.offsetWidth; node.style.removeProperty('animation');
    }
  });
}
for (const width of [375, 1280]) {
  test(`날짜 부유·추가 가로선은 조작 시 멈추고 움직임 줄이기에서 정지 ${width}px`, async ({ page, request }) => {
    test.setTimeout(90_000);
    await page.setViewportSize({ width, height: 812 });
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    const tiles = shots ? await useMapTiles(page) : async () => {};
    const api = await openFinished(page, request, undefined, { intakeEvents: 'off' });
    await tiles();
    await expect(page.getByRole('status').filter({ hasText: '계획 확인 화면이에요' })).toHaveCount(0);
    await page.mouse.move(0, 0);
    const strip = page.getByRole('tablist', { name: '일차 고르기', includeHidden: true });
    await expect(strip).not.toHaveAttribute('data-quiet');
    await expect(strip).toHaveCSS('animation-duration', '4s');
    await phase(strip, 0);
    const body = page.locator('div[class*=sheetBody]');
    const origin = await strip.boundingBox(), bodyOrigin = await body.boundingBox();
    const marker = strip.locator('[class*=dayMarker]');
    const markerOrigin = await marker.boundingBox();
    await phase(strip, 2000);
    const raised = await strip.boundingBox(), raisedMarker = await marker.boundingBox();
    expect(raised!.y).toBeCloseTo(origin!.y - 2, 1);
    expect(raised!.height).toBe(origin!.height);
    expect(raisedMarker!.y - raised!.y).toBeCloseTo(markerOrigin!.y - origin!.y, 1);
    expect(await body.boundingBox()).toEqual(bodyOrigin);
    await snap(page, `date-float-${width}`);
    await restart(strip);
    const stripBox = (await strip.boundingBox())!;
    // A floating target is intentionally moving; move the real pointer without the locator stability gate.
    await page.mouse.move(stripBox.x + stripBox.width / 2, stripBox.y + stripBox.height / 2);
    await expect(strip).toHaveCSS('animation-play-state', 'paused');
    await expect.poll(() => strip.evaluate(e => e.getAnimations().filter(a => a instanceof CSSAnimation).every(a => a.playState === 'paused'))).toBe(true);
    await page.mouse.move(0, 0);
    await strip.getByRole('tab').first().focus(); await expect(strip).toHaveCSS('animation-play-state', 'paused');
    const handle = page.getByRole('button', { name: '목록 높이 바꾸기' });
    await handle.focus();
    for (let i = 0; i < 5; i++) await handle.press('ArrowUp');
    await head(page, '올리브영').click(); await page.mouse.move(0, 0);
    await expect(strip).not.toHaveAttribute('data-quiet');
    const seam = page.locator('[data-insert-near]'), add = seam.getByRole('button');
    await expect(add).toBeVisible();
    const line = () => seam.evaluate(e => {
      const c = getComputedStyle(e, '::after'), r = e.getBoundingClientRect();
      const button = e.querySelector('button')!.getBoundingClientRect();
      return { opacity: Number(c.opacity), height: c.height, left: c.left, right: c.right, width: r.width, y: r.y, centerX: r.x + r.width / 2, buttonX: button.x + button.width / 2, buttonY: button.y + button.height / 2, buttonWidth: button.width, buttonHeight: button.height, animation: c.animationName, state: c.animationPlayState };
    });
    await phase(seam, 0); const dim = await line();
    await phase(seam, 1500); const bright = await line();
    expect(bright.opacity - dim.opacity).toBeGreaterThan(.45);
    expect(bright.height).toBe('1px'); expect(bright.left).toBe('0px'); expect(bright.right).toBe('0px');
    expect(bright.buttonX).toBeCloseTo(bright.centerX, 1); expect(bright.buttonY).toBeCloseTo(bright.y, 1);
    expect(bright.buttonWidth).toBe(44); expect(bright.buttonHeight).toBe(44);
    expect(bright.buttonX).toBe(dim.buttonX); expect(bright.buttonY).toBe(dim.buttonY);
    await phase(strip, 2000); await snap(page, `divider-${width}`);
    if (shots && width === 375 && process.env.DATE_DIVIDER_PREVIEW === '1') {
      const frames = '.tmp/date-divider-preview-frames'; await mkdir(frames, { recursive: true });
      // Capture real browser frames over the common 12s cycle of the 4s row and 3s line.
      for (let i = 0; i < 60; i++) {
        await phase(strip, i * 200 % 4000); await phase(seam, i * 200 % 3000);
        await page.screenshot({ path: `${frames}/${String(i).padStart(3, '0')}.png` });
      }
    }
    await restart(strip); await restart(seam);
    await add.hover(); expect((await line()).state).toBe('paused');
    await add.focus(); expect((await line()).state).toBe('paused');
    const label = (await add.getAttribute('aria-label'))!;
    await add.click(); await expect(page.getByRole('searchbox', { name: '장소 검색', exact: true })).toBeFocused();
    await page.getByRole('button', { name: '일정 추가 취소', exact: true }).click();
    await expect(page.getByRole('button', { name: label, exact: true })).toBeFocused();
    await page.mouse.move(0, 0);
    await handle.focus();
    await restart(strip);
    await body.hover(); await page.mouse.wheel(0, 80);
    await expect(strip).toHaveAttribute('data-quiet'); await expect(strip).toHaveAttribute('inert', '');
    await expect(strip).not.toHaveAttribute('data-quiet'); await expect(strip).toHaveCSS('animation-play-state', 'running');
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await expect(strip).toHaveCSS('animation-name', 'none'); await expect(strip).toHaveCSS('transform', 'none');
    const staticSeam = page.locator('[data-insert-near]');
    expect(await staticSeam.evaluate(e => getComputedStyle(e, '::after').animationName)).toBe('none');
    expect(Number(await staticSeam.evaluate(e => getComputedStyle(e, '::after').opacity))).toBe(.6);
    await snap(page, `reduced-motion-${width}`);
    expect(await api.received('POST', '/edits')).toHaveLength(0); await noHorizontalScroll(page);
  });
}
