/* Shared, page-local journey preview for the two onboarding homes. */
(() => {
  'use strict';
  const home = document.querySelector('#app');
  const shell = document.createElement('main');
  shell.id = 'journey-app';
  shell.className = 'phone journey-shell';
  shell.hidden = true;
  home.after(shell);
  const state = {
    lang: 'ko', answers: {}, view: 'home', source: '', scenario: 'success', verificationScenario: 'success',
    rawStops: [], stops: [], results: [], status: 'draft', verification: 'idle', progress: 0,
    scope: false, day: '', resultDay: '', pane: 'schedule', selectedId: '', expandedId: '',
    draft: '', messages: [], error: '',
  };
  let onHome = null, timer = null;
  const t = (ko, en) => state.lang === 'ko' ? ko : en;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const icon = name => {
    const paths = {
      arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>', back: '<path d="M20 12H4m6-6-6 6 6 6"/>',
      check: '<path d="m5 12 4 4L19 6"/>', pin: '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',
      calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18"/>',
      chat: '<path d="M21 11a9 9 0 0 1-9 9H4l-2 2V11a9 9 0 0 1 19 0Z"/><path d="M7 10h10m-10 4h6"/>',
      edit: '<path d="m15 4 5 5-11 11H4v-5L15 4Zm-2 2 5 5"/>', send: '<path d="m3 3 18 9-18 9 4-9-4-9Zm4 9h14"/>',
      leaf: '<path d="M20 3C9 2 2 7 5 16c9 6 16-2 15-13ZM3 21 16 8"/>',
      home: '<path d="m3 10 9-7 9 7M5 9v12h14V9M9 21v-7h6v7"/>', close: '<path d="m6 6 12 12M6 18 18 6"/>',
    };
    return `<svg class="j-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.leaf}</svg>`;
  };
  const button = (action, text, primary = false, attributes = '') => `<button type="button" class="j-button ${primary ? 'j-primary' : 'j-secondary'}" data-j-action="${action}" ${attributes}>${text}</button>`;
  const days = () => [...new Set(state.stops.map(stop => stop.date))];
  const context = () => ({state, t, esc, icon, render, navigate});
  const stages = () => [
    [t('여행 계획 읽기', 'Read your plan'), t('날짜와 장소, 머무는 시간을 정리해요.', 'Organize dates, places, and planned times.')],
    [t('장소와 운영시간', 'Places & opening hours'), t('방문 조건을 확인하는 과정을 살펴봐요.', 'Preview the checks for each visit.')],
    [t('이동과 예약 조건', 'Travel & reservations'), t('이동 여유와 예약 시간을 함께 살펴봐요.', 'Review travel buffers and reserved times.')],
    [t('전체 일정 정리', 'Bring it all together'), t('달라진 점과 유지할 내용을 모아요.', 'Gather changes and the plans to keep.')],
  ];
  function preferenceMarkup() {
    const a = state.answers;
    const themeLabels = {food:t('맛집 탐방','Food'),nature:t('자연과 힐링','Nature'),culture:t('문화와 역사','Culture'),activity:t('액티비티','Activities'),shopping:t('쇼핑','Shopping'),local:t('로컬 일상','Local life')};
    const tags = (a.themes || []).map(value => themeLabels[value]);
    const people = (a.adults || 1) + (a.children || 0) + (a.infants || 0);
    return `<div class="j-preferences"><span class="j-eyebrow">${t('함께 고른 여행 취향','YOUR TRAVEL PREFERENCES')}</span><div class="j-tags">${tags.map(label => `<span class="j-pill">${esc(label)}</span>`).join('')}<span class="j-pill">${people}${t('명과 함께',' travelers')}</span></div><p class="j-muted">${t('홈에서 고른 취향을 이 여행과 함께 이어가요.','The preferences you chose stay with this journey.')}</p></div>`;
  }
  function registrationMarkup() {
    return `<header class="j-page-header"><p class="j-eyebrow">A PLAN THAT FEELS LIKE YOU</p><h1>${t('이제, 여행을 담아볼까요?','Let’s put your trip together.')}</h1><p>${t('준비한 계획을 그대로 붙여 넣어 주세요.<br>하나씩 살펴보고, 편안한 여행으로 이어갈게요.','Paste the plan you have prepared.<br>We’ll walk through it, one step at a time.')}</p></header>
    <form data-j-form="plan" novalidate><div class="j-plan-layout"><section class="j-card j-plan-editor">
      <div class="j-label-row"><label for="j-plan-source">${t('나의 여행 계획','Your travel plan')}</label><button type="button" class="j-button j-quiet" data-j-action="sample">${t('예시 불러오기','Load example')}</button></div>
      <textarea id="j-plan-source" class="j-plan-input" name="source" maxlength="12000" required aria-invalid="${Boolean(state.error)}" aria-describedby="j-plan-format j-plan-error" placeholder="${t('1일차 · 2026-09-15\n09:00 호텔 조식\n13:00 점심 식당 · 예약 있음\n\n2일차 · 2026-09-16\n10:00 박물관 관람','DAY 1 · 2026-09-15\n09:00 Hotel breakfast\n13:00 Lunch restaurant · reserved\n\nDAY 2 · 2026-09-16\n10:00 Museum visit')}">${esc(state.source)}</textarea>
      <div class="j-input-meta"><span id="j-plan-format">${t('날짜 · 시간 · 장소를 함께 적어 주세요.','Include dates, times, and places.')}</span><span id="j-source-count">${state.source.length.toLocaleString()} / 12,000</span></div><p id="j-plan-error" class="j-error" role="alert">${esc(state.error)}</p>
    </section><aside class="j-plan-tips"><section class="j-card">${preferenceMarkup()}<hr><h2>${t('작은 준비, 더 편한 여행','A little preparation goes a long way')}</h2><ol class="j-tip-list"><li>${t('일차 제목에 날짜를 적어요.','Start each day with a date.')}</li><li>${t('시작 시간과 장소를 한 줄씩 적어요.','Write each start time and place on a new line.')}</li><li>${t('예약한 일정은 ‘예약 있음’으로 표시해요.','Mark reserved plans with “reserved”.')}</li></ol></section>
    <details class="j-demo-options"><summary>${t('목업 체험 옵션','Preview options')}</summary><label for="j-scenario">${t('검증 결과 시나리오','Verification scenario')}</label><select id="j-scenario" name="scenario">${[['success',t('검증 완료','Completed')],['needs-review',t('확인이 필요한 항목','Items needing review')],['failed',t('검증 중단 후 재시도','Failure and retry')]].map(([value,label])=>`<option value="${value}" ${state.scenario===value?'selected':''}>${label}</option>`).join('')}</select><p class="j-muted">${t('준비된 응답으로 화면 흐름을 체험해요.','Explore the flow with prepared responses.')}</p></details></aside></div>
    <div class="j-actions">${button('home',icon('back')+t('홈으로','Home'))}<span class="j-action-note">${t('입력한 계획은 화면을 오가도 유지돼요.','Your draft stays while you explore.')}</span><button type="submit" class="j-button j-primary">${t('계획 확인하기','Check my plan')}${icon('arrow')}</button></div></form>`;
  }
  function verificationMarkup() {
    const failed = state.verification === 'failed', ready = state.verification === 'completed';
    const labels = stages(), completed = Math.floor(state.progress / 25), current = Math.min(3, completed);
    return `<header class="j-page-header"><p class="j-eyebrow">A LITTLE CHECK, A BETTER JOURNEY</p><h1>${failed?t('잠시 쉬어가는 중이에요.','Let’s try that once more.'):ready?t('여행 계획을 살펴봤어요.','Your plan is ready to review.'):t('더 편한 여행을 준비해요.','Getting your journey ready.')}</h1><p>${t('계획부터 이동까지, 차근차근 확인하는 과정이에요.','From your plan to travel details, one step at a time.')}</p></header>
    <section class="j-card"><div class="j-progress-top"><div><p class="j-eyebrow">${t('여행 계획 확인','CHECKING YOUR PLAN')}</p><h2>${ready?t('결과가 준비되었어요','Your results are ready'):labels[current][0]}</h2></div><strong class="j-progress-number">${state.progress}<small>%</small></strong></div>
    <div class="j-progress-track" role="progressbar" aria-label="${t('계획 확인 진행률','Plan check progress')}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${state.progress}"><div class="j-progress-fill" style="width:${state.progress}%"></div></div>
    <ol class="j-stage-list">${labels.map(([label,desc],i)=>{const status=ready||i<completed?'completed':i===current?(failed?'failed':'running'):'pending';return `<li class="j-stage" data-status="${status}" ${status==='running'?'aria-current="step"':''}><span class="j-stage-number">${status==='completed'?icon('check'):i+1}</span><div><h3>${label}</h3><p>${desc}</p></div><span class="j-stage-state">${status==='completed'?t('완료','Done'):status==='running'?t('확인 중','Checking'):status==='failed'?t('중단','Stopped'):t('대기','Next')}</span></li>`}).join('')}</ol>
    ${failed?`<p class="j-warning" role="alert">${t('검증이 중단된 상황을 체험하고 있어요. 입력한 계획을 유지한 채 다시 시도할 수 있어요.','This preview simulates an interrupted check. You can retry with your original plan preserved.')}</p>`:''}
    <div class="j-actions">${button('registration',t('계획 보기','View plan'))}${failed?button('retry',t('다시 시도하기','Try again'),true):button('results',t('결과 확인하기','View results')+icon('arrow'),true,ready?'':'disabled')}</div></section>`;
  }
  function resultItem(result) {
    const adjusted=result.status==='adjusted', review=result.status==='needs_review';
    return `<details class="j-result${adjusted?' j-result-adjusted':''}" ${review?'open':''}><summary><div><span class="j-badge ${review?'j-review':''}">${review?t('확인 필요','Review'):adjusted?t('조정','Adjusted'):t('유지','Kept')}</span><strong>${esc(result.title)}</strong><p class="j-result-brief">${esc(result.originalValue)}${adjusted?' → '+esc(result.proposedValue):' · '+t('입력한 시간','Original time')}</p></div><span aria-hidden="true">+</span></summary><div class="j-result-detail">${adjusted?`<div class="j-result-change"><span>${t('변경 전','Before')}<strong>${esc(result.originalValue)}</strong></span>${icon('arrow')}<span>${t('변경 후','After')}<strong>${esc(result.proposedValue)}</strong></span></div>`:''}<p>${esc(result.reason)}</p><p class="j-muted">${esc(result.impact)}</p></div></details>`;
  }
  function resultsMarkup() {
    const unresolved=state.results.filter(r=>r.status==='needs_review'), adjusted=state.results.filter(r=>r.status==='adjusted');
    const activeDay=days().includes(state.resultDay)?state.resultDay:days()[0];
    const active=state.status==='active';
    return `<header class="j-page-header"><p class="j-eyebrow">READY, WITH A LITTLE MORE CARE</p><h1>${unresolved.length?t('한 번 더 확인해 주세요.','A little more checking is needed.'):t('여행의 준비가 끝났어요.','You’re ready for your journey.')}</h1><p>${t('바뀐 부분은 한눈에, 지켜야 할 계획은 그대로.','See what changed and what stays just as planned.')}</p></header>
    <div class="j-stats">${[[adjusted.length,t('조정한 일정','Adjusted')],[state.results.length-adjusted.length-unresolved.length,t('유지한 일정','Kept')],[unresolved.length,t('확인이 필요한 일정','Needs review')]].map(([n,label])=>`<div class="j-stat"><strong>${n}<small>${t('개','')}</small></strong><span>${label}</span></div>`).join('')}</div>
    <div class="j-results-layout"><section class="j-card"><div class="j-card-header"><h2>${t('여행 계획 살펴보기','A closer look at your plan')}</h2><span class="j-badge">${state.results.length}${t('개 일정',' stops')}</span></div>
    ${unresolved.length?`<div class="j-warning"><strong>${t('여행 관리를 시작하기 전에','Before starting your trip')}</strong><p>${t('확인이 필요한 항목을 수정한 뒤 다시 검증해 주세요.','Edit the items needing review and check the plan again.')}</p></div>${unresolved.map(resultItem).join('')}`:''}
    <div class="j-day-tabs" aria-label="${t('결과 일차','Result days')}">${days().map((day,i)=>`<button type="button" data-j-action="result-day" data-value="${day}" aria-pressed="${day===activeDay}">${t((i+1)+'일차','Day '+(i+1))}<small>${day.slice(5).replace('-','.')}</small></button>`).join('')}</div>
    <div class="j-result-list">${state.results.filter(r=>r.date===activeDay&&r.status!=='needs_review').map(resultItem).join('')}</div></section>
    <aside class="j-card j-scope-card"><span class="j-eyebrow">WITH YOU, ALONG THE WAY</span><h2>${t('이제 여행에 집중하세요.','Make room for the journey.')}</h2><p class="j-muted">${t('확인한 계획을 일정과 지도에 모으고, 여행 채팅으로 이어가요.','Bring your checked plan into your itinerary, visit diagram, and travel chat.')}</p><ul class="j-tip-list"><li>${t('조정 전후를 언제든 다시 확인','Revisit changes whenever you need')}</li><li>${t('예약이 있는 일정의 시간 유지','Keep the times of reserved plans')}</li><li>${t('일정·지도·채팅을 한곳에서','Itinerary, map, and chat together')}</li></ul>
    <label class="j-scope"><input type="checkbox" id="j-scope" ${state.scope?'checked':''}><span>${t('관리 범위를 확인했어요. 예약 변경·취소와 결제는 별도이며, 이 목업에서는 실제 감시나 예약을 실행하지 않아요.','I understand the scope. Booking changes, cancellations, and payments are separate. This preview does not monitor or book anything.')}</span></label>
    ${active?button('trip',t('내 여행으로 돌아가기','Back to my trip')+icon('arrow'),true):button('activate',t('여행 관리 시작','Start my trip')+icon('arrow'),true,(!state.scope||unresolved.length)?'disabled':'')}
    ${unresolved.length?`<p class="j-error">${t('미확인 항목을 해결해야 시작할 수 있어요.','Resolve the items needing review before starting.')}</p>${button('retry',t('검증 다시 시도','Retry verification'))}`:''}
    ${button('registration',t('계획 수정 후 다시 확인','Edit and check again'))}</aside></div>`;
  }
  function render(focus=false) {
    if(state.view==='home')return;
    document.documentElement.lang=state.lang;
    const step=state.view==='registration'?0:state.view==='checking'?1:2;
    shell.dataset.view=state.view;
    shell.innerHTML=`<header class="j-topbar"><button type="button" class="j-brand brand" data-j-action="home" aria-label="${t('triPilot 홈으로','triPilot home')}"><span class="brand-mark" aria-hidden="true">t</span>triPilot</button><div class="j-top-actions"><button type="button" class="j-home-button" data-j-action="home" aria-label="${t('홈으로','Home')}">${icon('home')}</button><button type="button" class="j-language-button" data-j-action="language">${t('English','한국어')}</button></div></header><div class="j-main">
    ${state.view!=='trip'?`<ol class="j-steps">${[t('계획 담기','Your plan'),t('함께 확인','Check together'),t('여행 시작','Your journey')].map((label,i)=>`<li ${i===step?'aria-current="step"':''} ${i<step?'data-done="true"':''}><span>${i<step?icon('check'):'0'+(i+1)}</span>${label}</li>`).join('')}</ol>`:''}
    ${state.view==='registration'?registrationMarkup():state.view==='checking'?verificationMarkup():state.view==='results'?resultsMarkup():window.triPilotWorkspace.render(context())}
    <footer class="j-footer"><span>${icon('leaf')}${t('당신의 취향대로, 더 편안하게.','More you. A little more at ease.')}</span><p class="j-demo-note">${t('인터랙션 목업 · 검증과 채팅은 시연 응답이며 실제 서비스에 연결되지 않아요.','Interactive preview · Checks and chat use demo responses, without a live service connection.')}</p></footer></div>`;
    if(focus){const target=shell.querySelector('h1');if(target){target.tabIndex=-1;target.focus({preventScroll:true})}}
  }
  function refreshResults() {
    const verified=window.triPilotJourneyData.verify(state.rawStops,state.verificationScenario,state.lang);
    state.stops=verified.stops;state.results=verified.results;
  }
  function show(view) {
    state.view=view;
    const isHome=view==='home';home.hidden=!isHome;shell.hidden=isHome;
    if(isHome){onHome?.(state.lang);return}
    window.triPilotScene.update({stage:view==='registration'?0:view==='trip'?2:1,step:0,totalSteps:1,complete:false});
    render(true);window.scrollTo({top:0,behavior:'instant'});
  }
  function navigate(view) {
    if(view==='results'&&state.verification!=='completed')view='checking';
    if(view==='trip'&&state.status!=='active')view=state.verification==='completed'?'results':'registration';
    history.pushState({tripilotView:view},'',view==='home'?location.pathname+location.search:'#'+view);
    show(view);
  }
  function beginVerification(retry=false) {
    clearInterval(timer);
    state.verificationScenario=retry?'success':state.scenario;
    state.progress=0;state.verification='running';state.status='processing';state.scope=false;state.results=[];
    state.stops=state.rawStops.map(stop=>({...stop}));state.day=days()[0];state.resultDay=state.day;
    state.selectedId=state.stops[0]?.id||'';state.expandedId='';state.messages=[];state.draft='';
    navigate('checking');
    const ticks=[25,55,80,100];let tick=0;
    timer=setInterval(()=>{
      state.progress=ticks[tick++];
      if(state.verificationScenario==='failed'&&state.progress===55){state.verification='failed';clearInterval(timer)}
      else if(state.progress===100){state.verification='completed';state.status='ready';refreshResults();clearInterval(timer)}
      if(state.view==='checking')render();
    },850);
  }
  shell.addEventListener('click',event=>{
    const el=event.target.closest('[data-j-action]');if(!el||el.disabled)return;
    const action=el.dataset.jAction;
    if(window.triPilotWorkspace.action(action,el,context()))return;
    if(['home','registration','results','trip'].includes(action)){navigate(action);return}
    if(action==='sample'){state.source=window.triPilotJourneyData.sample(state.lang);state.error='';render();shell.querySelector('#j-plan-source')?.focus()}
    if(action==='retry')beginVerification(true);
    if(action==='language'){state.lang=state.lang==='ko'?'en':'ko';if(state.verification==='completed')refreshResults();render()}
    if(action==='result-day'){state.resultDay=el.dataset.value;render()}
    if(action==='activate'&&state.verification==='completed'&&state.scope&&!state.results.some(r=>r.status==='needs_review')){state.status='active';navigate('trip')}
  });
  shell.addEventListener('input',event=>{
    if(event.target.id==='j-plan-source'){state.source=event.target.value;state.error='';shell.querySelector('#j-source-count').textContent=state.source.length.toLocaleString()+' / 12,000';shell.querySelector('#j-plan-error').textContent='';event.target.setAttribute('aria-invalid','false')}
    if(event.target.id==='j-chat-message')state.draft=event.target.value;
  });
  shell.addEventListener('change',event=>{
    if(event.target.id==='j-scenario')state.scenario=event.target.value;
    if(event.target.id==='j-scope'){state.scope=event.target.checked;const next=shell.querySelector('[data-j-action="activate"]');if(next)next.disabled=!state.scope||state.results.some(r=>r.status==='needs_review')}
  });
  shell.addEventListener('submit',event=>{
    const form=event.target;if(!form.dataset.jForm)return;event.preventDefault();
    if(form.dataset.jForm==='chat'){window.triPilotWorkspace.submit(form,context());return}
    if(form.dataset.jForm==='plan'){
      try{state.rawStops=window.triPilotJourneyData.parse(state.source,state.lang);state.error='';beginVerification()}
      catch(error){state.error=error.message;render();shell.querySelector('#j-plan-source')?.focus()}
    }
  });
  window.addEventListener('popstate',event=>{
    if(!onHome)return;
    let view=event.state?.tripilotView||'home';
    if(!['home','registration','checking','results','trip'].includes(view))view='home';
    if(view==='trip'&&state.status!=='active')view=state.verification==='completed'?'results':'registration';
    if(view==='results'&&state.verification!=='completed')view='checking';
    show(view);
  });
  history.replaceState({tripilotView:'home'},'',location.pathname+location.search);
  window.triPilotJourney={
    open(options){state.lang=options.lang;state.answers={...options.answers};onHome=options.onHome;if(state.verification==='completed')refreshResults();navigate(state.status==='active'?'trip':'registration')},
    setLanguage(lang){
      if(!['en','ko'].includes(lang))return;
      state.lang=lang;
      if(state.verification==='completed')refreshResults();
      if(state.view!=='home')render();
    },
    hasTrip(){return state.status==='active'},
  };
})();
