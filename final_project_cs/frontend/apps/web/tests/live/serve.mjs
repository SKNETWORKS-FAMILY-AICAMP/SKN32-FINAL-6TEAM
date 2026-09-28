// Builds the web app in live mode against the stand-in server and serves it, for the live end-to-end tests.
// A separate build folder keeps this out of the way of a running dev server (`.next`).
import { spawn, spawnSync } from "node:child_process";

const env = {
  ...process.env,
  NEXT_PUBLIC_DATA_MODE: "live",
  NEXT_PUBLIC_API_BASE: `http://127.0.0.1:${process.env.STUB_PORT ?? 8043}`,
  NEXT_PUBLIC_MAP_PROVIDER: "demo",
  NEXT_PUBLIC_GOOGLE_MAP_API_KEY: "",
  NEXT_PUBLIC_GOOGLE_MAP_ID: "",
  // The human check calls Cloudflare; these tests stay on the stand-in server, so it is off here (a dev .env.local may set it).
  NEXT_PUBLIC_TURNSTILE_SITE_KEY: "",
  NEXT_DIST_DIR: ".next-live",
};
const shell = process.platform === "win32";

const build = spawnSync("npx", ["next", "build"], { env, stdio: "inherit", shell });
if (build.status !== 0) process.exit(build.status ?? 1);

const port = process.env.LIVE_PORT ?? "3102";
const server = spawn("npx", ["next", "start", "--hostname", "127.0.0.1", "--port", port], { env, stdio: "inherit", shell });
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => { server.kill(); process.exit(0); });
server.on("exit", (code) => process.exit(code ?? 0));
