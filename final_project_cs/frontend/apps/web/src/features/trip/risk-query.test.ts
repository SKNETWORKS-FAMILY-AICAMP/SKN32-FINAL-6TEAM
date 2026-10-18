import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { requestRiskRefresh, riskQueryOptions } from "./risk-query";

describe("위험 화면 공유 조회", () => {
  it("첫 진입만 fresh이고 알림 센터·주기 조회는 같은 캐시를 읽는다", async () => {
    const client = new QueryClient();
    const read = vi.fn(async () => ({ tripId: "t1", version: 1, at: null, mode: null, items: [] }));
    const main = riskQueryOptions(client, ["risk", "t1", 1], read);
    await client.fetchQuery(main);
    const center = riskQueryOptions(client, ["risk", "t1", 1], read);
    await client.fetchQuery(center);
    expect(read.mock.calls).toEqual([[true]]);
    await client.fetchQuery({ ...center, staleTime: 0 });
    expect(read.mock.calls).toEqual([[true], [false]]);
    requestRiskRefresh(client, ["risk", "t1", 1]);
    await client.fetchQuery({ ...center, staleTime: 0 });
    expect(read.mock.calls).toEqual([[true], [false], [true]]);
    await client.fetchQuery({ ...main, staleTime: 0 });
    expect(read.mock.calls).toEqual([[true], [false], [true], [false]]);
    expect(center.refetchInterval).toBe(180_000);
    client.clear();
  });
  it("초기 확인 실패 뒤 자동 조회는 다시 외부 갱신을 강제하지 않는다", async () => {
    const client = new QueryClient();
    const read = vi.fn<(fresh: boolean) => Promise<never>>().mockRejectedValue(new Error("unavailable"));
    await expect(client.fetchQuery(riskQueryOptions(client, ["risk", "t1"], read))).rejects.toThrow();
    await expect(client.fetchQuery(riskQueryOptions(client, ["risk", "t1"], read))).rejects.toThrow();
    expect(read.mock.calls).toEqual([[true], [false]]);
    client.clear();
  });
  it("여행 판이 바뀌면 새 판을 한 번 확인한다", async () => {
    const client = new QueryClient();
    const read = vi.fn(async () => ({ tripId: "t1", version: 2, at: null, mode: null, items: [] }));
    await client.fetchQuery(riskQueryOptions(client, ["risk", "t1", 1], read));
    await client.fetchQuery(riskQueryOptions(client, ["risk", "t1", 2], read));
    expect(read.mock.calls).toEqual([[true], [true]]);
    client.clear();
  });
});
