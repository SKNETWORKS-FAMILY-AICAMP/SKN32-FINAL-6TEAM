import { afterEach, describe, expect, it, vi } from "vitest";
import { askBrowserNotify, browserNotify, browserNotifyState } from "./browser-notify";

// 시험 환경은 node 라 window 가 없다 — 필요한 만큼만 window 를 꽂는다(실제 브라우저 알림은 띄우지 않는다).
type Shown = { title: string; options?: { body?: string; tag?: string }; onclick: (() => void) | null; close: () => void };

function install(permission: "default" | "granted" | "denied", answer: "default" | "granted" | "denied" = permission) {
  const shown: Shown[] = [];
  class FakeNotification {
    static permission = permission;
    static requestPermission = vi.fn(async () => { FakeNotification.permission = answer; return answer; });
    onclick: (() => void) | null = null;
    close = vi.fn();
    constructor(public title: string, public options?: { body?: string; tag?: string }) { shown.push(this as unknown as Shown); }
  }
  const focus = vi.fn();
  vi.stubGlobal("window", { Notification: FakeNotification, focus });
  return { shown, FakeNotification, focus };
}

afterEach(() => vi.unstubAllGlobals());

describe("browser notifications", () => {
  it("reports unsupported when the browser has no Notification", () => {
    vi.stubGlobal("window", { focus: vi.fn() });
    expect(browserNotifyState()).toBe("unsupported");
    expect(browserNotify("t", "b", "k", undefined, () => false)).toBe(false);
  });

  it("asks only when called and returns the new state", async () => {
    const { FakeNotification } = install("default", "granted");
    expect(browserNotifyState()).toBe("default");
    expect(FakeNotification.requestPermission).not.toHaveBeenCalled();
    expect(await askBrowserNotify()).toBe("granted");
    expect(FakeNotification.requestPermission).toHaveBeenCalledTimes(1);
  });

  it("shows nothing without permission", () => {
    const { shown } = install("denied");
    expect(browserNotify("새 알림", "본문", "n1", undefined, () => false)).toBe(false);
    expect(shown).toHaveLength(0);
  });

  it("shows nothing while the trip tab is in view (the in-screen bar is enough)", () => {
    const { shown } = install("granted");
    expect(browserNotify("새 알림", "본문", "n1", undefined, () => true)).toBe(false);
    expect(shown).toHaveLength(0);
  });

  it("shows one notification tagged with the notice key when the tab is not in view, and clicking opens the notices", () => {
    const { shown, focus } = install("granted");
    const open = vi.fn();
    expect(browserNotify("기상 특보", "[시뮬레이션] 강풍 특보", "trip:1:n1", open, () => false)).toBe(true);
    expect(shown).toHaveLength(1);
    expect(shown[0].title).toBe("기상 특보");
    expect(shown[0].options).toMatchObject({ body: "[시뮬레이션] 강풍 특보", tag: "trip:1:n1" });
    shown[0].onclick?.();
    expect(focus).toHaveBeenCalled();
    expect(open).toHaveBeenCalledTimes(1);
    expect(shown[0].close).toHaveBeenCalled();
  });
});
