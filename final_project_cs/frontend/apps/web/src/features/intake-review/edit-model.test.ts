import { describe, expect, it } from "vitest";
import { translator } from "@/lib/i18n";
import type { Candidate, CandidateList, ReviewItem } from "@/lib/live/intake-review";
import { buildCards, chipText, distanceText, indexOfPlace, letterOf, positionText, safePhotoUrl } from "./edit-model";
import { projectPoints } from "./review-model";

const ko = translator("ko");
const en = translator("en");

const item: ReviewItem = { id: "0-1", source_id: "s1", index: 1, title: "올리브영", kind: null, day: 1, date: "2026-10-01", starts_at: "11:00", ends_at: "12:30", locked: false, status: "review",
  can_lock: false, place_state: "picked_nearest", place: { name: "올리브영 인사동점", latitude: 37.5741, longitude: 126.9857, source: "kakao", kind: null, content_id: null },
  candidates_hint: 3, rows: [{ row: "place", result: "warn", text: "임시로 골랐어요" }] };

const cand = (name: string, rank: number, patch: object = {}): Candidate => ({
  rank, place: { name, latitude: 37.57, longitude: 126.98, source: "kakao", kind: null, address: "서울 종로구", category: "화장품", ref: null }, distance_m: 800 + rank * 100,
  reference: "경복궁", rows: [{ row: "hours", result: "ok", text: "09:00–22:00" }], fits: true, status: "ok", slack: { before: 5, after: 5 }, estimated: false, ...patch,
});
const list = (...candidates: Candidate[]): CandidateList => ({ revision: 1, item: "0-1", current: item.place, reference: { before: "경복궁", after: null }, candidates, notes: [] });

describe("the cards of the edit screen", () => {
  it("starts with the stop as it is now, with the lines the server gave it", () => {
    const [current] = buildCards(item, list(), []);
    expect(current).toMatchObject({ kind: "current", status: "review", pickable: false, rows: [{ row: "place", result: "warn" }] });
  });

  it("follows with the server's alternatives in the server's order, each with its own check lines", () => {
    const cards = buildCards(item, list(cand("올리브영 광화문점", 1), cand("올리브영 종각점", 2)), []);
    expect(cards.map((card) => [card.kind, card.place?.name, card.rank])).toEqual([["current", "올리브영 인사동점", null], ["alternative", "올리브영 광화문점", 1], ["alternative", "올리브영 종각점", 2]]);
    expect(cards[1].rows[0].text).toBe("09:00–22:00");
    expect(cards[1].pickable).toBe(true);
  });

  it("puts a place the customer picked from a search right after the current stop", () => {
    const cards = buildCards(item, list(cand("올리브영 광화문점", 1)), [cand("올리브영 명동 플래그십", 9)]);
    expect(cards.map((card) => card.kind)).toEqual(["current", "search", "alternative"]);
  });

  it("does not make a second card for a place that is already one — the stop itself, or an alternative", () => {
    const alt = cand("올리브영 광화문점", 1);
    const cards = buildCards(item, list(alt), [alt, { ...cand("x", 1), place: { ...item.place!, address: null, category: null, ref: null } }]);
    expect(cards).toHaveLength(2);
    expect(indexOfPlace(cards, alt.place)).toBe(1);
    expect(indexOfPlace(cards, { name: "없는 곳", latitude: 1, longitude: 2 })).toBe(-1);
  });

  it("marks an alternative without coordinates as not pickable — the server takes a pick by its coordinates", () => {
    const cards = buildCards(item, list(cand("좌표 없는 곳", 1, { place: { name: "좌표 없는 곳", latitude: null, longitude: null, source: "kakao", kind: null, address: null, category: null, ref: null } })), []);
    expect(cards[1].pickable).toBe(false);
  });

  it("asks for photos only for a place that has a tourism-organization reference", () => {
    const withRef = buildCards(item, list(cand("광장시장", 1, { place: { name: "광장시장", latitude: 37.57, longitude: 126.99, source: "tour_api", kind: null, address: null, category: null, ref: "tour:132183", content_id: "132183" } })), []);
    expect(withRef[1].photoRef).toBe("tour:132183");
    expect(withRef[0].photoRef).toBeNull();
    expect(buildCards({ ...item, place: { ...item.place!, content_id: "126508" } }, list(), [])[0].photoRef).toBe("tour:126508");
  });

  it("keeps the estimate flag so the lines are not read as measured", () => {
    expect(buildCards(item, list(cand("a", 1, { estimated: true })), [])[1].estimated).toBe(true);
  });
});

describe("the words on the cards", () => {
  const cards = buildCards(item, list(cand("광화문점", 1), cand("종각점", 2)), []);
  it("names a card and its place in the row", () => {
    expect(chipText(cards[0], 0, ko)).toBe("지금 일정");
    expect(chipText(cards[1], 1, ko)).toBe("대체 후보 A · 1순위");
    expect(chipText(cards[2], 2, en)).toBe("Alternative B · #2");
    expect(positionText(cards[1], 1, 3, ko)).toBe("대체 후보 A · 2/3");
    expect(positionText(cards[0], 0, 3, en)).toBe("Current stop · 1/3");
    expect(letterOf(0)).toBe("");
    expect(letterOf(3)).toBe("C");
  });

  it("says how far, and from where", () => {
    expect(distanceText({ from: "경복궁", meters: 900 }, ko)).toBe("경복궁에서 0.9km");
    expect(distanceText({ from: "경복궁", meters: 1250 }, en)).toBe("1.3km from 경복궁");
    expect(distanceText({ from: null, meters: 400 }, ko)).toBe("0.4km");
    expect(distanceText(null, ko)).toBe("");
    expect(distanceText({ from: "경복궁", meters: null }, ko)).toBe("");
  });
});

describe("projecting points", () => {
  it("keeps north up and fills the area, for any number of points", () => {
    const spots = projectPoints([{ id: "a", lat: 37.58, lng: 126.97 }, { id: "b", lat: 37.55, lng: 126.99 }, { id: "c", lat: 37.56, lng: 126.98 }]);
    expect(spots.get("a")!.y).toBeLessThan(spots.get("b")!.y);
    for (const { x, y } of spots.values()) { expect(x).toBeGreaterThan(0); expect(x).toBeLessThan(100); expect(y).toBeGreaterThan(0); expect(y).toBeLessThan(100); }
  });

  it("puts one point in the middle and nothing for no points", () => {
    expect(projectPoints([{ id: "a", lat: 37.5, lng: 127 }]).get("a")).toEqual({ x: 50, y: 50 });
    expect(projectPoints([]).size).toBe(0);
  });
});

describe("photo addresses", () => {
  it("accepts only plain web addresses", () => {
    expect(safePhotoUrl("https://tong.visitkorea.or.kr/a.jpg")).toBe("https://tong.visitkorea.or.kr/a.jpg");
    expect(safePhotoUrl("http://tong.visitkorea.or.kr/a.jpg")).toBe("http://tong.visitkorea.or.kr/a.jpg");
    for (const bad of ["javascript:alert(1)", "data:image/svg+xml;base64,AAAA", "file:///etc/passwd", "//tong.visitkorea.or.kr/a.jpg", "not a url", "", null, undefined]) expect(safePhotoUrl(bad)).toBeNull();
  });
});
