import type { NextConfig } from 'next';
const config: NextConfig = { distDir: process.env.NEXT_DIST_DIR || '.next', poweredByHeader: false, devIndicators: false };
export default config;
