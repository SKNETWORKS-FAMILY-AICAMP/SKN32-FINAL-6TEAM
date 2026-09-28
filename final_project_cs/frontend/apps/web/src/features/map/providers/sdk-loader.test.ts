import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createSdkLoader } from "./sdk-loader";

function fakeBrowser() {
  const globals: Record<string, unknown> = {};
  const scripts: {
    src: string; async: boolean; dataset: Record<string, string>;
    onerror: null | (() => void); remove: ReturnType<typeof vi.fn>;
  }[] = [];
  vi.stubGlobal("window", globals);
  vi.stubGlobal("document", {
    createElement: () => ({ src: "", async: false, dataset: {}, onerror: null, remove: vi.fn() }),
    head: { append: (script: typeof scripts[number]) => scripts.push(script) },
  });
  function ready(index = scripts.length - 1) {
    const callback = new URL(scripts[index].src).searchParams.get("callback")!;
    (globals[callback] as () => void)();
  }
  function failAuth() { (globals.gm_authFailure as () => void)(); }
  return { globals, scripts, ready, failAuth };
}

function setupLoader() {
  const browser = fakeBrowser();
  const read = vi.fn<() => { loaded: true } | undefined>(() => ({ loaded: true }));
  const loader = createSdkLoader({
    provider: "google", label: "Google 지도", authCallback: "gm_authFailure", read,
    url: (key, callback) => `https://maps.example.test/sdk?${new URLSearchParams({ key, callback })}`,
    timeoutMs: 100,
  });
  return { ...browser, ...loader, read };
}

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe("browser map SDK loading", () => {
  it("shares a single pending and completed script across consumers", async () => {
    const sdk = setupLoader();
    const first = sdk.load("public-key");
    expect(sdk.load("public-key")).toBe(first);
    expect(sdk.scripts).toHaveLength(1);
    sdk.ready();
    await expect(first).resolves.toEqual({ loaded: true });
    expect(sdk.load("public-key")).toBe(first);
    expect(sdk.scripts).toHaveLength(1);
  });

  it("removes a failed network request and retries with a fresh callback", async () => {
    const sdk = setupLoader();
    const first = sdk.load("public-key");
    const rejection = expect(first).rejects.toThrow("네트워크");
    sdk.scripts[0].onerror?.();
    await rejection;
    expect(sdk.scripts[0].remove).toHaveBeenCalledOnce();
    const retry = sdk.load("public-key");
    expect(sdk.scripts[1].src).not.toBe(sdk.scripts[0].src);
    sdk.ready(0); // Late response from a cancelled request cannot settle the retry.
    sdk.ready(1);
    await expect(retry).resolves.toEqual({ loaded: true });
  });

  it("times out a callback that never arrived and permits retry", async () => {
    const sdk = setupLoader();
    const first = sdk.load("public-key");
    const rejection = expect(first).rejects.toThrow("초과");
    await vi.advanceTimersByTimeAsync(101);
    await rejection;
    expect(sdk.scripts[0].remove).toHaveBeenCalledOnce();
    const retry = sdk.load("public-key");
    sdk.ready();
    await expect(retry).resolves.toEqual({ loaded: true });
  });

  it("rejects readiness callbacks when the expected SDK API is missing", async () => {
    const sdk = setupLoader();
    sdk.read.mockReturnValue(undefined);
    const first = sdk.load("public-key");
    const rejection = expect(first).rejects.toThrow("라이브러리");
    sdk.ready();
    await rejection;
    sdk.read.mockReturnValue({ loaded: true });
    const retry = sdk.load("public-key");
    sdk.ready();
    await expect(retry).resolves.toEqual({ loaded: true });
  });

  it("rejects early authentication failure without exposing the credential", async () => {
    const sdk = setupLoader();
    const first = sdk.load("browser-key-value");
    const rejection = expect(first).rejects.toThrow("인증에 실패");
    sdk.failAuth();
    await rejection;
    await expect(sdk.load("browser-key-value")).rejects.not.toThrow("browser-key-value");
    expect(sdk.scripts).toHaveLength(1);
  });

  it("broadcasts late auth failures only to mounted consumers and preserves an existing hook", async () => {
    const sdk = setupLoader();
    const previous = vi.fn();
    sdk.globals.gm_authFailure = previous;
    const first = sdk.load("public-key");
    sdk.ready();
    await first;
    const active = vi.fn();
    const removed = vi.fn();
    sdk.watchAuthFailure(active);
    const unsubscribe = sdk.watchAuthFailure(removed);
    unsubscribe();
    sdk.failAuth();
    expect(active).toHaveBeenCalledOnce();
    expect(removed).not.toHaveBeenCalled();
    expect(previous).toHaveBeenCalledOnce();
    await expect(sdk.load("public-key")).rejects.toThrow("새로고침");
  });

  it("requires a reload to change credentials within a loaded provider", async () => {
    const sdk = setupLoader();
    const first = sdk.load("public-key");
    sdk.ready();
    await first;
    await expect(sdk.load("changed-key")).rejects.toThrow("키가 변경");
    expect(sdk.scripts).toHaveLength(1);
  });
});
