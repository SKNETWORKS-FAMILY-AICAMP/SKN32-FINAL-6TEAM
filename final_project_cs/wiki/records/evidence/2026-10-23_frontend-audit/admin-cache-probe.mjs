// Reproduces the reviewed admin QueryClient lifecycle without a browser or server.
// Run: node <this-file>; stdout is JSON evidence. This does not edit app code.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';

const csRoot = new URL('../../../../', import.meta.url);
const require = createRequire(new URL('frontend/apps/web/package.json', csRoot));
const { QueryClient, QueryObserver } = require('@tanstack/query-core');
const { version } = require('@tanstack/query-core/package.json');
const app = readFileSync(new URL('frontend/apps/admin/src/components/AdminApp.tsx', csRoot), 'utf8');
const cases = readFileSync(new URL('frontend/apps/admin/src/features/operations/connected.tsx', csRoot), 'utf8');
assert.ok(app.includes('staleTime: Infinity, refetchOnWindowFocus: false'));
assert.ok(app.includes("client.removeQueries({ queryKey: ['admin'] })"));
assert.ok(cases.includes("queryKey: ['operation-cases', id]"));

const client = new QueryClient({ defaultOptions: {
  queries: { retry: false, staleTime: Infinity, refetchOnWindowFocus: false },
} });
const caseKey = ['operation-cases', 'case-owned-by-authorized-view'];
let operatorAReads = 0;
let operatorBReads = 0;
await client.fetchQuery({ queryKey: ['admin'], queryFn: async () => ({ operator: 'A' }) });
await client.fetchQuery({ queryKey: caseKey, queryFn: async () => {
  operatorAReads += 1;
  return { case_id: caseKey[1], evidence: 'synthetic-private-case-evidence' };
} });
// Matches LiveAdmin.logout() after operatorLogout succeeds.
client.removeQueries({ queryKey: ['admin'] });
const adminRemoved = client.getQueryData(['admin']) === undefined;
const caseRetainedAfterLogout = client.getQueryData(caseKey) !== undefined;
await client.fetchQuery({ queryKey: ['admin'], queryFn: async () => ({ operator: 'B' }) });

// Matches B mounting CaseTrace. If called, its API would reject case:read.
const observer = new QueryObserver(client, { queryKey: caseKey, queryFn: async () => {
  operatorBReads += 1;
  throw new Error('403: case:read permission denied');
} });
const unsubscribe = observer.subscribe(() => {});
await new Promise(resolve => setTimeout(resolve, 20));
const result = observer.getCurrentResult();
assert.equal(adminRemoved, true);
assert.equal(caseRetainedAfterLogout, true);
assert.equal(operatorAReads, 1);
assert.equal(operatorBReads, 0);
assert.equal(result.status, 'success');
assert.equal(result.isStale, false);
assert.equal(result.data?.evidence, 'synthetic-private-case-evidence');

console.log(JSON.stringify({
  checkedAt: new Date().toISOString(),
  library: '@tanstack/query-core', version,
  sourceSettingsVerified: true,
  adminRemoved, caseRetainedAfterLogout, operatorAReads, operatorBReads,
  operatorBObserver: { status: result.status, isStale: result.isStale,
    fetchStatus: result.fetchStatus, data: result.data },
  verdict: 'REPRODUCED: cached Case data survives logout and is displayed without the new operator query executing',
  limitation: 'Query-core lifecycle probe only; no React/browser/backend/network execution; synthetic data only',
}, null, 2));
unsubscribe();
client.clear();
