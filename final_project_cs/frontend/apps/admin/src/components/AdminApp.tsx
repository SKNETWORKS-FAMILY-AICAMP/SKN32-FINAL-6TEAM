'use client';

import { useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { Activity, ArrowRight, Bell, Gauge, Home, Inbox, ListChecks, LogOut, PanelLeft, RotateCcw, Settings2, ShieldCheck, Users } from 'lucide-react';
import { createAdminGateway } from '../lib/gateway';
import { isDemoMode } from '../lib/data-mode';
import { DEMO_OPERATOR } from '../lib/demo/fixtures';
import type { AdminCommand, ScreenProps, ViewState } from '../lib/model';
import { HomeScreen, UsersScreen, UserDetailScreen, LimitsScreen, UsageScreen, ServerScreen } from '../features/overview/screens';
import { InquiriesScreen, NoticesScreen, AuditScreen, OpsScreen } from '../features/workflows/screens';
import styles from './AdminApp.module.css';

const MENUS = [
  { group: '운영', path: '/', title: '운영 홈', icon: Home },
  { group: '운영', path: '/inquiries', title: '문의함', icon: Inbox },
  { group: '운영', path: '/users', title: '사용자', icon: Users },
  { group: '사용 · 상태', path: '/usage', title: '사용량', icon: Gauge },
  { group: '사용 · 상태', path: '/server', title: '서버 상태', icon: Activity },
  { group: '설정', path: '/limits', title: '한도 · 감시 조절', icon: Settings2 },
  { group: '설정', path: '/notices', title: '공지 · 점검', icon: Bell },
  { group: '기록', path: '/audit', title: '운영 기록', icon: ListChecks },
  { group: '임시', path: '/ops', title: '승인 · 위임 · 발송', icon: ShieldCheck },
];
const SCENARIO = [
  { title: '채팅 한도 문의 읽기', path: '/inquiries/inq-01', text: '첫 번째 문의를 열어 상황을 확인합니다. 사용자 ID로 상세 화면에 이동할 수 있습니다.' },
  { title: '오늘의 예외 한도 부여', path: '/users/demo-user-01', text: '채팅 한도를 80회로 조정하고 사유를 남깁니다. 차단과 해제도 직접 체험할 수 있습니다.' },
  { title: '문의에 답변하기', path: '/inquiries/inq-01', text: '답변 템플릿을 선택하고 수정해 보냅니다. 답변 완료 상태와 처리 이력을 확인하세요.' },
  { title: '기능 차질 공지 게시', path: '/notices', text: '장소 정보 갱신 지연을 알리는 공지를 작성합니다. 사용자 화면 미리보기와 게시 기간을 확인하세요.' },
  { title: '발송 확인 결과 남기기', path: '/ops', text: '발송 결과가 미확인인 알림에 전달 확인 또는 미전달 확인과 근거를 기록합니다.' },
  { title: '운영 기록 확인', path: '/audit', text: '변경 전후 값, 수행자, 사유와 답변·공지 본문이 기록되었는지 확인합니다.' },
];
const DEMO_BANNER = '데모 데이터 — 서버에 저장되지 않음';
type AppProps = { mode?: string; initialPath?: string; standalone?: boolean };

export default function AdminApp(props: AppProps) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, refetchOnWindowFocus: false } } }));
  return <QueryClientProvider client={client}><Console {...props} /></QueryClientProvider>;
}

function Console({ mode, initialPath = '/', standalone = false }: AppProps) {
  const [gateway] = useState(() => isDemoMode(mode) ? createAdminGateway(mode) : null);
  const [route, setRoute] = useState(initialPath);
  const [visited, setVisited] = useState([initialPath]);
  const [viewState, setViewState] = useState<ViewState>('normal');
  const [guide, setGuide] = useState(false);
  const [step, setStep] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [toast, setToast] = useState('');
  const [resetCount, setResetCount] = useState(0);
  const query = useQuery({ queryKey: ['admin'], queryFn: () => gateway!.snapshot(), enabled: !!gateway });
  useEffect(() => {
    const onBack = () => { if (standalone && window.location.hash && !window.location.hash.startsWith('#/')) return; setRoute(standalone ? window.location.hash.slice(1) || '/login' : window.location.pathname); setToast(''); };
    window.addEventListener('popstate', onBack);
    window.addEventListener('hashchange', onBack);
    return () => { window.removeEventListener('popstate', onBack); window.removeEventListener('hashchange', onBack); };
  }, [standalone]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(''), 5000);
    return () => clearTimeout(timer);
  }, [toast]);
  const navigate = (path: string) => {
    window.history.pushState(null, '', standalone ? `#${path}` : path);
    setRoute(path); setMenuOpen(false); setToast(''); setViewState('normal');
    setVisited(paths => paths.includes(path) ? paths : [...paths, path]);
    window.scrollTo({ top: 0 });
  };
  const onCommand = async (command: AdminCommand) => {
    if (!gateway) throw new Error('연결 미설정');
    await gateway.execute(command);
    await query.refetch();
    setToast(command.type === 'check-server' ? '데모 점검 시각을 갱신했습니다. 실제 서버에 요청하지 않았습니다.' : '데모에 반영했습니다. 운영 기록에서 확인할 수 있습니다.');
  };
  const reset = async () => {
    await gateway!.reset(); await query.refetch(); setResetCount(n => n + 1); setViewState('normal'); setStep(0); setVisited([route]);
    setToast('모든 데모 변경을 초기화했습니다.');
  };
  const breadcrumb = MENUS.find(m => m.path === '/' ? route === '/' : route.startsWith(m.path))?.title || '운영자 콘솔';
  if (!gateway) return <div className={styles.unconfigured}><main id="main-content"><ShieldCheck size={38} /><h1>연결 미설정</h1><p>운영자 콘솔의 데이터 모드가 설정되지 않았습니다.</p><p>데모를 실행하려면 <code>NEXT_PUBLIC_ADMIN_DATA_MODE=demo</code>로 설정한 뒤 다시 빌드하거나 개발 서버를 다시 시작해 주세요.</p><p className="muted">다른 값은 지원하지 않습니다. 실제 API와 운영자 인증은 연결 전입니다.</p></main></div>;
  const banner = <div className={styles.demo}><span className={styles.demoDot} /><strong>{DEMO_BANNER}</strong><span>가상 운영일 2026.09.29 · KST</span></div>;
  if (route === '/login') return <div className={styles.loginPage}>{banner}<main id="main-content" className={styles.loginMain}><section className={styles.loginStory}><div className={styles.brand}>triPilot<span>OPERATIONS</span></div><span className={styles.eyebrow}>여행은 이어지고, 운영은 명확하게.</span><h1>한눈에 확인하고,<br />근거를 남기는 운영.</h1><p>문의부터 사용량, 서비스 상태까지.<br />운영자의 다음 행동을 한곳에서 연결합니다.</p><div className={styles.loginSteps}><span>01 <b>살펴보기</b> 오늘 처리할 일</span><span>02 <b>조치하기</b> 사유와 함께 변경</span><span>03 <b>확인하기</b> 운영 기록 추적</span></div></section><section className={styles.loginCard}><span className="badge">운영자 콘솔 · 시연</span><h2>운영자 로그인</h2><p className="muted">회원가입은 없습니다. 계정은 팀에서 발급합니다.</p><label>운영자 ID<input value={DEMO_OPERATOR} readOnly autoComplete="off" /></label><label>비밀번호<input placeholder="데모에서는 입력하지 않습니다" type="password" disabled autoComplete="off" /></label><p className={styles.loginNote}>실제 계정이나 비밀번호를 입력할 필요가 없습니다. 이번 시연에서는 인증하지 않습니다.</p><button className="primary" onClick={() => navigate('/')}>데모로 들어가기 — 인증하지 않음 <ArrowRight size={16} /></button><p className="muted">실제 연결 시 로그인 실패가 반복되면 계정이 잠깁니다.</p></section></main><footer className={styles.loginFooter}>triPilot · 운영자 화면 시연 / 실제 고객 데이터 없음</footer></div>;
  const data = query.data;
  const screenProps: ScreenProps | null = data ? { data, onCommand, navigate } : null;
  let screen = <section className="panel"><h1>화면을 찾을 수 없습니다</h1><button onClick={() => navigate('/')}>운영 홈으로</button></section>;
  if (screenProps) {
    if (route === '/') screen = <HomeScreen {...screenProps} />;
    else if (route === '/users') screen = <UsersScreen {...screenProps} />;
    else if (route.startsWith('/users/')) screen = <UserDetailScreen {...screenProps} userId={decodeURIComponent(route.slice('/users/'.length))} />;
    else if (route === '/limits') screen = <LimitsScreen {...screenProps} />;
    else if (route === '/usage') screen = <UsageScreen {...screenProps} />;
    else if (route === '/server') screen = <ServerScreen {...screenProps} />;
    else if (route === '/inquiries' || route.startsWith('/inquiries/')) screen = <InquiriesScreen {...screenProps} inquiryId={route === '/inquiries' ? undefined : decodeURIComponent(route.slice('/inquiries/'.length))} />;
    else if (route === '/notices') screen = <NoticesScreen {...screenProps} />;
    else if (route === '/audit') screen = <AuditScreen {...screenProps} />;
    else if (route === '/ops') screen = <OpsScreen {...screenProps} />;
  }
  const guideComplete = data ? [visited.includes('/inquiries/inq-01'), data.users[0].exceptionLimit !== null, data.inquiries[0].status === '답변 완료', data.notices.length > 1, !!data.outbox[0].resolution, visited.includes('/audit') && data.audit.length > 1].filter(Boolean).length : 0;
  return <div className={styles.app}>
    <a href="#main-content" className={styles.skip} onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus(); }}>본문으로 건너뛰기</a>
    <aside className={`${styles.sidebar} ${menuOpen ? styles.open : ''}`}>
      <div className={styles.brand}>triPilot<span>OPERATIONS</span></div>
      <nav aria-label="운영 메뉴">{MENUS.map((item, i) => <div key={item.path}>{(i === 0 || MENUS[i-1].group !== item.group) && <p className={styles.navGroup}>{item.group}</p>}<button aria-current={(item.path === '/' ? route === '/' : route.startsWith(item.path)) ? 'page' : undefined} onClick={() => navigate(item.path)}><item.icon size={18} /><span>{item.title}</span>{item.path === '/inquiries' && data && <b>{data.inquiries.filter(q => q.status !== '답변 완료').length}</b>}</button></div>)}</nav>
      <div className={styles.sidebarBottom}><button onClick={() => setGuide(v => !v)} aria-expanded={guide}><ListChecks size={17} /> 시연 가이드 {guide ? '닫기' : '열기'}</button><p>v0.1 · 화면 검토용<br />실제 운영 연결 전</p></div>
    </aside>
    <div className={styles.workspace}><header className={styles.header}><button className={styles.menuButton} aria-label="메뉴 열기" aria-expanded={menuOpen} onClick={() => setMenuOpen(v => !v)}><PanelLeft size={20} /></button><span className={styles.breadcrumb}>워크스페이스 <span>/</span> <strong>{breadcrumb}</strong></span><div className={styles.operator}><span className={styles.avatar}>OP</span><span>{DEMO_OPERATOR}<small>시연 운영자</small></span><button aria-label="로그아웃" onClick={() => navigate('/login')}><LogOut size={17} /></button></div></header>
      {banner}
      <div className={styles.demoControls}><span>시나리오 실습 <b>DEMO</b></span><div><label>화면 상태<select aria-label="화면 상태" value={viewState} onChange={e => setViewState(e.target.value as ViewState)}><option value="normal">정상</option><option value="loading">불러오는 중</option><option value="empty">빈 목록</option><option value="error">불러오기 실패</option></select></label><button onClick={() => void reset()}><RotateCcw size={14} /> 데모 초기화</button><button onClick={() => setGuide(v => !v)} aria-expanded={guide}>시연 가이드</button></div></div>
      {guide && <section className={styles.guide} aria-label="운영 시나리오"><div><span className={styles.eyebrow}>팀 시연 · {step+1} / {SCENARIO.length}</span><h2>{SCENARIO[step].title}</h2><p>{SCENARIO[step].text}</p><small>진행 조건 충족 {guideComplete}/{SCENARIO.length} · 실제 변경은 없습니다.</small></div><div className={styles.guideActions}><button disabled={step === 0} onClick={() => { setStep(step-1); navigate(SCENARIO[step-1].path); }}>이전</button><button className="primary" onClick={() => navigate(SCENARIO[step].path)}>해당 화면 열기</button><button disabled={step === SCENARIO.length-1} onClick={() => { setStep(step+1); navigate(SCENARIO[step+1].path); }}>다음 <ArrowRight size={14} /></button></div></section>}
      {toast && <div role="status" className={styles.toast}>{toast}</div>}
      <main id="main-content" tabIndex={-1} className={styles.main} key={`${route}-${resetCount}`}>
        {(query.isPending || viewState === 'loading') ? <section className={styles.state} role="status"><span className={styles.spinner} /><h1>불러오는 중</h1><p>데모 로딩 상태를 보여주고 있습니다.</p><button onClick={() => setViewState('normal')}>정상 화면 보기</button></section> : (query.isError || viewState === 'error') ? <section className={styles.state} role="alert"><Activity size={32} /><h1>불러오기 실패</h1><p>{query.error?.message || '요청을 완료하지 못했습니다. 데이터가 저장되거나 변경되지 않았습니다.'}</p><button onClick={() => { setViewState('normal'); void query.refetch(); }}>다시 불러오기</button></section> : viewState === 'empty' ? <section className={styles.state}><Inbox size={34} /><h1>표시할 데이터가 없습니다.</h1><p>이 조회에 해당하는 항목이 없습니다. 화면 상태를 정상으로 바꾸어 시연을 이어가세요.</p><button onClick={() => setViewState('normal')}>정상 화면 보기</button></section> : screen}
      </main><footer className={styles.footer}>triPilot 운영자 콘솔 <span>모든 수치·인물·처리 결과는 시연용입니다.</span></footer>
    </div>
  </div>;
}
