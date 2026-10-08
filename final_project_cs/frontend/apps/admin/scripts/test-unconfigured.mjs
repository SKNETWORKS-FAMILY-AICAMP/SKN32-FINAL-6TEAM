import { spawnSync } from 'node:child_process';
const env = { ...process.env, NEXT_DIST_DIR: '.next-unconfigured', NEXT_PUBLIC_ADMIN_DATA_MODE: '' };
let result = spawnSync(process.execPath, ['node_modules/next/dist/bin/next', 'build'], { env, stdio: 'inherit' });
if (result.status !== 0) process.exit(result.status ?? 1);
result = spawnSync(process.execPath, ['node_modules/@playwright/test/cli.js', 'test', '--config', 'playwright.unconfigured.config.ts'], { env, stdio: 'inherit' });
process.exit(result.status ?? 1);
