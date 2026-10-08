import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A separate build folder for the live end-to-end tests (`npm run test:live`), so they never touch a running dev server's `.next`.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  reactStrictMode: true,
  poweredByHeader: false,
  agentRules: false,
  devIndicators: false,
  // Phones on the same router open the dev server by this PC's LAN address (`scripts/ops/lan_serve.ps1` sets it). Unset = same-machine only, as before.
  allowedDevOrigins: process.env.NEXT_ALLOWED_DEV_ORIGINS?.split(",").map((host) => host.trim()).filter(Boolean),
};

export default nextConfig;
