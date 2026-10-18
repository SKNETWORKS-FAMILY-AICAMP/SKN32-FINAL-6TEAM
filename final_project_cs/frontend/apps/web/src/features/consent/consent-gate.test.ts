import { beforeEach, describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

const h = vi.hoisted(() => ({
  pathname: "/mypage/account", result: "failed", state: 0,
  effects: [] as (() => unknown)[], reconcile: vi.fn(async () => "failed"),
}));
vi.mock("react", async (original) => ({
  ...await original<typeof import("react")>(),
  useState: (initial: unknown) => [h.state++ === 1 ? h.result : initial, vi.fn()],
  useEffect: (effect: () => unknown) => { h.effects.push(effect); },
  useSyncExternalStore: () => true,
}));
vi.mock("next/navigation", () => ({ usePathname: () => h.pathname, useRouter: () => ({ replace: vi.fn() }) }));
vi.mock("@/lib/settings", () => ({ useT: () => (ko: string) => ko, useSettings: () => ({ language: "ko" }) }));
vi.mock("@/components/ui", () => ({ Button: "button", ButtonLink: "a" }));
vi.mock("@/components/layout/device-frame", () => ({ DeviceFrame: "div" }));
vi.mock("@/features/onboarding/onboarding", () => ({ Onboarding: () => "terms-body" }));
vi.mock("./consent-store", () => ({ useRequiredConsents: () => false, useConsentsSynced: () => false }));
vi.mock("./consent-sync", () => ({
  reconcileConsents: h.reconcile, CONSENT_CHECK_STEPS: [["확인", "Check"]],
}));
import { ConsentGate } from "./consent-gate";

describe("로그인과 공개 화면의 동의 오류 분리", () => {
  beforeEach(() => {
    h.state = 0; h.result = "failed"; h.effects = []; h.reconcile.mockClear();
    vi.stubGlobal("window", { location: { search: "", pathname: h.pathname } });
  });

  it.each(["/mypage/account", "/auth/done", "/start", "/notices", "/notices/example", "/"])("%s에서는 동의 조회 실패가 화면을 덮지 않는다", (path) => {
    h.pathname = path;
    const html = renderToStaticMarkup(createElement(ConsentGate, null, "login-content"));
    expect(html).toContain("login-content");
    expect(html).not.toContain("동의 기록을 확인하지 못했어요");
    h.effects[0]();
    expect(h.reconcile).not.toHaveBeenCalled();
  });

  it("보호 화면의 실제 동의 오류는 숨기지 않는다", () => {
    h.pathname = "/trips";
    const html = renderToStaticMarkup(createElement(ConsentGate, null, "private-content"));
    expect(html).toContain("동의 기록을 확인하지 못했어요");
  });
});
