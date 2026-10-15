import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { translator } from "@/lib/i18n";
import { DiningCards, DiningProposal } from "./cards";
import type { DiningLink, DiningPreview } from "@/lib/live/social-dining";

const link: DiningLink = { key: "yt:one", platform: "youtube", source_urls: ["https://youtu.be/one", "javascript:alert(1)"], status: "needs_choice", reason: "restaurant_choice_required", priority: "must", checked_at: "2026-10-15T01:00:00Z",
  restaurants: [{ name: "성수 국수", evidence: [{ source: "metadata", quote: "성수 국수 방문", source_url: "https://youtu.be/one", checked_at: "2026-10-15T01:00:00Z" }] }, { name: "종로 찌개", evidence: [{ source: "customer_note", quote: "종로 찌개 추천" }] }], choices: [{ ref: "kakao:1", name: "성수 국수 본점", address: "서울 성동구", latitude: 37.5, longitude: 127 }] };
describe("restaurant link cards", () => {
  it("shows multiple extracted restaurants, actual branch choices and provenance without claiming they were applied", () => {
    const html = renderToStaticMarkup(createElement(DiningCards, { links: [link], busy: false, t: translator("ko"), onUpdate: async () => true }));
    expect(html).toContain("성수 국수");
    expect(html).toContain("종로 찌개");
    expect(html).toContain("성수 국수 본점");
    expect(html).toContain("서울 성동구");
    expect(html).toContain("https://youtu.be/one");
    expect(html).not.toContain('href="javascript:');
    expect(html).toContain("2026-10-15T01:00:00Z");
    expect(html).toContain("일정에는 아직 넣지 않았어요");
    expect(html).toContain("꼭 가고 싶어요");
  });
  it("retains an inaccessible link and offers name/area supplementation", () => {
    const html = renderToStaticMarkup(createElement(DiningCards, { links: [{ ...link, status: "inaccessible", reason: null, restaurants: [], choices: [] }], busy: false, t: translator("en"), onUpdate: async () => true }));
    expect(html).toContain("Could not open the post");
    expect(html).toContain("Restaurant name");
    expect(html).toContain("Area or branch");
    expect(html).toContain("https://youtu.be/one");
  });
  it("shows unplaced must-go restaurants and a separate explicit apply control", () => {
    const proposal: DiningPreview = { revision: 3, proposal_id: "p1", links: [link], changes: [{ key: link.key, item_id: "0-1", from: { name: "기존 점심" }, to: { name: "성수 국수 본점" }, reason: "fits" }], unplaced: [{ key: "yt:two", name: "종로 찌개", priority: "must", reason: "does_not_fit" }] };
    const html = renderToStaticMarkup(createElement(DiningProposal, { proposal, busy: false, t: translator("ko"), onApply: () => undefined }));
    expect(html).toContain("기존 점심");
    expect(html).toContain("성수 국수 본점");
    expect(html).toContain("꼭 가기 미충족");
    expect(html).toContain("종로 찌개");
    expect(html).toContain("이 변경안 적용");
  });
  it("localizes a dietary omission when the server includes a Korean explanation", () => {
    const proposal: DiningPreview = { revision: 3, proposal_id: "p1", links: [link], changes: [], unplaced: [{ key: link.key, name: "성수 국수", priority: "must", reason: "unknown_dietary", message: "요청 식이 조건 근거 미확인" }] };
    const html = renderToStaticMarkup(createElement(DiningProposal, { proposal, busy: false, t: translator("en"), onApply: () => undefined }));
    expect(html).toContain("dietary requirements");
    expect(html).not.toContain("요청 식이 조건 근거 미확인");
  });
  it("reveals partial placement information without exposing prompt audit fields", () => {
    const proposal: DiningPreview = { revision: 3, proposal_id: "p1", links: [link], changes: [], unplaced: [], planning: { mode: "partial", reason: "missing_ranking", messages: ["일부 후보의 배치를 확인하지 못했어요."], omissions: [{ key: link.key, reason: "missing_ranking" }], prompt_version: "private-version", prompt_hash: "private-hash" } };
    const html = renderToStaticMarkup(createElement(DiningProposal, { proposal, busy: false, t: translator("ko"), onApply: () => undefined }));
    expect(html).toContain("일부 후보의 배치를 확인하지 못했어요.");
    expect(html).not.toContain("private-version");
    expect(html).not.toContain("private-hash");
  });
  it("says the same reason once when the link and its placement were stopped for the same reason", () => {
    // [2026-10-15 브라우저 실측] 「같은 이름의 장소가 있어요」가 한 카드에 두 번 나왔다(링크 사유 · 배치 사유가 같다).
    const same: DiningLink = { ...link, status: "needs_choice", reason: "place_choice_required", placement_status: "unplaced", placement_reason: "place_choice_required" };
    const html = renderToStaticMarkup(createElement(DiningCards, { links: [same], busy: false, t: translator("ko"), onUpdate: async () => true }));
    expect(html.split("같은 이름의 장소가 있어요").length - 1).toBe(1);
    expect(html).toContain("일정에는 아직 넣지 않았어요");
  });
  it("does not call a must-go restaurant unmet when it is already on the itinerary", () => {
    // [2026-10-15 브라우저 실측] 점심에 이미 넣은 우래옥이 다음 반영안에서 「꼭 가기 미충족」으로 보였다.
    const proposal: DiningPreview = { revision: 4, proposal_id: null as unknown as string, links: [link], changes: [], unplaced: [{ key: link.key, name: "우래옥", priority: "must", reason: "already_scheduled", message: "같은 식당이 이미 일정에 들어 있어 중복으로 넣지 않았어요." }] };
    const html = renderToStaticMarkup(createElement(DiningProposal, { proposal, busy: false, t: translator("ko"), onApply: () => undefined }));
    expect(html).not.toContain("꼭 가기 미충족");
    expect(html).toContain("이미 일정에 들어 있어");
  });
  it("shows a verified quoted span and accepts menus returned as text or a list", () => {
    for (const menu of ["칼국수", ["칼국수", "만두"]]) {
      const html = renderToStaticMarkup(createElement(DiningCards, { links: [{ ...link, restaurants: [{ ...link.restaurants[0], menu }] }], busy: false, t: translator("ko"), onUpdate: async () => true }));
      expect(html).toContain("성수 국수 방문");
      expect(html).toContain("칼국수");
    }
  });
});
