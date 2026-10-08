import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { tripKey, tripsKey } from "../../lib/gateway";
import { deleteTrips } from "./delete-trips";

const languages = ["ko", "en"] as const;

/** A client holding trips a, b and c in both languages, and the list in both languages. */
function cached() {
  const client = new QueryClient();
  for (const language of languages) {
    for (const id of ["a", "b", "c"]) client.setQueryData(tripKey(id, language), { id });
    client.setQueryData([...tripsKey, language], [{ id: "a" }, { id: "b" }, { id: "c" }]);
  }
  return client;
}

describe("deleting trips", () => {
  it("takes each delete's own result, drops only what went — in every language — and marks the list to be read again", async () => {
    const client = cached();
    const result = await deleteTrips(["a", "b"], async (id) => { if (id === "b") throw new Error("denied"); }, client);
    expect(result).toMatchObject({ deleted: ["a"], failed: ["b"] });
    expect(result.errors.get("b")).toEqual(new Error("denied"));            // the reason comes back with the failure
    expect(result.errors.has("a")).toBe(false);
    for (const language of languages) {
      expect(client.getQueryData(tripKey("a", language))).toBeUndefined();
      expect(client.getQueryData(tripKey("b", language))).toEqual({ id: "b" });
      expect(client.getQueryData(tripKey("c", language))).toEqual({ id: "c" });
      expect(client.getQueryState([...tripsKey, language])?.isInvalidated).toBe(true);
    }
  });

  it("when every delete fails, keeps every cached trip", async () => {
    const client = cached();
    const result = await deleteTrips(["a", "c"], async () => { throw new Error("denied"); }, client);
    expect(result).toMatchObject({ deleted: [], failed: ["a", "c"] });
    for (const language of languages) for (const id of ["a", "b", "c"]) expect(client.getQueryData(tripKey(id, language))).toEqual({ id });
  });
});
