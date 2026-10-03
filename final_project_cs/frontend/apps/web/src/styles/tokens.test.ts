import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { themeScript, themes } from "@/lib/theme";

const src = join(__dirname, "..");
const tokens = readFileSync(join(__dirname, "tokens.css"), "utf8");

/** The roles a block of `tokens.css` defines, in order. */
function roles(selector: string) {
  const block = tokens.slice(tokens.indexOf(`${selector} {`)).split("}")[0];
  return [...block.matchAll(/(--color-[a-z-]+):/g)].map(([, name]) => name);
}

describe("the two themes (styles/tokens.css)", () => {
  it("define the same colour roles, so a screen looks complete in either", () => {
    const green = roles(':root, [data-theme="green"]');
    expect(green.length).toBeGreaterThan(30);
    expect(roles('[data-theme="neutral"]')).toEqual(green);
  });

  it("are the values the theme setting and the early script know", () => {
    expect(themes).toEqual(["green", "neutral"]);
    expect(themeScript).toContain('s.theme==="neutral"');
  });

  it("leave no colour written into a screen's CSS: every screen follows the chosen theme", () => {
    // The landscape's veil and light belong to the green pictures and are hidden in the white theme.
    const decorative = new Set(["styles/tokens.css", "components/layout/scene.module.css"]);
    const files = readdirSync(src, { recursive: true, encoding: "utf8" }).map((file) => file.replaceAll("\\", "/")).filter((file) => file.endsWith(".css") && !decorative.has(file));
    expect(files.length).toBeGreaterThan(15);
    const found = files.flatMap((file) => readFileSync(join(src, file), "utf8").replace(/\/\*[\s\S]*?\*\//g, "")
      .split("\n").filter((line) => /#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(|\b(white|black)\b(?!-)/i.test(line)).map((line) => `${file}: ${line.trim()}`));
    expect(found).toEqual([]);
  });
});
