import { afterEach, expect, it, vi } from "vitest";
import { IntakeStarting } from "./intake-starting";
import { RegistrationScreen } from "../trip-registration/registration-screen";

const h = vi.hoisted(() => ({
  effects: [] as (() => void | (() => void))[], cleanups: [] as (() => void)[],
  start: null as null | { result: Promise<{ intake_id: string }>; text: string; files: File[]; plan: null; send: ReturnType<typeof vi.fn>; cancel: ReturnType<typeof vi.fn> },
  router: { replace: vi.fn(), push: vi.fn() }, remember: vi.fn(), end: vi.fn(),
}));
vi.mock("react", () => ({
  useState: (initial: unknown) => [typeof initial === "function" ? initial() : initial, vi.fn()],
  useMemo: (fn: () => unknown) => fn(), useRef: (value: unknown) => ({ current: value }),
  useCallback: (fn: unknown) => fn,
  useEffect: (fn: () => void | (() => void)) => { h.effects.push(fn); },
}));
vi.mock("next/navigation", () => ({ useRouter: () => h.router }));
vi.mock("@tanstack/react-query", () => ({ useQueryClient: () => ({ removeQueries: vi.fn() }) }));
vi.mock("@/lib/settings", () => ({ useT: () => (ko: string) => ko }));
vi.mock("@/lib/gateway", () => ({ tripsKey: ["trips"] }));
vi.mock("@/lib/live/intake-plan", () => ({ planFromIntake: vi.fn() }));
vi.mock("@/lib/live/intake-start", () => ({ intakeStart: () => h.start, rememberIntakeFailure: h.remember, endIntakeStart: h.end, rememberIntakeArrival: vi.fn() }));
vi.mock("@/features/plan-check/plan-check", () => ({ PlanCheck: () => null }));
vi.mock("@/features/plan-check/planning-progress", () => ({ PlanningProgress: () => null }));
vi.mock("@/components/layout/journey-shell", () => ({ JourneyShell: () => null }));
vi.mock("../trip-registration/trip-registration", () => ({ TripRegistration: () => null }));

afterEach(() => {
  h.cleanups.splice(0).forEach(fn => fn()); h.effects = []; h.start = null;
  vi.restoreAllMocks(); vi.clearAllMocks(); vi.unstubAllGlobals();
});

it.each([new TypeError("network down"), new Error("서버가 응답하지 않아요")])("returns the inline sending screen on failure even when navigation never commits: %s", async (error) => {
  h.start = { text: "서울 여행", files: [], plan: null, result: Promise.reject(error), send: vi.fn(), cancel: vi.fn() };
  vi.stubGlobal("requestAnimationFrame", () => 1); vi.stubGlobal("cancelAnimationFrame", vi.fn());
  const onReturn = vi.fn();
  IntakeStarting({ onReturn });
  h.effects.splice(0).forEach(fn => { const clean = fn(); if (clean) h.cleanups.push(clean); });
  await Promise.resolve();
  expect(h.remember).toHaveBeenCalledWith(h.start, error);
  expect(h.end).toHaveBeenCalledWith(h.start);
  expect(onReturn).toHaveBeenCalledOnce();
  expect(h.router.replace).toHaveBeenCalled();
  expect(h.start.send).not.toHaveBeenCalled(); // recovery never resubmits
});

it("gives the inline sending screen a way to restore the registration form", async () => {
  const react = await import("react");
  const setSending = vi.fn();
  vi.spyOn(react, "useState").mockReturnValueOnce([true, setSending]);
  const element = RegistrationScreen();
  expect(element.props.onReturn).toBeTypeOf("function");
  element.props.onReturn();
  expect(setSending).toHaveBeenCalledWith(false);
});

it("restores the form when the customer leaves a request that is still waiting", () => {
  h.start = { text: "서울 여행", files: [], plan: null, result: new Promise(() => {}), send: vi.fn(), cancel: vi.fn() };
  const onReturn = vi.fn();
  const element = IntakeStarting({ onReturn });
  element.props.onBack();
  expect(h.start.cancel).toHaveBeenCalledOnce();
  expect(h.remember).toHaveBeenCalledWith(h.start, "");
  expect(onReturn).toHaveBeenCalledOnce();
  expect(h.start.send).not.toHaveBeenCalled();
});

it("does not offer to resubmit an intake the server already took", async () => {
  h.start = { text: "서울 여행", files: [], plan: null, result: Promise.resolve({ intake_id: "taken" }), send: vi.fn(), cancel: vi.fn() };
  vi.stubGlobal("requestAnimationFrame", () => 1); vi.stubGlobal("cancelAnimationFrame", vi.fn());
  const onReturn = vi.fn();
  IntakeStarting({ onReturn });
  h.effects.splice(0).forEach(fn => { const clean = fn(); if (clean) h.cleanups.push(clean); });
  await Promise.resolve();
  expect(onReturn).not.toHaveBeenCalled();
  expect(h.remember).not.toHaveBeenCalled();
  expect(h.router.replace).toHaveBeenCalledWith(expect.stringContaining("taken"));
});
