import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { StopRow, PastStopRow } from "./trip-rows";
import { stopDisplayName, stopPlaceNote } from "./stop-display";
import type { TripStop } from "./model";

// `[2026-10-21 사용자 결정 C — ST4F-706]` The customer's title is the stop's name; the chosen place shows under it when it differs (as the shared plan does).
const chosen: TripStop = { id: "qa-stop", date: "2026-10-25", time: "19:00", endTime: "20:30", title: "호텔", place: "선택한 서울 숙소", booking: "booked", pinned: true, notes: "", coordinates: { lat: 37.57, lng: 126.99 } };
const noop = () => {};
const card = (stop: TripStop) => renderToStaticMarkup(createElement(StopRow, { stop, open: false, selected: false, onToggle: noop, onDetail: noop, onMapApps: noop }));

describe("registered selected place", () => {
  it("names the main card by the written title and shows the saved place under it, keeping the protection marks", () => {
    const html = card(chosen);
    expect(html).toMatch(/<strong[^>]*>호텔<\/strong>/);
    expect(html).toMatch(/data-stop-place[^>]*>.*<span>선택한 서울 숙소<\/span>/);
    expect(html.indexOf("호텔</strong>")).toBeLessThan(html.indexOf("선택한 서울 숙소"));
    expect(html).toContain("예약 있음");
    expect(html).toContain("고정한 일정");
    expect(html).toContain("19:00");
    expect(html).toContain("20:30");
  });
  it("names a folded past card by the written title", () => {
    const html = renderToStaticMarkup(createElement(PastStopRow, { stop: chosen, onToggle: noop }));
    expect(html).toContain("<span>호텔</span>");
    expect(html).not.toContain("선택한 서울 숙소");
  });
  it("shows no place line when the place is missing, blank or the same as the title", () => {
    for (const place of [undefined, "", "   ", "호텔", " 호텔 "]) {
      expect(stopPlaceNote({ ...chosen, place })).toBeNull();
      expect(card({ ...chosen, place })).not.toContain("data-stop-place");
    }
    expect(stopPlaceNote({ ...chosen, place: "  선택한 서울 숙소  " })).toBe(chosen.place);
  });
  it("keeps the place name for place phrases, falling back to the title", () => {
    for (const place of [undefined, "", "   "]) expect(stopDisplayName({ ...chosen, place })).toBe("호텔");
    expect(stopDisplayName({ ...chosen, place: "  선택한 서울 숙소  " })).toBe(chosen.place);
  });
  it("renders a supplied place name as text", () => {
    const html = card({ ...chosen, place: "<script>test</script>" });
    expect(html).toContain("&lt;script&gt;test&lt;/script&gt;");
    expect(html).not.toContain("<script>");
  });
});
