// Read-only probes of the actual review checkout. No HTTP, server, or source writes.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { stripTypeScriptTypes } = require('node:module');
const root = path.resolve(__dirname, '../../../../../frontend/apps/web/src');
const code = p => fs.readFileSync(path.join(root, p), 'utf8');
function load(source, names, bindings = {}) {
  const js = stripTypeScriptTypes(source).replace(/^import[\s\S]*?from\s+["'][^"']+["'];\s*/gm, '').replace(/\bexport (?=(?:async )?(?:function|const|class))/g, '');
  return vm.runInNewContext(js + '\n;({' + names.join(',') + '})', { setTimeout, clearTimeout, AbortController, Response, ReadableStream, TextDecoderStream, TextEncoder, console, ...bindings });
}
async function main() {
  const output = { timestamp: new Date().toISOString(), sourceRoot: root, probes: [] };
  let fetchImpl;
  const events = load(code('lib/live/events.ts'), ['eventStreamParser', 'watchTrip'], { API_BASE: '', sessionInit: async (_l, init) => init, fetch: (...args) => fetchImpl(...args) });
  const seen = [];
  const feed = events.eventStreamParser((name, data) => seen.push({ name, data }));
  feed('event: result\r');
  feed('\ndata: {"status":"adjusted","version":4}\r\n\r\n');
  output.probes.push({ name: 'SSE CRLF split at event line', expected: [{name:'result',data:'{"status":"adjusted","version":4}'}], actual: seen, defectReproduced: seen.length === 2 && seen[0].data === '' });

  const stop = new AbortController();
  let eventCount = 0;
  fetchImpl = async (_url, init) => new Response(new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode('event: ready\ndata: {"version":1}\n\n')); init.signal.addEventListener('abort', () => controller.error(new Error('probe cleanup')), { once: true }); } }), { headers: { 'Content-Type': 'text/event-stream' } });
  const pending = events.watchTrip('probe', 'ko', () => eventCount++, stop.signal);
  const bell = await Promise.race([pending, new Promise(resolve => setTimeout(() => resolve('still-pending'), 35))]);
  stop.abort();
  await pending;
  output.probes.push({ name: 'Trip SSE after ready then silent', observedAfterMs:35, actual:bell, receivedEvents:eventCount, note:'Actual function has no timer; short probe confirms it waits only for data/close/abort. Not a real-network duration measurement.' });

  const stream = load(code('lib/live/stream.ts'), ['watchIntake'], { API_BASE:'', sessionInit: async (_l, init) => init, eventStreamParser: events.eventStreamParser, fetch: (_url, init) => new Promise((_resolve,reject) => init.signal.addEventListener('abort', () => reject(new Error('probe cleanup')), {once:true})) });
  const intakeStop = new AbortController();
  const intakePending = stream.watchIntake('probe','ko',() => {},intakeStop.signal,{ watchdogMs:5,reconnectMs:[] });
  const intakeResult = await Promise.race([intakePending,new Promise(resolve => setTimeout(() => resolve('still-pending'),35))]);
  intakeStop.abort(); await intakePending;
  output.probes.push({name:'Intake headers stalled beyond watchdog', configuredWatchdogMs:5, observedAfterMs:35,actual:intakeResult,defectReproduced:intakeResult==='still-pending'});

  // Preserve the production hook/callback code, replacing only its JSX return with a test handle.
  const guardianSource = code('features/guardian/trip-guardian.tsx');
  const start = guardianSource.indexOf('export function useTripGuardian(');
  const end = guardianSource.indexOf('  return {\n    tool:',start) >= 0 ? guardianSource.indexOf('  return {\n    tool:',start) : guardianSource.indexOf('  return {\r\n    tool:',start);
  if (end < 0) throw new Error('guardian probe source boundary changed');
  let cache = { id:'trip-a',version:1,stops:[{id:'a',title:'before'}],guardian:{enabled:true,since:null,via:'header'} };
  const entry = {};
  const queryClient = { getQueryCache:()=>({find:()=>entry}),getQueryData:()=>cache,setQueryData:(_key,value)=>{cache=typeof value==='function'?value(cache):value;},invalidateQueries:()=>Promise.resolve() };
  const bindings = {useT:()=>((ko)=>ko),useSettings:()=>({language:'ko'}),useRouter:()=>({replace:()=>{}}),usePathname:()=>'/trips/trip-a',useSearchParams:()=>new Map(),useQueryClient:()=>queryClient,useTrip:()=>({data:cache}),useAppToast:()=>({show:()=>{},node:null}),useState:(v)=>[v,()=>{}],tripKey:(id,l)=>['trip',id,l],useMutation:options=>options,LiveError:class extends Error{},rememberGuardian:()=>{},setGuardian:()=>{}};
  const guardian = load(guardianSource.slice(start,end)+' return change;\n}', ['useTripGuardian'], bindings).useTripGuardian('trip-a');
  const context = guardian.onMutate({enabled:false,via:'header'});
  cache = {...cache,version:2,stops:[{id:'a',title:'changed by SSE'}]};
  guardian.onError(new Error('network unavailable'),{enabled:false,via:'header'},context);
  output.probes.push({name:'Guardian rollback after SSE refresh',expectedVersion:2,actualVersion:cache.version,actualStop:cache.stops[0].title,defectReproduced:cache.version===1});

  let photoCalls=0, candidateStreams=0;
  const candidates = [1,2,3].map(rank=>({rank,place:{name:`place-${rank}`,ref:`tour:${rank}`,content_id:String(rank)},fits:true}));
  const view={intake_id:'probe',revision:1,status:'review',sources:[],review:{checked:true,needs:{total:0},items:[{id:'0-0',source_id:'s',index:0,place:null,risk:null}]}};
  const hookBindings={useState:v=>[v,()=>{}],useMemo:fn=>fn(),useRef:v=>({current:v}),useEffect:fn=>fn(),ReviewUndo:class {active=true;activate(){}deactivate(){}},translator:()=>((ko)=>ko),LiveError:class extends Error{},itemRiskOf:()=>null,riskSignature:()=>'',streamCandidates:async(_id,_item,_rev,_lang,onFirst)=>{candidateStreams++;const list={candidates,notes:[]};onFirst(list);return list;},getPlacePhotos:async()=>{photoCalls++;return {photos:[],source_note:null};},planCandidate:(candidate,id)=>({id:`${id}:${candidate.rank}`,name:candidate.place.name}),safePhotoUrl:url=>url};
  const reviewHook=load(code('features/plan-check/use-server-review.ts'),['useServerReview'],hookBindings).useServerReview({intakeId:'probe',view,language:'ko',apply:()=>{},reread:()=>{}});
  await reviewHook.actions.candidates('0-0');
  const firstPhotos=photoCalls;
  await reviewHook.actions.candidates('0-0');
  output.probes.push({name:'Alternative photo requests on first and cached openings',candidateCount:3,candidateStreams,photoRequestsFirstOpen:firstPhotos,photoRequestsTwoOpens:photoCalls,defectReproduced:firstPhotos===6&&photoCalls===12});
  console.log(JSON.stringify(output,null,2));
}
main().catch(error => { console.error(error); process.exitCode=1; });
