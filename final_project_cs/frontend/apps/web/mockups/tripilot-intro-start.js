(() => {
  'use strict';
  let language = 'en';
  const inlineCards = document.body.dataset.introEnding === 'cards';
  const copy = {
    en: {
      title:'triPilot · Your next journey', language:'Language',
      intro:'From plans to memories,<br>triPilot by your side.',
      introDescription:'A travel partner that understands your style<br>and helps you review your plans.<br>Make room for the joy of the journey.',
      badge:'Your style. Your pace. Your journey.',
      how:'A trip that feels like you.<br>One step at a time.',
      howDescription:'A little less planning stress.<br>A little more looking forward.',
      step1:'Tell us what you love', detail1:'Your favorite experiences and travel companions.<br>Set the starting point for a trip that fits you.',
      step2:'Bring your travel plans', detail2:'Add the places and plans you have in mind.<br>See each day come together at a glance.',
      step3:'Review and refine together', detail3:'Check travel times and visiting requirements.<br>Fine-tune your itinerary through conversation.',
      howNote:'You can update your preferences and plans later.',
      start:'Your next journey<br>starts right here.',
      startDescription:'The places you dream of. The moments you love.<br>Tell us what your next trip looks like.',
      taste:'Your style', trip:'Your trip', cta:'Start my itinerary',
      actionNote:'Review the terms, then tell us your travel preferences.',
      scrollHint:'Scroll down to explore', skip:'Skip intro', next:'Next screen', home:'triPilot — Back to introduction',
      pages:'triPilot introduction. Scroll down to move to the next screen.',
      navigation:'Introduction screens', labels:['Introduction','How it works','Start your itinerary'],
      setup:'Travel setup', frame:'Travel setup: language and preferences'
    },
    ko: {
      title:'triPilot · 당신다운 여행의 시작', language:'언어 선택',
      intro:'계획부터 여행까지,<br>당신 곁의 triPilot.',
      introDescription:'취향을 이해하고, 일정을 함께 살펴보는<br>나만의 여행 파트너.<br>당신은 여행의 설렘에만 집중하세요.',
      badge:'내 취향에 맞게, 내 일정에 여유롭게.',
      how:'당신다운 여행,<br>이렇게 시작해요.',
      howDescription:'막막한 여행 준비도<br>한 단계씩, triPilot과 함께.',
      step1:'나의 여행 취향 알려주기', detail1:'좋아하는 테마부터 함께 가는 사람까지.<br>나에게 맞는 여행의 기준을 정해요.',
      step2:'준비한 일정 가져오기', detail2:'가고 싶은 장소와 여행 계획을 등록하면<br>하루의 흐름을 한눈에 정리해요.',
      step3:'함께 점검하고 다듬기', detail3:'이동 시간과 방문 조건을 살펴보고,<br>대화하며 일정을 조정해요.',
      howNote:'여행 취향과 일정은 나중에도 수정할 수 있어요.',
      start:'다음 여행의 첫걸음,<br>여기서 시작해요.',
      startDescription:'가고 싶은 곳, 좋아하는 순간.<br>당신의 여행 이야기를 들려주세요.',
      taste:'나의 취향', trip:'나의 여행', cta:'내 일정 시작하기',
      actionNote:'약관 확인과 여행 취향 설정부터 함께할게요.',
      scrollHint:'아래로 스크롤하며 만나보세요', skip:'소개 건너뛰기', next:'다음 화면', home:'triPilot — 소개 화면으로 돌아가기',
      pages:'triPilot 서비스 소개. 아래로 스크롤하면 다음 화면으로 이동합니다.',
      navigation:'소개 화면 이동', labels:['서비스 소개','이용 방법','일정 시작'],
      setup:'여행 시작 설정', frame:'여행 시작: 언어와 취향 설정'
    }
  };
  const down = next => `<div class="intro-controls"><div class="scroll-cue">${next===1?'<span class="scroll-hint" data-copy="scrollHint"></span>':''}<button class="down-arrow" data-go="${next}" data-label="next"><span aria-hidden="true">↓</span></button></div><button class="skip" data-go="2"><span data-copy="skip"></span><span aria-hidden="true"> ↗</span></button></div>`;
  document.body.innerHTML = `<div class="device">
    <header class="header"><button type="button" class="brand brand-home" data-label="home"><span class="mark" aria-hidden="true">t</span>triPilot</button><label class="language-box"><span data-copy="language"></span><select id="language" data-label="language"><option value="en" lang="en">English</option><option value="ko" lang="ko">한국어</option></select></label></header>
    <main class="pages" tabindex="0" data-label="pages">
      <section class="page hero" aria-labelledby="intro-title"><div class="hero-copy"><p class="eyebrow">YOUR TRAVEL, OUR JOURNEY</p><h1 id="intro-title" data-copy="intro"></h1><p class="description" data-copy="introDescription"></p></div><div class="hero-badge"><small>A LITTLE MORE YOU</small><strong data-copy="badge"></strong></div>${down(1)}</section>
      <section class="page how" aria-labelledby="how-title"><p class="eyebrow">HOW IT WORKS</p><h2 id="how-title" data-copy="how"></h2><p class="description" data-copy="howDescription"></p><div class="steps">${[1,2,3].map(i=>`<article class="step"><span class="step-no">0${i}</span><div><h3 data-copy="step${i}"></h3><p data-copy="detail${i}"></p></div></article>`).join('')}</div><p class="how-note" data-copy="howNote"></p>${down(2)}</section>
      ${inlineCards ? '<section class="page inline-card-page" data-label="setup"></section>' : `<section class="page start" aria-labelledby="start-title"><p class="eyebrow">LET’S MAKE IT YOURS</p><h2 id="start-title" data-copy="start"></h2><p class="description" data-copy="startDescription"></p><div class="ticket"><span class="ticket-label">YOUR NEXT JOURNEY</span><div class="ticket-route"><strong data-copy="taste"></strong><span class="route-line" aria-hidden="true">····· →</span><strong data-copy="trip"></strong></div><div class="ticket-bottom"><span>TRAVEL PARTNER</span><span>triPilot</span></div></div><div class="action-area"><button class="primary" id="start"><span data-copy="cta"></span><span aria-hidden="true">↗</span></button><p class="action-note" data-copy="actionNote"></p></div></section>`}
    </main><nav class="pagination" data-label="navigation">${[0,1,2].map(i=>`<button class="dot" data-go="${i}" ${i===0?'aria-current="step"':''}></button>`).join('')}</nav>
    <section class="setup" hidden data-label="setup"><iframe></iframe></section>
  </div>`;
  const pages = document.querySelector('.pages');
  const sections = [...pages.children];
  const selector = document.querySelector('#language');
  const setup = document.querySelector('.setup');
  const frame = setup.querySelector('iframe');
  const pagination = document.querySelector('.pagination');
  function translate() {
    const text = copy[language];
    document.documentElement.lang = language;
    document.title = text.title;
    document.querySelectorAll('[data-copy]').forEach(element => {element.innerHTML = text[element.dataset.copy];});
    document.querySelectorAll('[data-label]').forEach(element => element.setAttribute('aria-label',text[element.dataset.label]));
    document.querySelectorAll('.dot').forEach((dot,i)=>dot.setAttribute('aria-label',`${i+1}. ${text.labels[i]}`));
    frame.title = text.frame;
    if(inlineCards)document.querySelectorAll('.dot')[2].setAttribute('aria-label',`3. ${text.setup}`);
  }
  function syncFrameLanguage(){
    if(frame.hasAttribute('src'))frame.contentWindow?.postMessage({type:'tripilot:set-language',lang:language},'*');
  }
  frame.addEventListener('load',syncFrameLanguage);
  selector.addEventListener('change',()=>{language=selector.value;translate();syncFrameLanguage();});
  const go = index => pages.scrollTo({top:sections[index].offsetTop,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
  document.querySelectorAll('[data-go]').forEach(button=>button.addEventListener('click',()=>go(Number(button.dataset.go))));
  const observer = new IntersectionObserver(entries=>entries.forEach(entry=>{
    if(!entry.isIntersecting || entry.intersectionRatio < .6)return;
    const index=sections.indexOf(entry.target);
    if(inlineCards){
      setup.hidden=index!==2;
      if(index===2)loadOnboarding();
    }
    document.querySelectorAll('.dot').forEach((dot,i)=>{if(i===index)dot.setAttribute('aria-current','step');else dot.removeAttribute('aria-current');});
  }),{root:pages,threshold:.6});
  sections.forEach(section=>observer.observe(section));
  pages.addEventListener('keydown',event=>{
    if(event.target!==pages)return;
    const current=Math.round(pages.scrollTop/pages.clientHeight);
    const keys={ArrowDown:Math.min(2,current+1),PageDown:Math.min(2,current+1),ArrowUp:Math.max(0,current-1),PageUp:Math.max(0,current-1),Home:0,End:2};
    if(event.key in keys){event.preventDefault();go(keys[event.key]);}
  });
  function loadOnboarding(){
    const onboarding=document.body.dataset.cardLayout==='expanded'?'tripilot-onboarding-expanded.html':'tripilot-mobile-onboarding-carousel.html';
    const navigation=['fixed','floating'].includes(document.body.dataset.navigation)?`&nav=${document.body.dataset.navigation}`:'';
    const src=`${onboarding}?embed=intro&lang=${language}${navigation}`;
    if(!frame.hasAttribute('src'))frame.src=src;
    else syncFrameLanguage();
  }
  document.querySelector('#start')?.addEventListener('click',()=>{
    loadOnboarding();
    setup.hidden=false;pages.inert=true;pagination.inert=true;frame.focus();
  });
  document.querySelector('.brand-home').addEventListener('click',()=>{
    setup.hidden=true;pages.inert=false;pagination.inert=false;
    pages.scrollTo({top:0,behavior:'instant'});
    document.querySelectorAll('.dot').forEach((dot,i)=>{if(i===0)dot.setAttribute('aria-current','step');else dot.removeAttribute('aria-current');});
  });
  window.addEventListener('message',event=>{
    if(event.source!==frame.contentWindow || event.data?.type!=='tripilot:terms-view' || typeof event.data.open!=='boolean')return;
    const expanded=event.data.open && !setup.hidden;
    setup.classList.toggle('terms-expanded',expanded);
    document.querySelector('.header').inert=expanded;

  });
  translate();
})();
