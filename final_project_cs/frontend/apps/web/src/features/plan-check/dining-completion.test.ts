import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { Checks, kindLabel, needsOf } from "./parts";
import type { CheckRow } from "./model";

describe("missing restaurant checks stay visible and advisory", () => {
  const notice: CheckRow = { kind: "dining_check", result: "unknown", text: "추가 확인을 마치지 못했어요: 할랄" };
  it("has a customer-facing label in both languages", () => {
    expect(kindLabel("dining_check", (ko) => ko)).toBe("식당 확인");
    expect(kindLabel("dining_check", (_, en) => en)).toBe("Restaurant check");
  });
  it("renders the missing-check explanation and does not turn it into a must-fix chip", () => {
    const html = renderToStaticMarkup(createElement(Checks, { rows: [notice] }));
    expect(html).toContain("추가 확인을 마치지 못했어요: 할랄");
    expect(html).toContain('data-result="unknown"');
    expect(needsOf([notice])).toEqual([]);
  });
});
