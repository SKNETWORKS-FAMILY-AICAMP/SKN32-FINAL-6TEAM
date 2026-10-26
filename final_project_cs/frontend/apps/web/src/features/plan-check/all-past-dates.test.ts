import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { translator } from "@/lib/i18n";
import type { ReviewItem, ReviewedIntakeView } from "@/lib/live/intake-review";

// `[2026-10-26]` 신규 계획의 모든 일정이 오늘 이전일 때 서버(d2ab93a65 `review.admission_dates`)가 검사에 붙이는 `date` 줄 — 계획 확인 화면에 어떻게 보이는지.
const h = vi.hoisted(() => ({ language: "ko" as "ko" | "en" }));
vi.mock("@/lib/settings", async (original) => ({
  ...await original<typeof import("@/lib/settings")>(),
  useT: () => (ko: string, en: string) => h.language === "ko" ? ko : en,
}));

import { readingOf } from "./from-intake";
import { reviewResultOf } from "./from-review";
import { stopToast } from "./map-description";
import { Checks, kindLabel, NeedsLine } from "./parts";
import { placeQuestion } from "./stop-questions";

/** The server's sentence as `review.py` writes it (no closing full stop). */
const SERVER = "모든 일정이 오늘 이전이에요. 여행 날짜를 확인해주세요";
const ENGLISH = "Every stop is before today. Please check the trip dates.";

const pastItem = (index: number, date: string, title: string): ReviewItem => ({
  id: `0-${index}`, source_id: "s1", index, title, kind: null, day: index + 1, date, starts_at: "10:00", ends_at: "11:00",
  locked: false, status: "review", can_lock: false, place_state: "found",
  place: { name: title, latitude: 37.57, longitude: 126.98, source: "kakao", kind: null }, candidates_hint: null,
  rows: [{ row: "place", result: "ok", text: title }, { row: "date", result: "bad", text: SERVER }],
});

/** A review as the server answers it for a wholly past new plan: every stop `review`, not lockable, `ready: false`. */
function allPastIntake(): ReviewedIntakeView {
  const items = [pastItem(0, "2020-05-01", "경복궁 관람"), pastItem(1, "2020-05-02", "광장시장 점심")];
  return {
    intake_id: "i1", status: "review", stage: "review", stage_label: "", revision: 2, fatal: null, trip_id: null, needs_review: [], check: null,
    sources: [{ source_id: "s1", kind: "text", filename: null, transcribed: false, items: [], trip: {}, reading: null,
      lines: [{ no: 1, text: "2020-05-01 10:00 경복궁 관람", read: true }, { no: 2, text: "2020-05-02 10:00 광장시장 점심", read: true }] }],
    review: { revision: 2, built_at: "", engine: "estimate", ready: false, needs: { items: 2, moves: 0, total: 2 }, items, moves: [] },
  } as unknown as ReviewedIntakeView;
}

const result = () => {
  const next = allPastIntake();
  return reviewResultOf(next, readingOf(next))!;
};

describe("a new plan whose every stop is before today, on the plan check", () => {
  beforeEach(() => { h.language = "ko"; });

  it("keeps the server's date line on every stop, as a must-fix line, and every stop needs a look", () => {
    const view = result();
    expect(view.items).toHaveLength(2);
    for (const item of view.items) {
      expect(item.verdict).toBe("review");
      expect(item.checks).toContainEqual({ kind: "date", result: "bad", text: SERVER });
    }
  });

  it("names the line 「날짜」 · 「Date」 instead of leaving its label empty", () => {
    expect(kindLabel("date", translator("ko"))).toBe("날짜");
    expect(kindLabel("date", translator("en"))).toBe("Date");
  });

  it("shows the server's own sentence on the Korean screen, unchanged", () => {
    const rows = result().items[0].checks;
    const html = renderToStaticMarkup(createElement(Checks, { rows }));
    expect(html).toContain(SERVER);
    expect(html).toContain("날짜");
    expect(renderToStaticMarkup(createElement(NeedsLine, { rows }))).toContain("<b>날짜</b>");
  });

  it("says it in English on the English screen — not the Korean sentence", () => {
    h.language = "en";
    const rows = result().items[0].checks;
    const html = renderToStaticMarkup(createElement(Checks, { rows }));
    expect(html).toContain(ENGLISH);
    expect(html).not.toContain(SERVER);
    expect(html).toContain(">Date<");
    expect(renderToStaticMarkup(createElement(NeedsLine, { rows }))).toContain("<b>Date</b>");
  });

  it("asks at the stopped card with the same sentence, in the screen's language", () => {
    const view = result();
    const item = view.items[0];
    expect(placeQuestion(item, view, [], translator("ko"), "ko").question).toContain(SERVER);
    const english = placeQuestion(item, view, [], translator("en"), "en").question;
    expect(english).toContain(ENGLISH);
    expect(english).not.toContain(SERVER);
  });

  it("puts the same sentence on a pin pressed on the map", () => {
    const item = result().items[0];
    expect(stopToast({ order: 1, item }, translator("ko"), () => {}).note).toBe(SERVER);
    expect(stopToast({ order: 1, item }, translator("en"), () => {}).note).toBe(ENGLISH);
  });

  it("leaves any other server line as the server wrote it — nothing is made up", () => {
    h.language = "en";
    const other = [{ kind: "date" as const, result: "bad" as const, text: "날짜를 다시 확인해 주세요" }, { kind: "place" as const, result: "bad" as const, text: SERVER }];
    const html = renderToStaticMarkup(createElement(Checks, { rows: other }));
    expect(html).toContain("날짜를 다시 확인해 주세요");
    expect(html).toContain(SERVER);
    expect(html).not.toContain(ENGLISH);
  });
});
