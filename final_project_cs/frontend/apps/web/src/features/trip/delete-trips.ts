import type { QueryClient } from "@tanstack/react-query";
import { tripKeyPrefix, tripsKey } from "../../lib/gateway";

/**
 * Deletes the given trips one by one and says which went, from each delete's own result. A deleted trip leaves the
 * cache in every language and `forget` drops any other reference to it; the list is then read again.
 */
export async function deleteTrips(ids: readonly string[], remove: (id: string) => Promise<void>, queryClient: QueryClient, forget: (deleted: string[]) => void) {
  const settled = await Promise.allSettled(ids.map((id) => remove(id)));
  const deleted = ids.filter((_, index) => settled[index].status === "fulfilled");
  for (const id of deleted) queryClient.removeQueries({ queryKey: tripKeyPrefix(id) });
  forget(deleted);
  await queryClient.invalidateQueries({ queryKey: tripsKey });
  return { deleted, failed: ids.filter((id) => !deleted.includes(id)) };
}
