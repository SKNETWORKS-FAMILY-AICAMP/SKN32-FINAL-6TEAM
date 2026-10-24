import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { toIntakeEvent } from "@/lib/live/intake-events";
import { StopEditor } from "./result-parts";
import { draftOfItem, draftProblem, completionText, type PlanItem } from "./model";
import { viewOfReview } from "./from-review";
import type { ReviewItem } from "@/lib/live/intake-review";
import type { PlanCheckView } from "./model";

vi.mock("@/lib/settings", () => ({ useT: () => (ko: string) => ko }));
const stop = { id: "s", title: "통인시장", date: "2026-10-15", startsAt: "12:00", endsAt: "13:00", place: "통인시장", noPlace: false,
  hoursState: "customer", toldHours: { open: "10:00", close: "24:00", closed_days: ["sun"] } } as PlanItem;

describe("customer hours editor contract", () => {
  it("never announces all checked when opening hours remain unknown", () => {
    const view = {items:[{...stop,hoursState:"unknown"}]} as PlanCheckView;
    expect(completionText(view, ko => ko)).toContain("운영시간을 못 찾은 곳 1곳");
    expect(completionText(view, ko => ko)).not.toContain("모두 확인했어요");
  });
  it("retains hours in item events", () => {
    const event = toIntakeEvent("item", JSON.stringify({id:"0-0", source_id:"s1", index:0, hours_state:"customer", customer_hours:stop.toldHours}));
    expect(event?.type).toBe("item");
    if (event?.type === "item") {
      expect(event.item.hours_state).toBe("customer");
      expect(event.item.customer_hours).toEqual(stop.toldHours);
    }
  });
  it("shows labelled fields only for customer or unknown sources and reopens midnight", () => {
    const html = renderToStaticMarkup(<StopEditor item={stop} onCancel={() => {}} onSave={async () => {}} />);
    expect(html).toContain("여는 시각");
    expect(html).toContain("닫는 시각");
    expect(html).toContain('value="00:00"');
    expect(html).toContain("알려 주신");
    const official = renderToStaticMarkup(<StopEditor item={{ ...stop, hoursState: "official" }} onCancel={() => {}} onSave={async () => {}} />);
    expect(official).not.toContain("여는 시각");
  });
  it("rejects partial, reversed, duplicated weekdays and all days closed", () => {
    const draft = draftOfItem(stop);
    expect(draft.hours?.close).toBe("00:00");
    expect(draftProblem({ ...draft, hours: { open: "10:00", close: "", closedDays: [] } })).toBe("hours");
    expect(draftProblem({ ...draft, hours: { open: "19:00", close: "10:00", closedDays: [] } })).toBe("hours");
    expect(draftProblem({ ...draft, hours: { open: "10:00", close: "19:00", closedDays: ["sun", "sun"] } })).toBe("hours");
    expect(draftProblem({ ...draft, hours: { open: "10:00", close: "19:00", closedDays: ["mon","tue","wed","thu","fri","sat","sun"] } })).toBe("hours");
  });
  it("carries the server state and told value into the displayed stop", () => {
    const item = { id: "0-0", title: "통인시장", date: "2026-10-15", place_state: "found", place: null, rows: [], hours_state: "customer", customer_hours: stop.toldHours } as unknown as ReviewItem;
    const view = viewOfReview({} as PlanCheckView, {items:[item],moves:[]}, "done");
    expect(view.items[0].hoursState).toBe("customer");
    expect(view.items[0].toldHours).toEqual(stop.toldHours);
  });
});
