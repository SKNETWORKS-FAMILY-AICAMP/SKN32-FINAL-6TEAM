import { describe, expect, it } from "vitest";
import { itemRiskOf } from "./risks";

describe("deferred date risk decoding", () => {
  it("decodes only explicit deferral without hiding real findings", () => {
    expect(itemRiskOf({ status: "unknown", deferred: true })?.deferred).toBe(true);
    for (const row of [
      { status: "unknown", deferred: "true" },
      { status: "problem", deferred: true },
      { status: "unknown", deferred: true, unknown_categories: [{ category: "forecast", code: "source_failed" }] },
    ]) expect(itemRiskOf(row)?.deferred).toBe(false);
  });
});
