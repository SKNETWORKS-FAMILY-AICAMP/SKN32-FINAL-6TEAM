import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { tooltipContent } from "./osm";

describe("OSM route tooltip content", () => {
  it("keeps HTML in a place name as literal text without writing innerHTML", () => {
    const title = '<img src="x" onerror="1">경복궁 → 광장시장 · 도보 1.8km';
    const node = { textContent: "", innerHTML: "" };
    const doc = { createElement: () => node } as unknown as Pick<Document, "createElement">;

    expect(tooltipContent(doc, title)).toBe(node);
    expect(node.textContent).toBe(title);
    expect(node.innerHTML).toBe("");
  });

  it("passes text elements to both Leaflet tooltip bindings", () => {
    const source = readFileSync(new URL("./osm.ts", import.meta.url), "utf8");
    const bindings = source.match(/\.bindTooltip\s*\(/g) ?? [];
    const textBindings = source.match(/\.bindTooltip\(tooltipContent\(/g) ?? [];

    expect(bindings).toHaveLength(2);
    expect(textBindings).toHaveLength(bindings.length);
  });
});
