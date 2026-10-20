import { describe, expect, it } from "vitest";
import { pickOf } from "./gateway";

/** `[2026-10-19 사용자 결정 — 못 찾은 장소는 직접 고르기로]` The chat answer's `pick` (`wiki/external/rest-endpoints/web-intakes.md` 「장소를 못 찾았을 때」), read as data. */
describe("the chat answer's 「직접 고르기」 (pick)", () => {
  it("keeps a change of a named stop and an add with its words — and only the fields the server sent", () => {
    expect(pickOf({ mode: "change", item_id: "trip-b", query: "민수네", prefill: {}, blocked: false, actions: ["pick_myself"] }))
      .toEqual({ mode: "change", itemId: "trip-b", query: "민수네", prefill: {}, blocked: false });
    expect(pickOf({ mode: "add", item_id: null, query: "민수네", prefill: { title: "민수네", date: "2026-10-21", starts_at: "19:00", kind: "dining" }, blocked: true }))
      .toEqual({ mode: "add", itemId: null, query: "민수네", prefill: { title: "민수네", date: "2026-10-21", startsAt: "19:00", kind: "dining" }, blocked: true });
  });

  it("drops what cannot be acted on: no stop to change, no words to add, an unknown mode, a malformed time", () => {
    expect(pickOf({ mode: "change", item_id: null, query: "민수네" })).toBeNull();
    expect(pickOf({ mode: "add", query: "" })).toBeNull();
    expect(pickOf({ mode: "move", item_id: "x", query: "y" })).toBeNull();
    expect(pickOf(null)).toBeNull();
    expect(pickOf({ mode: "add", query: "민수네", prefill: { starts_at: "7pm", date: "내일" } })?.prefill).toEqual({});
  });
});
