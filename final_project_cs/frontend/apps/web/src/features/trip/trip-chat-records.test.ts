import { describe, expect, it } from "vitest";
import type { Notice, Proposal } from "@/lib/live/extras";
import type { TripMessage } from "./model";
import { chatRecords, proposalAvailable } from "./trip-chat-records";

const notice = (key: string, at: string): Notice => ({ key, at, type: "safety_alert", kind: null,
  text: "공식 도로 통제 원문", version: 2, proposalId: null, delivery: "sent", rollback: null, safety: null });
const message = (id: string, at: string): TripMessage => ({ id, createdAt: at, role: "assistant", text: "상담 답변" });
const proposal = (over: Partial<Proposal> = {}): Proposal => ({ id: "p1", itemId: "i1", baseVersion: 2,
  reason: "ask_first", status: "open", safety: true, expiresAt: null,
  options: [{ key: "museum", rank: 1, name: "실내 박물관", startsAt: null, note: null, warnings: [] }], ...over });

describe("여행 알림의 채팅 도달", () => {
  it("실제 알림 원문을 대화 사이의 확인 시각에 놓는다", () => {
    const records = chatRecords([message("m1", "2030-01-01T10:00:00+09:00"), message("m2", "2030-01-01T12:00:00+09:00")],
      [notice("n1", "2030-01-01T11:00:00+09:00")]);
    expect(records.map(row => row.id)).toEqual(["message:m1", "notice:n1", "message:m2"]);
    expect(records[1]).toMatchObject({ kind: "notice", notice: { text: "공식 도로 통제 원문" } });
  });
  it("알림을 섞어도 원래 최신 답변 인덱스를 바꾸지 않는다", () => {
    const records = chatRecords([message("m1", "2030-01-01T10:00:00+09:00")], [notice("n1", "2030-01-01T11:00:00+09:00")]);
    expect(records[0]).toMatchObject({ kind: "message", index: 0 });
    expect(records[1].kind).toBe("notice");
  });
  it("같은 알림의 재조회는 한 번만 표시하고 원본 배열을 바꾸지 않는다", () => {
    const input = [notice("n1", "2030-01-01T11:00:00+09:00")];
    expect(chatRecords([], [...input, ...input])).toHaveLength(1);
    expect(input).toHaveLength(1);
  });
  it("알림 key와 상담 id가 같아도 서로 지우지 않는다", () => {
    expect(chatRecords([message("one", "2030-01-01T10:00:00Z")], [notice("one", "2030-01-01T10:00:00Z")])).toHaveLength(2);
  });
});

describe("채팅의 제안 선택 보호", () => {
  it("열린 현재 버전의 제안만 고를 수 있다", () => expect(proposalAvailable(proposal(), 2)).toBe(true));
  it.each(["adjusted", "kept", "expired"])("%s 제안을 고르지 않는다", status => expect(proposalAvailable(proposal({ status }), 2)).toBe(false));
  it("버전이 다르거나 아직 버전을 모르면 고르지 않는다", () => {
    expect(proposalAvailable(proposal(), 3)).toBe(false);
    expect(proposalAvailable(proposal(), undefined)).toBe(false);
  });
  it("만료됐거나 읽을 수 없는 만료 시각은 거절한다", () => {
    expect(proposalAvailable(proposal({ expiresAt: "2030-01-01T00:00:00Z" }), 2, Date.parse("2030-01-01T00:00:00Z"))).toBe(false);
    expect(proposalAvailable(proposal({ expiresAt: "invalid" }), 2)).toBe(false);
    expect(proposalAvailable(proposal({ expiresAt: "2030-01-02T00:00:00Z" }), 2, Date.parse("2030-01-01T00:00:00Z"))).toBe(true);
  });
});
