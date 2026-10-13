// Controlled request completion with the product hook and installed QueryClient.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '../../..');
const web = path.join(root, 'frontend/apps/web');
const localRequire = createRequire(path.join(web, 'package.json'));
const ts = localRequire('typescript');
const { QueryClient } = localRequire('@tanstack/react-query');
class LiveError extends Error { constructor(code, detail) { super(code); this.code = code; this.detail = detail; } }
const noop = () => {};
const key = ['trip', 'test-trip', 'ko'];
const baseMessage = { id: 'original', role: 'user', text: 'Test travel question', createdAt: '2026-10-12T00:00:00Z' };
const reply = { id: 'reply', role: 'assistant', text: 'Test travel reply', createdAt: '2026-10-12T00:00:01Z' };
const fresh = { id: 'followup', role: 'assistant', text: 'Test followup', createdAt: '2026-10-12T00:00:02Z' };
async function run(file, responseVersion, duplicate) {
  const q = new QueryClient();
  const initial = { id: 'test-trip', version: 1, stops: [{ id: 'initial-stop' }], messages: [baseMessage] };
  q.setQueryData(key, initial);
  let resolveResponse, pending;
  const response = new Promise(resolve => { resolveResponse = resolve; });
  const modules = {
    react: { useEffect: noop, useRef: initial => ({ current: initial }), useState: initial => [initial, noop] },
    '@tanstack/react-query': { useQueryClient: () => q, useMutation: options => {
      const mutation = q.getMutationCache().build(q, options);
      return { isPending: false, mutate: variables => { pending = mutation.execute(variables); } };
    } },
    '@/lib/settings': { useT: () => ko => ko, useSettings: () => ({ language: 'ko' }) },
    '@/lib/gateway': { tripGateway: { sendMessage: () => response } },
    '@/lib/live/client': { LiveError },
    '@/features/consent/consent-store': { useConsent: () => true, readConsents: () => ({ location: true }) },
    './use-trip': { tripKey: () => key },
    './use-trip-extras': { proposalsKey: () => ['proposals'], noticesKey: () => ['notices'] },
  };
  const compiled = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, { exports, require: name => modules[name] || {}, setTimeout, clearTimeout, document: { getElementById: () => null } });
  exports.useTripChat(initial, null, noop).ask('Test travel request');
  await new Promise(resolve => setImmediate(resolve));
  // The independent trip event query has delivered a newer itinerary.
  q.setQueryData(key, { ...initial, version: 3, stops: [{ id: 'updated-stop' }], messages: duplicate ? [baseMessage, reply, fresh] : [baseMessage] });
  resolveResponse({ ...initial, version: responseVersion, stops: [{ id: 'response-stop' }], messages: [baseMessage, reply] });
  await pending;
  const updated = q.getQueryData(key);
  const result = { version: updated.version, stop: updated.stops[0].id, messageIds: updated.messages.map(item => item.id) };
  q.clear();
  return result;
}
(async () => {
  const beforeFile = '_backup/2026-10-12_UIUX정상채팅응답경합_수정전/trip-chat.tsx';
  const afterFile = 'frontend/apps/web/src/features/trip/trip-chat.tsx';
  const cases = [];
  for (const [responseVersion, duplicate] of [[2, false], [2, true], [3, false], [4, false], [undefined, false]]) {
    const before = await run(beforeFile, responseVersion, duplicate);
    const after = await run(afterFile, responseVersion, duplicate);
    const old = responseVersion === 2;
    const expectedIds = old && duplicate ? ['original', 'reply', 'followup'] : ['original', 'reply'];
    const pass = after.version === (old ? 3 : responseVersion) && after.stop === (old ? 'updated-stop' : 'response-stop') && JSON.stringify(after.messageIds) === JSON.stringify(expectedIds);
    cases.push({ responseVersion: responseVersion ?? 'absent', duplicateAlreadyInCache: duplicate, before, after, pass });
  }
  const result = { generatedAt: new Date().toISOString(), browserVerified: false, externalRequests: 0, passed: cases.filter(item => item.pass).length, total: cases.length, cases };
  const output = path.join(__dirname, 'normal-reply-race-results.json');
  if (fs.existsSync(output)) {
    const backup = path.join(__dirname, '_backup', new Date().toISOString().replace(/[:.]/g, '-'));
    fs.mkdirSync(backup, { recursive: true }); fs.copyFileSync(output, path.join(backup, path.basename(output)));
  }
  fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n');
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  if (result.passed !== result.total) process.exitCode = 1;
})().catch(error => { process.stderr.write(String(error) + '\n'); process.exitCode = 1; });
