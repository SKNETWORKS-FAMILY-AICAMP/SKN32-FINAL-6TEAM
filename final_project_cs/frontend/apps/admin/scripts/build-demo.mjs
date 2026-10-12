import { spawnSync } from 'node:child_process';
const result = spawnSync(process.execPath, ['node_modules/next/dist/bin/next', 'build'], { stdio: 'inherit', env: { ...process.env, NEXT_PUBLIC_ADMIN_DATA_MODE: 'demo' } });
process.exit(result.status ?? 1);
