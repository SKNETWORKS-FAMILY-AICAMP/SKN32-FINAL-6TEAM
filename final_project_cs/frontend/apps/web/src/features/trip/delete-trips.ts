import type { QueryClient } from "@tanstack/react-query";
import { tripKeyPrefix, tripsKey } from "../../lib/gateway";

/**
 * Deletes the given trips and says which went, from each delete's own result — and why the others did not (`errors`,
 * by trip id). A deleted trip leaves the cache in every language; the list is then read again.
 */
export async function deleteTrips(ids: readonly string[], remove: (id: string) => Promise<void>, queryClient: QueryClient) {
  const settled = await Promise.allSettled(ids.map((id) => remove(id)));
  const deleted = ids.filter((_, index) => settled[index].status === "fulfilled");
  for (const id of deleted) queryClient.removeQueries({ queryKey: tripKeyPrefix(id) });
  await queryClient.invalidateQueries({ queryKey: tripsKey });
  const errors = new Map(ids.flatMap((id, index) => { const result = settled[index]; return result.status === "rejected" ? [[id, result.reason] as const] : []; }));
  return { deleted, failed: ids.filter((id) => !deleted.includes(id)), errors };
}
