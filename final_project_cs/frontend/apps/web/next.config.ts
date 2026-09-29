import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A separate build folder for the live end-to-end tests (`npm run test:mock`), so they never touch a running dev server's `.next`.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  reactStrictMode: true,
  poweredByHeader: false,
  agentRules: false,
  devIndicators: false,
};

export default nextConfig;
