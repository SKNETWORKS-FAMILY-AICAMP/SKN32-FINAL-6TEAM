// Runs the product TSX with its installed QueryClient and controlled responses.
// No browser, credentials, personal data or external requests are used.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '../../..');
const web = path.join(root, 'frontend/apps/web');
const localRequire = createRequire(path.join(web, 'package.json'));
const ts = localRequire('typescript');
const { QueryClient } = localRequire('@tanstack/react-query');
const noop = () => {};
const turn = () => new Promise(resolve => setImmediate(resolve));
const fixtures = {
  chat: {
    before: '_backup/2026-10-12_UIUX로그아웃지연채팅_수정전/trip-chat.tsx',
    after: 'src/features/trip/trip-chat.tsx',
  },
  support: {
    before: '_backup/2026-10-12_UIUX로그아웃지연문의_수정전/support.tsx',
    after: 'src/features/support/support.tsx',
  },
};

function load(file, modules) {
  const output = ts.transpileModule(fs.readFileSync(path.join(web, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const exports = {};
  vm.runInNewContext(output, {
    exports, require: name => modules[name] || (name.endsWith('.css') ? { default: {} } : {}), setTimeout, clearTimeout,
    document: { getElementById: () => null },
  });
  return exports;
}

async function run(feature, file, scenario) {
  const q = new QueryClient();
  const key = feature === 'chat' ? ['trip', 'test-trip', 'ko'] : ['support-inquiries', 'ko'];
  const value = owner => feature === 'chat' ? { id: 'test-trip', owner } : {
    inquiries: [{ id: owner, title: 'Test travel inquiry', body: 'Test only', replies: [], receivedAt: '2026-10-12T00:00:00Z', status: '접수' }],
  };
  q.setQueryData(key, value('original-account'));
  let finish;
  const response = new Promise(resolve => { finish = resolve; });
  const modules = {
    react: { useEffect: noop, useRef: initial => ({ current: initial }), useState: initial => [initial, noop] },
    '@/lib/settings': { useT: () => ko => ko, useSettings: () => ({ language: 'ko' }) },
    '@tanstack/react-query': { useQueryClient: () => q },
  };
  let pending;
  if (feature === 'chat') {
    modules['@tanstack/react-query'].useMutation = options => {
      const mutation = q.getMutationCache().build(q, options);
      return { isPending: false, mutate: variables => { pending = mutation.execute(variables); } };
    };
    modules['@/lib/gateway'] = { tripGateway: { sendMessage: () => response } };
    modules['@/features/consent/consent-store'] = { useConsent: () => true, readConsents: () => ({ location: true }) };
    modules['./use-trip'] = { tripKey: () => key };
    modules['./use-trip-extras'] = { proposalsKey: () => ['proposals'], noticesKey: () => ['notices'] };
    load(file, modules).useTripChat({ id: 'test-trip', stops: [], messages: [] }, null, noop).ask('test travel question');
  } else {
    let stateIndex = 0;
    modules.react.useState = initial => [[ 'test subject', 'test travel inquiry' ][stateIndex++] ?? initial, noop];
    modules['@tanstack/react-query'].useQuery = () => ({ data: q.getQueryData(key), isPending: false, isFetching: false });
    modules['./client'] = {
      createInquiry: () => response,
      requestIdentity: () => ({ fingerprint: 'test-inquiry', requestId: 'test-request' }),
    };
    modules['react/jsx-runtime'] = { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) };
    const tree = load(file, modules).SupportPage();
    function findForm(node) {
      if (!node || typeof node !== 'object') return null;
      if (node.type === 'form') return node;
      for (const child of [node.props?.children].flat(Infinity)) {
        const found = findForm(child);
        if (found) return found;
      }
      return null;
    }
    const form = findForm(tree);
    if (!form) throw new Error('Product inquiry form was not rendered');
    form.props.onSubmit({ preventDefault: noop });
  }
  await turn();
  if (scenario !== 'normal') { await q.cancelQueries(); q.clear(); }
  if (scenario === 'new-session') q.setQueryData(key, value('new-account'));
  finish(feature === 'chat' ? value('old-response') : { inquiry: { id: 'old-response' } });
  if (pending) await pending;
  await turn();
  const cached = q.getQueryData(key);
  const owner = feature === 'chat' ? cached?.owner : cached?.inquiries[0]?.id;
  q.clear();
  return owner ?? 'empty';
}

(async () => {
  const cases = [];
  for (const feature of ['chat', 'support']) {
    for (const scenario of ['normal', 'logout', 'new-session']) {
      const before = await run(feature, fixtures[feature].before, scenario);
      const after = await run(feature, fixtures[feature].after, scenario);
      const expected = scenario === 'normal' ? 'old-response' : scenario === 'logout' ? 'empty' : 'new-account';
      cases.push({ feature, scenario, before, after, expected, pass: after === expected });
    }
  }
  const result = {
    generatedAt: new Date().toISOString(),
    method: 'Product TSX transpiled and executed with installed QueryClient; controlled UI hooks and request completion',
    browserVerified: false, externalRequests: 0,
    passed: cases.filter(item => item.pass).length, total: cases.length, cases,
  };
  const output = path.join(__dirname, 'account-cache-guard-results.json');
  if (fs.existsSync(output)) {
    const backup = path.join(__dirname, '_backup', new Date().toISOString().replace(/[:.]/g, '-'));
    fs.mkdirSync(backup, { recursive: true });
    fs.copyFileSync(output, path.join(backup, path.basename(output)));
  }
  fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n');
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  if (result.passed !== result.total) process.exitCode = 1;
})().catch(error => { process.stderr.write(String(error) + '\n'); process.exitCode = 1; });
