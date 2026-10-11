import { describe, expect, it, vi } from "vitest";
import type { Notice, Proposal } from "@/lib/live/extras";
import { resolveNoticeTarget } from "./notice-target";

describe("새 선택 요청의 대상 조회", () => {
  const notice = { type: "proposal_request", proposalId: "p-1" } as Notice;
  const target = { id: "p-1", itemId: "i-c" } as Proposal;
  it("제안 조회가 시작되기 전의 빈 캐시도 다시 조회하여 실제 대상을 전달한다", async () => {
    let finish!: (value: Proposal[]) => void;
    const reload = vi.fn(() => new Promise<Proposal[]>((resolve) => { finish = resolve; }));
    const delivered = vi.fn();
    const pending = resolveNoticeTarget(notice, [], reload).then(delivered);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(delivered).not.toHaveBeenCalled();
    finish([target]);
    await pending;
    expect(delivered).toHaveBeenCalledExactlyOnceWith([target]);
  });
  it("대상이 이미 있거나 다른 알림이면 추가 조회하지 않는다", async () => {
    const reload = vi.fn();
    expect(await resolveNoticeTarget(notice, [target], reload)).toEqual([target]);
    expect(await resolveNoticeTarget({ type: "plan_changed" } as Notice, [], reload)).toEqual([]);
    expect(reload).not.toHaveBeenCalled();
  });
});
