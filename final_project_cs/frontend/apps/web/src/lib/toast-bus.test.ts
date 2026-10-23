import { afterEach, describe, expect, it, vi } from "vitest";
import { clearPendingToast, onToast, pushToast, takePendingToast, type BusToast } from "./toast-bus";

afterEach(() => { takePendingToast(); vi.useRealTimers(); });

describe("notice handoff across intake route replacement", () => {
  it("keeps the undo action and only the remaining display time", () => {
    vi.useFakeTimers();
    const run = vi.fn();
    expect(pushToast({ text: "Course Keeper is off.", action: { label: "Undo", run } })).toBe(false);
    vi.advanceTimersByTime(600);
    const held = takePendingToast();
    expect(held?.ms).toBe(3900);
    held?.action?.run();
    expect(run).toHaveBeenCalledOnce();
    expect(takePendingToast()).toBeNull();
  });

  it("hands the notice to the new check-screen listener once", () => {
    pushToast({ text: "Stopped watching" });
    const receive = vi.fn();
    const unsubscribe = onToast(receive);
    expect(receive).toHaveBeenCalledOnce();
    expect(receive.mock.calls[0][0].text).toBe("Stopped watching");
    expect(takePendingToast()).toBeNull();
    unsubscribe();
  });

  it("does not replay an expired notice", () => {
    vi.useFakeTimers();
    pushToast({ text: "Plan checked" });
    vi.advanceTimersByTime(2801);
    expect(takePendingToast()).toBeNull();
  });

  it("keeps persistent error notices until explicitly dismissed", () => {
    vi.useFakeTimers();
    pushToast({ text: "Retry this change", stay: true });
    vi.advanceTimersByTime(60_000);
    expect(takePendingToast()).toMatchObject({ text: "Retry this change", stay: true });
  });

  it("does not replay a dismissed notice or clear a newer one", () => {
    const first: BusToast = { text: "First" };
    const newer: BusToast = { text: "Newer" };
    pushToast(first);
    pushToast(newer);
    clearPendingToast(first);
    expect(takePendingToast()?.text).toBe("Newer");
    pushToast(first);
    clearPendingToast(first);
    expect(takePendingToast()).toBeNull();
  });

  it("does not replay notices already delivered to a mounted screen", () => {
    const receive = vi.fn();
    const unsubscribe = onToast(receive);
    expect(pushToast({ text: "Updated departure" })).toBe(true);
    expect(receive).toHaveBeenCalledOnce();
    expect(takePendingToast()).toBeNull();
    unsubscribe();
  });
});
