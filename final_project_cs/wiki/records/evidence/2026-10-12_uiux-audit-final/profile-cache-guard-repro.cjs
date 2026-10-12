// Executes product UI callbacks with the installed QueryClient and controlled responses.
// No browser, real account, credentials or external requests are used.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '../../..');
const web = path.join(root, 'frontend/apps/web');
const localRequire = createRequire(path.join(web, 'package.json'));
const ts = localRequire('typescript');
const { QueryClient } = localRequire('@tanstack/react-query');
const backup = '_backup/2026-10-12_UIUX계정지연응답_수정전';
const noop = () => {};
const turn = () => new Promise(resolve => setImmediate(resolve));
const jsx = (type, props) => ({ type, props });
const files = {
  webhook: 'src/features/profile/webhook.tsx',
  telegram: 'src/features/profile/telegram.tsx',
  profile: 'src/features/profile/profile.tsx',
  social: 'src/features/account/social-accounts.tsx',
  guardian: 'src/features/guardian/trip-guardian.tsx',
};
const operations = [
  ['webhook', 'test', 0], ['webhook', 'choose', 2],
  ['telegram', 'test', 1], ['telegram', 'release', 2], ['telegram', 'choose', 3],
  ['profile', 'save', null], ['social', 'unlink', 1],
  ['guardian', 'success', 0], ['guardian', 'rollback', 0],
];

function load(file, modules, exposeForm = false) {
  const source = fs.readFileSync(path.join(web, file), 'utf8') + (exposeForm ? '\nexport { ProfileForm };\n' : '');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, {
    exports,
    require: name => modules[name] || (name.endsWith('.css') ? { default: {} } : {}),
    window: { location: { search: '', pathname: '/mypage', assign: noop }, open: noop },
    setTimeout, clearTimeout,
  });
  return exports;
}

async function run(feature, operation, mutationIndex, file, scenario) {
  const q = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const key = feature === 'social' ? ['auth-links', 'ko'] : feature === 'guardian' ? ['trip', 'test-trip', 'ko'] : ['server-profile', 'ko'];
  const value = owner => feature === 'social' ? [{ provider: 'google', owner }] : {
    owner, id: 'test-trip', guardian: { enabled: true, owner },
    webhook: { set: true, masked: owner, status: 'ok' }, telegram: { connected: true },
    discordConnect: true, telegramConnect: true, noticeChannel: feature === 'telegram' ? 'discord' : 'telegram',
  };
  q.setQueryData(key, value('original-account'));
  let resolveResponse, rejectResponse;
  const response = new Promise((resolve, reject) => { resolveResponse = resolve; rejectResponse = reject; });
  const mutations = [];
  let navigation = 0, guardianRemembered = 0, toasts = 0;
  const profileKey = () => ['server-profile', 'ko'];
  const modules = {
    react: { useEffect: noop, useContext: () => noop, useState: initial => [initial, noop] },
    'react/jsx-runtime': { jsx, jsxs: jsx, Fragment: 'fragment' },
    '@tanstack/react-query': {
      useQueryClient: () => q,
      useQuery: () => ({ data: q.getQueryData(key), isPending: false, refetch: noop }),
      useMutation: options => { mutations.push(options); return { isPending: false, reset: noop, mutate: noop }; },
    },
    '@/lib/settings': { useT: () => ko => ko, useSettings: () => ({ language: 'ko' }) },
    '@/lib/data-mode': { DATA_MODE: 'live' },
    '@/features/consent/consent-store': { useConsent: () => true },
    '@/lib/profile': { useProfile: () => ({ session: { kind: 'member' } }), nicknameLabel: () => 'Test account' },
    '@/lib/live/client': { LiveError: class LiveError extends Error {} },
    '@/lib/live/profile': { testDiscordWebhook: () => response, putProfile: () => response },
    '@/lib/live/telegram-connect': { startTelegramConnect: () => response, testTelegram: () => response, disconnectTelegram: () => response },
    './webhook': { serverProfileKey: profileKey, useServerProfile: () => ({ data: q.getQueryData(key), refetch: noop }) },
    '@/lib/live/auth': { unlinkSocial: () => response, providerName: () => ['테스트', 'Test'] },
    './use-auth-providers': { useAuthProviders: () => ({ data: ['google'], isPending: false }) },
    '@/lib/webhook': { saveDiscordWebhook: () => response },
    '@/lib/routes': { routes: { myPage: '/mypage' } },
    '@/features/onboarding/model': { discordWebhookProblem: () => null },
    './model': { checkDraft: () => ({}) },
    'next/navigation': { useRouter: () => ({ push: () => navigation++, replace: noop }), usePathname: () => '/trip/test-trip', useSearchParams: () => new URLSearchParams() },
    '@/features/trip/use-trip': { tripKey: () => key, useTrip: () => ({ data: q.getQueryData(key) }) },
    '@/components/app-toast': { useAppToast: () => ({ show: () => toasts++, node: null }) },
    '@/components/layout/settings-menu': { CloseMenu: {} },
    '@/lib/live/extras': { setGuardian: () => response },
    './criteria-store': { rememberGuardian: () => guardianRemembered++ },
  };
  let pending;
  if (feature === 'profile') {
    let stateIndex = 0;
    // ProfileForm's sixth state is the remove-webhook checkbox: saving null avoids any real URL.
    modules.react.useState = initial => [stateIndex++ === 5 ? true : initial, noop];
    const tree = load(file, modules, true).ProfileForm({ profile: { nickname: null, session: { kind: 'member' } } });
    const children = tree.props.children;
    const bar = children.find(child => child?.props?.onSave);
    if (!bar || !bar.props.canSave) throw new Error('Product profile save was not enabled');
    bar.props.onSave();
  } else {
    const product = load(file, modules);
    if (feature === 'webhook') product.WebhookView({ hasSession: true });
    if (feature === 'telegram') product.TelegramRow({ hasSession: true });
    if (feature === 'social') product.SocialAccounts();
    if (feature === 'guardian') product.useTripGuardian('test-trip');
    const options = mutations[mutationIndex];
    if (!options) throw new Error('Expected product mutation was not registered');
    const mutation = q.getMutationCache().build(q, options);
    const variables = feature === 'guardian' ? { enabled: false, via: 'header' } : feature === 'social' ? 'google' : undefined;
    pending = mutation.execute(variables).catch(() => undefined);
  }
  await turn();
  if (scenario !== 'normal') { await q.cancelQueries(); q.clear(); }
  if (scenario === 'new-session') q.setQueryData(key, value('new-account'));
  if (operation === 'rollback') rejectResponse(new Error('Controlled refusal'));
  else if (feature === 'profile') resolveResponse({ where: 'server', profile: value('old-response') });
  else if (feature === 'webhook' && operation === 'test' || feature === 'telegram' && operation === 'test') resolveResponse({ result: 'ok', profile: value('old-response') });
  else if (feature === 'guardian') resolveResponse({ enabled: false, owner: 'old-response' });
  else resolveResponse(value('old-response'));
  if (pending) await pending;
  await turn();
  const cached = q.getQueryData(key);
  const owner = feature === 'social' ? cached?.[0]?.owner : feature === 'guardian' && operation === 'success' ? cached?.guardian?.owner : cached?.owner;
  const result = { owner: owner ?? 'empty', navigation, guardianRemembered, toasts };
  q.clear();
  return result;
}

(async () => {
  const cases = [];
  for (const [feature, operation, mutationIndex] of operations) for (const scenario of ['normal', 'logout', 'new-session']) {
    const before = await run(feature, operation, mutationIndex, path.join(backup, files[feature]), scenario);
    const after = await run(feature, operation, mutationIndex, files[feature], scenario);
    const expected = scenario === 'normal' ? operation === 'rollback' ? 'original-account' : 'old-response' : scenario === 'logout' ? 'empty' : 'new-account';
    cases.push({ feature, operation, scenario, before, after, expected, pass: after.owner === expected && (scenario === 'normal' || after.navigation === 0 && after.guardianRemembered === 0 && after.toasts === 0) });
  }
  const result = { generatedAt: new Date().toISOString(), browserVerified: false, externalRequests: 0, passed: cases.filter(x => x.pass).length, total: cases.length, cases };
  const output = path.join(__dirname, 'profile-cache-guard-results.json');
  if (fs.existsSync(output)) { const dir = path.join(__dirname, '_backup', new Date().toISOString().replace(/[:.]/g, '-')); fs.mkdirSync(dir, { recursive: true }); fs.copyFileSync(output, path.join(dir, path.basename(output))); }
  fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n');
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  if (result.passed !== result.total) process.exitCode = 1;
})().catch(error => { process.stderr.write(String(error.stack || error) + '\n'); process.exitCode = 1; });
