import { expect, type Page } from "@playwright/test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { createHash } from "node:crypto";

const cache = resolve("../../../../.tmp/ui-map-tiles/identified-v1");
const blockedTile = resolve("../../../../.tmp/ui-map-tiles/13_6984_3171.png");
const tiles = new Map<string, Promise<Buffer>>();



export async function useMapTiles(page: Page) {
  await mkdir(cache, { recursive: true });
  const pending = new Set<string>();
  const errors: string[] = [];
  await page.route("**/__test/tile/**", async (route) => {
    const suffix = new URL(route.request().url()).pathname.split("/__test/tile/")[1];
    pending.add(suffix);
    let body = tiles.get(suffix);
    if (!body) {
      body = (async () => {
        const path = resolve(cache, suffix.replaceAll("/", "_"));
        try { return await readFile(path); } catch (error) {
          if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
        }
        // 기본 라이브러리 식별자를 쓰지 않고 촬영 앱과 실제 열어 본 페이지를 밝힌다.
        const response = await page.request.get(`https://tile.openstreetmap.org/${suffix}`, {
          timeout: 15_000, headers: { "User-Agent": "triPilot-UI-review/0.1 (local development screenshot)", Referer: page.url() },
        });
        if (!response.ok()) throw new Error(`지도 타일 응답 ${response.status()}`);
        const bytes = await response.body();
        // 일부 타일은 차단 안내 그림도 HTTP 200으로 답한다. 그것을 지도 촬영 성공으로 세지 않는다.
        const blocked = await readFile(blockedTile).catch((error: NodeJS.ErrnoException) => {
          if (error.code === "ENOENT") return null;
          throw error;
        });
        if (blocked && createHash("sha256").update(bytes).digest("hex") === createHash("sha256").update(blocked).digest("hex")) throw new Error("지도 타일에 접근 차단 안내가 표시됩니다");
        await writeFile(path, bytes);
        return bytes;
      })();
      tiles.set(suffix, body);
    }
    try { await route.fulfill({ contentType: "image/png", body: await body }); }
    catch (error) { errors.push(String(error)); await route.abort(); }
    finally { pending.delete(suffix); }
  });
  return async () => {
    await expect.poll(() => pending.size, { timeout: 20_000 }).toBe(0);
    expect(errors).toEqual([]);
    await expect(page.locator(".leaflet-tile-loaded").first()).toBeVisible();
  };
}
