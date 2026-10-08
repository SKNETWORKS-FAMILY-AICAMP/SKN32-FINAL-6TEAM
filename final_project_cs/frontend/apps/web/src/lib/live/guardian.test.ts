import { describe, expect, it } from "vitest";
import { guardianOf } from "./gateway";

describe("the trip's Course Keeper as the screen reads it", () => {
  it("takes the server's {enabled, since, via} as it is", () => {
    expect(guardianOf({ enabled: true, since: "2026-10-06T05:00:00Z", via: "header" })).toEqual({ enabled: true, since: "2026-10-06T05:00:00Z", via: "header" });
    expect(guardianOf({ enabled: false, since: null, via: null })).toEqual({ enabled: false, since: null, via: null });
  });

  it("is null (no icon) when the server does not say: no object, or an enabled that is not true/false", () => {
    expect(guardianOf(undefined)).toBeNull();
    expect(guardianOf(null)).toBeNull();
    expect(guardianOf({})).toBeNull();
    expect(guardianOf({ enabled: "yes" })).toBeNull();
    expect(guardianOf({ enabled: 1 })).toBeNull();
  });

  it("makes nothing up for a field it was not sent", () => {
    expect(guardianOf({ enabled: true })).toEqual({ enabled: true, since: null, via: null });
    expect(guardianOf({ enabled: true, since: 5, via: {} })).toEqual({ enabled: true, since: null, via: null });
  });
});
