import { describe, expect, it } from "vitest";
import { translator } from "@/lib/i18n";
import { assertPlaceSearchComplete } from "./place-search-status";

const t = translator("ko");

describe("explicit place search status", () => {
  it.each(["kakao:timeout", "kakao:unavailable", "kakao:http_500"])("does not call %s an absent shop", (note) => {
    expect(() => assertPlaceSearchComplete({ results: [], notes: [note] }, t)).toThrow("가게가 없다는 뜻은 아니에요");
  });
  it.each(["kakao:budget_exhausted", "kakao:http_429"])("states %s as a lookup limit", (note) => {
    expect(() => assertPlaceSearchComplete({ results: [], notes: [note] }, t)).toThrow("검색 한도");
  });
  it("explains a kind exclusion without claiming no match", () => {
    expect(() => assertPlaceSearchComplete({ results: [], notes: ["no_same_kind"] }, t)).toThrow("종류를 이 일정에 사용할 수 없어");
  });
  it.each(["area_unverified", "area_mismatch"])("explains %s as an area restriction", (note) => {
    expect(() => assertPlaceSearchComplete({ results: [], notes: [note] }, t)).toThrow("요청한 지역");
  });
  it("keeps real results from another source when the map fails", () => {
    expect(() => assertPlaceSearchComplete({ results: [{}], notes: ["kakao:timeout"] }, t)).not.toThrow();
  });
  it("leaves a completed empty search as an empty search", () => {
    expect(() => assertPlaceSearchComplete({ results: [], notes: [] }, t)).not.toThrow();
  });
});
