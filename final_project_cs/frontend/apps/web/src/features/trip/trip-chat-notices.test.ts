import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Proposal } from "@/lib/live/extras";
import type { Trip } from "./model";

const state = vi.hoisted(() => ({ proposals: [] as Proposal[], mutate: vi.fn(), refetch: vi.fn(), invalidate: vi.fn() }));
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: state.invalidate }),
  useMutation: () => ({ mutate: state.mutate, isPending: false, data: null, error: null }),
}));
vi.mock("@/lib/settings", () => ({ useSettings: () => ({ language: "ko" }), useT: () => (ko: string) => ko }));
vi.mock("./use-trip-extras", () => ({
  useProposals: () => ({ data: state.proposals, error: null, refetch: state.refetch }),
  noticesKey: () => ["notices"], proposalsKey: () => ["proposals"],
}));
vi.mock("./use-trip", () => ({ tripKey: () => ["trip"] }));
import { ChatProposalChoices } from "./trip-chat-notices";

const proposal = (id: string, over: Partial<Proposal> = {}): Proposal => ({ id, itemId: "festival", baseVersion: 2,
  reason: "ask_first", status: "open", safety: true, expiresAt: null,
  options: [{ key: "indoor", rank: 1, name: `${id} 실내 전시관`, startsAt: null, note: null, warnings: [] }], ...over });
const trip = { id: "synthetic-trip", version: 2, stops: [{ id: "festival", title: "합성 여행 활동" }] } as Trip;
const render = (value: Trip = trip) => renderToStaticMarkup(createElement(ChatProposalChoices, { trip: value, notices: [] }));
const previous = (html: string) => html.match(/<details[^>]*data-chat-unavailable[^>]*>[\s\S]*?<\/details>/)?.[0] ?? "";

beforeEach(() => { state.proposals = []; vi.clearAllMocks(); });

describe("채팅의 현재 대안 첫 노출", () => {
  it("현재 제안 뒤에 만료·구버전 제안이 와도 접힌 이전 대안을 먼저 두고 현재 선택을 마지막에 둔다", () => {
    state.proposals = [proposal("current"), proposal("expired", { expiresAt: "2020-01-01T00:00:00Z" }), proposal("stale", { baseVersion: 1 })];
    const html = render(), history = previous(html);
    expect(history).toContain("이전 대안 2개 보기");
    expect(history).not.toMatch(/<details[^>]*\sopen(?:[\s=>])/);
    expect(history).toContain('data-chat-proposal="expired"');
    expect(history).toContain('data-chat-proposal="stale"');
    expect(history).not.toContain('data-chat-proposal="current"');
    expect(html.indexOf('</details>')).toBeLessThan(html.indexOf('data-chat-proposal="current"'));
    expect(html.slice(html.indexOf('</details>'))).toContain("current 실내 전시관");
    expect(history).toMatch(/<button[^>]*disabled=""[^>]*>expired 실내 전시관/);
    expect(state.mutate).not.toHaveBeenCalled();
  });

  it("현재 제안만 있으면 이전 대안의 빈 접기 UI를 만들지 않고 선택을 유지한다", () => {
    state.proposals = [proposal("current")];
    const html = render();
    expect(previous(html)).toBe("");
    expect(html).toContain("current 실내 전시관");
    expect(html).not.toContain('disabled=""');
    expect(html).toContain('min-height:44px');
    expect(state.mutate).not.toHaveBeenCalled();
  });

  it("여행에서 없어진 항목과 미확인 버전 제안은 접힌 이전 대안으로 남기고 선택을 차단한다", () => {
    state.proposals = [proposal("missing", { itemId: "removed" })];
    expect(previous(render())).toContain('data-chat-proposal="missing"');
    state.proposals = [proposal("unknown-version")];
    const history = previous(render({ ...trip, version: undefined }));
    expect(history).toContain('data-chat-proposal="unknown-version"');
    expect(history).toContain('disabled=""');
    expect(state.mutate).not.toHaveBeenCalled();
  });

  it("선택할 수 없는 제안만 있어도 기록을 삭제하지 않고 접어서 이유를 보존한다", () => {
    state.proposals = [proposal("invalid-expiry", { expiresAt: "invalid" })];
    const html = render(), history = previous(html);
    expect(history).toContain('data-chat-proposal="invalid-expiry"');
    expect(history).toContain("유효 시간이 지났어요");
    expect(html.slice(html.indexOf('</details>'))).not.toContain('data-chat-proposal=');
    expect(state.mutate).not.toHaveBeenCalled();
  });

  it("이미 처리한 제안은 접힌 기록에도 새 선택 버튼으로 되살리지 않는다", () => {
    state.proposals = [proposal("decided", { status: "adjusted" }), proposal("current")];
    const html = render();
    expect(html).not.toContain("decided 실내 전시관");
    expect(html).toContain("current 실내 전시관");
    expect(state.mutate).not.toHaveBeenCalled();
  });
});
