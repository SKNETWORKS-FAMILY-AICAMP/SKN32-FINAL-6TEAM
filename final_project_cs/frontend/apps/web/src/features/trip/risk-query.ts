import type { QueryClient, QueryKey } from "@tanstack/react-query";
import type { TripRisks } from "@/lib/live/risks";

const manualRefreshes = new WeakMap<QueryClient, Set<string>>();

/** A manual request belongs to the shared query, whichever panel owns its next fetch. */
export function requestRiskRefresh(client: QueryClient, key: QueryKey): void {
  let pending = manualRefreshes.get(client);
  if (!pending) { pending = new Set(); manualRefreshes.set(client, pending); }
  pending.add(JSON.stringify(key));
}

/** Both risk panels share query history, including failures, so a new observer does not spend another refresh. */
export function riskQueryOptions(client: QueryClient, key: QueryKey, read: (fresh: boolean) => Promise<TripRisks>) {
  return { queryKey: key, retry: false as const, staleTime: 30_000, refetchInterval: 180_000, refetchOnWindowFocus: true,
    queryFn: () => {
      const state = client.getQueryState(key);
      const manual = manualRefreshes.get(client)?.delete(JSON.stringify(key)) ?? false;
      const fresh = manual || !state?.dataUpdatedAt && !state?.errorUpdatedAt;
      return read(fresh);
    } };
}
