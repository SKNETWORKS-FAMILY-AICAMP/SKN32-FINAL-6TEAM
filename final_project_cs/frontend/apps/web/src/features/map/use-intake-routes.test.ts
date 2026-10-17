import { QueryClient } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { getIntakeRouteShapes } from "@/lib/live/route-shapes";
import { intakeRouteQuery } from "./use-intake-routes";

vi.mock("@/lib/live/route-shapes", () => ({ getIntakeRouteShapes: vi.fn() }));

it("접수 경로 조회 실패를 빈 성공으로 숨기지 않고 같은 판에서 재시도한다", async () => {
  const client = new QueryClient();
  const query = intakeRouteQuery("example", 3, "ko", true);
  vi.mocked(getIntakeRouteShapes).mockRejectedValueOnce(new Error("network"));
  await expect(client.fetchQuery(query)).rejects.toThrow("network");
  expect(client.getQueryState(query.queryKey)?.status).toBe("error");
  vi.mocked(getIntakeRouteShapes).mockResolvedValueOnce({ shapes: [], attribution: "OSM" });
  await expect(client.fetchQuery(query)).resolves.toEqual({ shapes: [], attribution: "OSM" });
  client.clear();
});
it("검증 판이 바뀌면 이전 경로 캐시를 재사용하지 않는다", () => {
  expect(intakeRouteQuery("example", 3, "ko", true).queryKey).not.toEqual(intakeRouteQuery("example", 4, "ko", true).queryKey);
  expect(intakeRouteQuery("", 3, "ko", true).enabled).toBe(false);
});
