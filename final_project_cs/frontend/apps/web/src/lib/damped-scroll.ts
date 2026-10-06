/**
 * `[2026-10-06 사용자 지적 — 스크롤이 딱딱 끊어진다, 댐퍼를 줘서 부드럽게]` A scroll that goes to its target like a damped spring (critically damped: it starts softly, runs, and settles without a bounce) instead of
 * the browser's fixed-length smooth scroll, which restarts at every small step and so looks jerky when a list is followed row by row. A new target while one is running only moves the target - the motion
 * goes on from where it is, with the speed it has (that is what keeps a followed list smooth as rows are added).
 */
interface Run { target: number; position: number; speed: number; last: number; frame: number | null }

const runs = new WeakMap<HTMLElement, Run>();
const wired = new WeakSet<HTMLElement>();

/**
 * The customer's own hand (wheel, finger, key, press) ends the screen's scroll where it is. ★Not "the list moved to somewhere we did not put it": a layout change (a card opening, rows being added) moves
 * `scrollTop` by itself and must not be taken for the customer.
 */
function listenForTheCustomer(element: HTMLElement) {
  if (wired.has(element)) return;
  wired.add(element);
  const stop = () => cancelDampedScroll(element);
  for (const type of ["wheel", "touchstart", "pointerdown", "keydown"]) element.addEventListener(type, stop, { passive: true });
}

/** 1/s: how stiff the spring is. About 4/OMEGA seconds to settle - 6 is a calm half second to a second. */
export const DEFAULT_OMEGA = 6;

/** The position after one step of a critically damped spring (semi-implicit Euler; `dt` in seconds). Pure, so it is tested without a browser. */
export function dampStep(position: number, speed: number, target: number, omega: number, dt: number): { position: number; speed: number } {
  const accel = -2 * omega * speed - omega * omega * (position - target);
  const nextSpeed = speed + accel * dt;
  return { position: position + nextSpeed * dt, speed: nextSpeed };
}

/** Whether the motion is done: close enough and slow enough. */
export const settled = (position: number, speed: number, target: number) => Math.abs(position - target) < 0.5 && Math.abs(speed) < 8;

export function dampedScrollTo(element: HTMLElement, top: number, omega = DEFAULT_OMEGA): void {
  const max = Math.max(0, element.scrollHeight - element.clientHeight);
  const target = Math.min(Math.max(0, top), max);
  const reduced = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced || typeof requestAnimationFrame !== "function") { element.scrollTop = target; return; }
  const running = runs.get(element);
  if (running) { running.target = target; return; }
  listenForTheCustomer(element);
  const run: Run = { target, position: element.scrollTop, speed: 0, last: performance.now(), frame: null };
  runs.set(element, run);
  const tick = (now: number) => {
    if (!element.isConnected) { runs.delete(element); return; }
    const dt = Math.min(0.05, (now - run.last) / 1000);
    run.last = now;
    const next = dampStep(run.position, run.speed, run.target, omega, dt);
    run.position = next.position; run.speed = next.speed;
    if (settled(run.position, run.speed, run.target)) { element.scrollTop = run.target; runs.delete(element); return; }
    element.scrollTop = run.position;
    run.frame = requestAnimationFrame(tick);
  };
  run.frame = requestAnimationFrame(tick);
}

/** Stop the screen's own scroll where it is. */
export function cancelDampedScroll(element: HTMLElement | null): void {
  if (!element) return;
  const run = runs.get(element);
  if (run?.frame != null) cancelAnimationFrame(run.frame);
  runs.delete(element);
}
