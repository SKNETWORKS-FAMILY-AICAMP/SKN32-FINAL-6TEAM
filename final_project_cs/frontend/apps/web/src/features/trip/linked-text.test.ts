import { describe, expect, it } from "vitest";
import { splitLinks } from "./linked-text";

describe("links inside a chat answer", () => {
  it("makes a Google Maps link a short map link and keeps the text around it", () => {
    const url = "https://www.google.com/maps/search/?api=1&query=%EA%B2%BD%EB%B3%B5%EA%B6%81";
    expect(splitLinks(`경복궁 주소는 사직로 161이에요.\n지도에서 보기: ${url}.`)).toEqual([
      { kind: "text", text: "경복궁 주소는 사직로 161이에요.\n지도에서 보기: " },
      { kind: "link", url, map: true },
      { kind: "text", text: "." },
    ]);
  });

  it("leaves plain text alone and never links anything that is not https", () => {
    expect(splitLinks("주소: 사직로 161")).toEqual([{ kind: "text", text: "주소: 사직로 161" }]);
    expect(splitLinks("http://example.com javascript:alert(1)")).toEqual([{ kind: "text", text: "http://example.com javascript:alert(1)" }]);
  });
});
