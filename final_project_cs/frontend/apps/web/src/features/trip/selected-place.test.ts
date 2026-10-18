import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { StopRow, PastStopRow } from "./trip-rows";
import { toMapPoints } from "../map/map-points";
import { mapStopsWithPlaceNames, stopDisplayName } from "./stop-display";
import type { TripStop } from "./model";

const chosen: TripStop = { id: "qa-stop", date: "2026-10-25", time: "19:00", endTime: "20:30", title: "호텔", place: "선택한 서울 숙소", booking: "booked", pinned: true, notes: "", coordinates: { lat: 37.57, lng: 126.99 } };
const noop = () => {};
const card = (stop: TripStop) => renderToStaticMarkup(createElement(StopRow, { stop, open: false, selected: false, onToggle: noop, onDetail: noop, onMapApps: noop }));

describe("registered selected place", () => {
  it("shows the saved place in the main card and preserves the source title and protection", () => {
    const html = card(chosen);
    expect(html).toMatch(/<strong[^>]*>선택한 서울 숙소<\/strong>/);
    expect(html).toContain("예약 있음");
    expect(html).toContain("고정한 일정");
    expect(html).toContain("19:00");
    expect(html).toContain("20:30");
    expect(chosen.title).toBe("호텔");
  });
  it("shows the saved place in a folded past card", () => {
    const html = renderToStaticMarkup(createElement(PastStopRow, { stop: chosen, onToggle: noop }));
    expect(html).toContain("선택한 서울 숙소");
  });
  it("uses the same saved name on the map without changing IDs, time or coordinates", () => {
    expect(toMapPoints(mapStopsWithPlaceNames([chosen]))[0]).toMatchObject({ id: chosen.id, title: chosen.place, time: chosen.time, endTime: chosen.endTime, coordinates: chosen.coordinates });
    expect(chosen.title).toBe("호텔");
  });
  it("falls back for empty place names and leaves the source unchanged", () => {
    for (const place of [undefined, "", "   "]) expect(stopDisplayName({ ...chosen, place })).toBe("호텔");
    expect(stopDisplayName({ ...chosen, place: "  선택한 서울 숙소  " })).toBe(chosen.place);
    expect(chosen.title).toBe("호텔");
  });
  it("renders a supplied place name as text", () => {
    const html = card({ ...chosen, place: "<script>test</script>" });
    expect(html).toContain("&lt;script&gt;test&lt;/script&gt;");
    expect(html).not.toContain("<script>");
  });
  it("keeps the written title when the saved place is missing", () => {
    const html = card({ ...chosen, place: undefined });
    expect(html).toMatch(/<strong[^>]*>호텔<\/strong>/);
  });
});
