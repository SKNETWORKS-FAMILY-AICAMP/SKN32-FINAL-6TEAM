(() => {
  'use strict';
  const cards = document.body.dataset.variant === 'cards';
  const original = 'tripilot-mobile-onboarding-carousel.html';
  document.body.innerHTML = `
    <aside class="review-bar"><strong>triPilot / ${cards ? 'B' : 'A'}</strong><p>${cards ? '소개를 읽은 흐름 그대로<br>마지막 화면에서 설정 시작.' : '소개를 충분히 둘러본 뒤<br>하나의 버튼으로 여행 시작.'}</p><a href="tripilot-intro-${cards ? 'start' : 'cards'}.html">${cards ? 'A · 일정 시작 버튼' : 'B · 기존 온보딩 카드'} 버전 보기 ↗</a></aside>
    <div class="device">
      <header class="header"><div class="brand"><span class="mark" aria-hidden="true">t</span>triPilot</div><button class="skip" data-go="2">소개 건너뛰기 ↗</button></header>
      <main class="pages" tabindex="0" aria-label="triPilot 서비스 소개. 아래로 스크롤하면 다음 화면으로 이동합니다.">
        <section class="page hero" aria-labelledby="intro-title">
          <div class="hero-copy"><p class="eyebrow">YOUR TRAVEL, OUR JOURNEY</p><h1 id="intro-title">계획부터 여행까지,<br>당신 곁의 triPilot.</h1><p class="description">취향을 이해하고, 일정을 함께 살펴보는<br>나만의 여행 파트너.<br>당신은 여행의 설렘에만 집중하세요.</p></div>
          <div class="hero-badge"><small>A LITTLE MORE YOU</small><strong>내 취향에 맞게, 내 일정에 여유롭게.</strong></div>
          <button class="next-page" data-go="1"><span>아래로 스크롤하며 만나보세요</span><span aria-hidden="true">↓</span></button>
        </section>
        <section class="page how" aria-labelledby="how-title">
          <p class="eyebrow">HOW IT WORKS</p><h2 id="how-title">당신다운 여행,<br>이렇게 시작해요.</h2><p class="description">막막한 여행 준비도<br>한 단계씩, triPilot과 함께.</p>
          <div class="steps">
            <article class="step"><span class="step-no">01</span><div><h3>나의 여행 취향 알려주기</h3><p>좋아하는 테마부터 함께 가는 사람까지.<br>나에게 맞는 여행의 기준을 정해요.</p></div></article>
            <article class="step"><span class="step-no">02</span><div><h3>준비한 일정 가져오기</h3><p>가고 싶은 장소와 여행 계획을 등록하면<br>하루의 흐름을 한눈에 정리해요.</p></div></article>
            <article class="step"><span class="step-no">03</span><div><h3>함께 점검하고 다듬기</h3><p>이동 시간과 방문 조건을 살펴보고,<br>대화하며 일정을 조정해요.</p></div></article>
          </div><p class="how-note">여행 취향과 일정은 나중에도 수정할 수 있어요.</p>
          <button class="next-page" data-go="2"><span>이제, 나의 여행을 시작해 볼까요?</span><span aria-hidden="true">↓</span></button>
        </section>
        ${cards ? `<section class="page cards-page" aria-label="여행 시작을 위한 기존 온보딩 카드"><iframe title="언어 선택, 약관 동의, 여행 취향 알아보기" data-src="${original}"></iframe></section>` : `<section class="page start" aria-labelledby="start-title"><p class="eyebrow">LET’S MAKE IT YOURS</p><h2 id="start-title">다음 여행의 첫걸음,<br>여기서 시작해요.</h2><p class="description">가고 싶은 곳, 좋아하는 순간.<br>당신의 여행 이야기를 들려주세요.</p><div class="ticket"><span class="ticket-label">YOUR NEXT JOURNEY</span><div class="ticket-route"><strong>나의 취향</strong><span class="route-line" aria-hidden="true">····· →</span><strong>나의 여행</strong></div><div class="ticket-bottom"><span>TRAVEL PARTNER</span><span>triPilot</span></div></div><div class="action-area"><button class="primary" id="start"><span>내 일정 시작하기</span><span aria-hidden="true">↗</span></button><p class="action-note">언어 선택과 여행 취향 설정부터 함께할게요.</p></div></section>`}
      </main>
      <nav class="pagination" aria-label="소개 화면 이동">${['서비스 소개','이용 방법',cards ? '여행 취향 설정' : '일정 시작'].map((label,i)=>`<button class="dot" data-go="${i}" aria-label="${i+1}. ${label}" ${i===0?'aria-current="step"':''}></button>`).join('')}</nav>
      ${cards ? '' : `<section class="setup" hidden aria-label="여행 시작 설정"><button class="back">← 소개 화면으로 돌아가기</button><iframe title="여행 시작: 언어와 취향 설정" data-src="${original}"></iframe></section>`}
    </div><span class="review-tag">${cards ? 'B / INLINE ONBOARDING' : 'A / SINGLE CALL TO ACTION'}</span>`;
  const pages = document.querySelector('.pages');
  const sections = [...pages.children];
  const skip = document.querySelector('.skip');
  const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  const go = index => pages.scrollTo({top:sections[index].offsetTop,behavior:reducedMotion()?'instant':'smooth'});
  document.querySelectorAll('[data-go]').forEach(button => button.addEventListener('click',()=>go(Number(button.dataset.go))));
  function loadFrame(frame){if(frame && !frame.hasAttribute('src')) frame.src=frame.dataset.src;}
  const observer = new IntersectionObserver(entries=>entries.forEach(entry=>{
    if(!entry.isIntersecting || entry.intersectionRatio < .6)return;
    const index=sections.indexOf(entry.target);
    document.querySelectorAll('.dot').forEach((dot,i)=>{if(i===index)dot.setAttribute('aria-current','step');else dot.removeAttribute('aria-current');});
    skip.textContent=index===2?'처음으로 ↑':'소개 건너뛰기 ↗';
    skip.dataset.go=index===2?'0':'2';
    if(index===2 && cards)loadFrame(entry.target.querySelector('iframe'));
  }),{root:pages,threshold:.6});
  sections.forEach(section=>observer.observe(section));
  pages.addEventListener('keydown',event=>{
    if(event.target!==pages)return;
    const current=Math.round(pages.scrollTop/pages.clientHeight);
    const keys={ArrowDown:Math.min(2,current+1),PageDown:Math.min(2,current+1),ArrowUp:Math.max(0,current-1),PageUp:Math.max(0,current-1),Home:0,End:2};
    if(event.key in keys){event.preventDefault();go(keys[event.key]);}
  });
  if(!cards){
    const setup=document.querySelector('.setup');
    document.querySelector('#start').addEventListener('click',()=>{loadFrame(setup.querySelector('iframe'));setup.hidden=false;pages.inert=true;document.querySelector('.pagination').inert=true;skip.hidden=true;setup.querySelector('.back').focus();});
    setup.querySelector('.back').addEventListener('click',()=>{setup.hidden=true;pages.inert=false;document.querySelector('.pagination').inert=false;skip.hidden=false;document.querySelector('#start').focus();});
  }
})();
