// Builds the web app in live mode against the test mock server (not the real server) and serves it, for the live end-to-end tests.
// A separate build folder keeps this out of the way of a running dev server (`.next`).
//
// The map: the free OpenStreetMap, drawn by the real map code with its tiles served by the test mock server (`/__test/tile/…`, a one-pixel
// image), so no test reaches OpenStreetMap. `MAP_TEST_PROVIDER=naver|google` builds with that provider instead, for `maps.spec.ts` (SDK contract doubles).
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";

const provider = process.env.MAP_TEST_PROVIDER === "naver" || process.env.MAP_TEST_PROVIDER === "google" ? process.env.MAP_TEST_PROVIDER : "osm";

const env = {
  ...process.env,
  NEXT_PUBLIC_DATA_MODE: "live",
  NEXT_PUBLIC_API_BASE: `http://127.0.0.1:${process.env.STUB_PORT ?? 8043}`,
  NEXT_PUBLIC_MAP_PROVIDER: provider,
  NEXT_PUBLIC_OSM_TILE_URL: `http://127.0.0.1:${process.env.STUB_PORT ?? 8043}/__test/tile/{z}/{x}/{y}.png`,
  // Test keys only: the SDK doubles answer for them and nothing leaves the machine.
  NEXT_PUBLIC_NAVER_MAP_CLIENT_ID: provider === "naver" ? "test-naver-key" : "",
  NEXT_PUBLIC_GOOGLE_MAP_API_KEY: provider === "google" ? "test-google-key" : "",
  NEXT_PUBLIC_GOOGLE_MAP_ID: provider === "google" ? "test-google-map" : "",
  // The human check calls Cloudflare; these tests stay on the test mock server, so it is off here (a dev .env.local may set it).
  NEXT_PUBLIC_TURNSTILE_SITE_KEY: "",
  NEXT_DIST_DIR: ".next-live",
};
const shell = process.platform === "win32";

// LIVE_SKIP_BUILD=1 reuses the build already in `.next-live` (a long run is split in batches so a shared, low-memory machine is not pushed over its limit).
const reuse = process.env.LIVE_SKIP_BUILD === "1" && existsSync(".next-live/BUILD_ID");
if (!reuse) {
  const build = spawnSync("npx", ["next", "build"], { env, stdio: "inherit", shell });
  if (build.status !== 0) process.exit(build.status ?? 1);
}

const port = process.env.LIVE_PORT ?? "3102";
const server = spawn("npx", ["next", "start", "--hostname", "127.0.0.1", "--port", port], { env, stdio: "inherit", shell });
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => { server.kill(); process.exit(0); });
server.on("exit", (code) => process.exit(code ?? 0));
