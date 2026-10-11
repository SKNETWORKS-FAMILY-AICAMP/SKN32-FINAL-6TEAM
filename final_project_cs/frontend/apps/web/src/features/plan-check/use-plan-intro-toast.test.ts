import { afterEach, expect, it, vi } from "vitest";
import type { Translate } from "@/lib/i18n";
import { onToast, pushToast, type BusToast } from "@/lib/toast-bus";
import { usePlanIntroToast, useReadingToastHandoff } from "./use-plan-intro-toast";

const hooks = vi.hoisted(() => ({ refs: [] as { current: boolean }[], effects: [] as { deps?: readonly unknown[]; cleanup?: () => void }[], cursor: 0, pending: [] as (() => void)[] }));
vi.mock("react", () => ({
  useRef: (initial: boolean) => { const index = hooks.cursor++; return hooks.refs[index] ??= { current: initial }; },
  useEffect: (run: () => void | (() => void), deps: readonly unknown[]) => {
    const index = hooks.cursor++;
    const slot = hooks.effects[index] ??= {};
    if (slot.deps && deps.every((value, at) => Object.is(value, slot.deps![at]))) return;
    hooks.pending.push(() => { slot.cleanup?.(); slot.deps = deps; slot.cleanup = run() || undefined; });
  },
}));
const t = ((ko: string, en: string) => en || ko) as Translate;
function draw(done: boolean, show: (toast: BusToast) => void) {
  hooks.cursor = 0;
  // eslint-disable-next-line react-hooks/rules-of-hooks -- Node lifecycle harness commits mocked effects in declaration order.
  usePlanIntroToast(done, show, t);
  hooks.pending.splice(0).forEach((run) => run());
}
afterEach(() => {
  hooks.effects.forEach((effect) => effect.cleanup?.());
  hooks.refs = []; hooks.effects = []; hooks.pending = []; hooks.cursor = 0;
  vi.restoreAllMocks();
});
it("hands the reading-screen notice and undo action to the result owner at the transition", () => {
  const receive=vi.fn(), hide=vi.fn(), undo=vi.fn();
  const notice={toast:{text:"Course Keeper is off.",action:{label:"Undo",run:undo}}};
  const drawHandoff=(reading:boolean)=>{
    hooks.cursor=0;
    // eslint-disable-next-line react-hooks/rules-of-hooks -- Same lifecycle harness as draw above.
    useReadingToastHandoff(reading,notice,hide);
    hooks.pending.splice(0).forEach(run=>run());
  };
  drawHandoff(true);expect(hide).not.toHaveBeenCalled();
  const stop=onToast(receive);
  try {
    drawHandoff(false);
    expect(receive).toHaveBeenCalledExactlyOnceWith(notice.toast);
    receive.mock.calls[0][0].action.run();expect(undo).toHaveBeenCalledOnce();
    expect(hide).toHaveBeenCalledOnce();
    drawHandoff(false);expect(receive).toHaveBeenCalledTimes(1);
  } finally {stop();}
});
it("shows the normal completed-plan introduction once", () => {
  const show = vi.fn();
  draw(false, show); expect(show).not.toHaveBeenCalled();
  draw(true, show); expect(show).toHaveBeenCalledWith(expect.objectContaining({ text: "Check your plan" }));
  draw(true, show); expect(show).toHaveBeenCalledTimes(1);
});
it("keeps an English guardian action when completion arrives later, including its action", () => {
  const show = vi.fn(); const action = { label: "Undo", run: vi.fn() };
  draw(false, show);
  pushToast({ text: "Course Keeper is off.", action });
  draw(true, show);
  expect(show).toHaveBeenCalledTimes(1);
  expect(show).toHaveBeenLastCalledWith({ text: "Course Keeper is off.", action });
});
it("consumes a pending header notice before deciding whether to show the introduction", () => {
  vi.spyOn(Date, "now").mockReturnValue(1_000);
  pushToast({ text: "Course Keeper is off." });
  const show = vi.fn(); draw(true, show);
  expect(show).toHaveBeenCalledTimes(1);
  expect(show).toHaveBeenLastCalledWith({ text: "Course Keeper is off.", ms: 2800 });
});
