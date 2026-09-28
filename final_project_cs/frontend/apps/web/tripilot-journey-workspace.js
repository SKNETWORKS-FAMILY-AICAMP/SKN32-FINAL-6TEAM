/* Local itinerary workspace shared by the two onboarding previews. */
(() => {
  'use strict';
  const navMode=new URLSearchParams(location.search).get('nav');
  const customNav=['fixed','floating'].includes(navMode);
  if(customNav)document.documentElement.dataset.tripNavigation=navMode;
  document.addEventListener('click',event=>{
    const toggle=event.target.closest('.j-nav-toggle');
    const nav=document.querySelector('.j-floating-nav');
    if(!nav)return;
    if(toggle){const open=toggle.getAttribute('aria-expanded')!=='true';nav.classList.toggle('is-open',open);toggle.setAttribute('aria-expanded',String(open));nav.querySelector('.j-mobile-tabs').inert=!open;if(open)nav.querySelector('[aria-pressed="true"]')?.focus({preventScroll:true});}
    else if(!nav.contains(event.target)){nav.classList.remove('is-open');nav.querySelector('.j-nav-toggle').setAttribute('aria-expanded','false');nav.querySelector('.j-mobile-tabs').inert=true;}
  });
  document.addEventListener('keydown',event=>{
    if(event.key!=='Escape')return;
    const nav=document.querySelector('.j-floating-nav.is-open');
    if(nav){nav.classList.remove('is-open');const toggle=nav.querySelector('.j-nav-toggle');toggle.setAttribute('aria-expanded','false');nav.querySelector('.j-mobile-tabs').inert=true;toggle.focus();}
  });

  function view(ctx) {
    const days = [...new Set(ctx.state.stops.map(stop => stop.date))].sort();
    const day = days.includes(ctx.state.day) ? ctx.state.day : days[0] || '';
    const stops = ctx.state.stops.filter(stop => stop.date === day);
    return { days, day, stops, dayNumber: days.indexOf(day) + 1, selected: stops.find(stop => stop.id === ctx.state.selectedId) || stops[0] };
  }

  function bookingLabel(stop, t) {
    if (stop.booking === 'booked') return t('예약 있음', 'Booking noted');
    if (stop.booking === 'none') return t('예약 없음', 'No booking noted');
    return t('예약 정보 없음', 'Booking not specified');
  }

  function render(ctx) {
    const { state, t, esc, icon } = ctx;
    const { days, day, stops, dayNumber, selected } = view(ctx);
    const e = value => esc(String(value ?? ''));
    const pane = ['schedule', 'map', 'chat'].includes(state.pane) ? state.pane : 'schedule';
    const dayText = t(`${dayNumber}일차`, `Day ${dayNumber}`);
    const dates = days.length > 1 ? `${days[0]} – ${days[days.length - 1]}` : days[0] || '';
    const details = (stop, next) => `<dl class="j-details">
      <dt>${t('날짜', 'Date')}</dt><dd>${e(stop.date)}</dd>
      <dt>${t('예정 시간', 'Planned time')}</dt><dd>${e(stop.time)}</dd>
      <dt>${t('예약 표시', 'Booking note')}</dt><dd>${bookingLabel(stop, t)}</dd>
      ${stop.originalTime && stop.originalTime !== stop.time ? `<dt>${t('시간 조정', 'Time adjustment')}</dt><dd>${e(stop.originalTime)} → ${e(stop.time)}</dd>` : ''}
      <dt>${t('다음 일정', 'Next stop')}</dt><dd>${next ? `${e(next.time)} · ${e(next.title)}` : t('이날 마지막 일정', 'Last stop of the day')}</dd>
      <dt>${t('입력한 메모', 'Your notes')}</dt><dd>${e(stop.notes || t('등록된 메모가 없어요.', 'No notes added.'))}</dd>
    </dl>`;
    const pointRows = Math.ceil(stops.length / 3);
    const diagramHeight = Math.max(230, pointRows * 100 + 24);
    const points = stops.map((stop, index) => {
      const row = Math.floor(index / 3), column = row % 2 ? 2 - index % 3 : index % 3;
      return { stop, index, x: 60 + column * 120, y: 48 + row * 100 };
    });
    const tabs = [['schedule', 'calendar', t('일정', 'Schedule')], ['map', 'pin', t('방문 순서', 'Visit order')], ['chat', 'chat', t('채팅', 'Chat')]];
    const tabMarkup=`<div class="j-mobile-tabs" role="group" aria-label="${t('여행 화면', 'Travel views')}">${tabs.map(([key, symbol, label]) => `<button type="button" id="j-pane-button-${key}" data-j-action="w-pane" data-value="${key}" aria-pressed="${pane === key}" aria-controls="j-pane-${key}">${icon(symbol)}${label}</button>`).join('')}</div>`;
    const selectedTab=tabs.find(tab=>tab[0]===pane);
    const navigation=navMode==='floating'?`<nav class="j-floating-nav" aria-label="${t('여행 화면','Travel views')}"><button type="button" id="j-nav-toggle" class="j-nav-toggle" aria-label="${selectedTab[2]} · ${t('메뉴 열기 또는 닫기','Toggle navigation')}" aria-expanded="false" aria-controls="j-floating-menu">${icon(selectedTab[1])}</button><div id="j-floating-menu" class="j-floating-menu">${tabMarkup.replace('role="group"','role="group" inert')}</div></nav>`:tabMarkup;
    return `<div class="j-workspace">
      <section class="j-tripbar" aria-labelledby="j-workspace-title">
        <div><p class="j-eyebrow">${t('여행을 함께 살펴볼까요', 'YOUR JOURNEY, TOGETHER')}</p><h1 id="j-workspace-title">${t('나의 여행', 'Your trip')}</h1></div>
        <p class="j-tripmeta">${icon('calendar')}<span>${e(dates)}<br>${t(`${days.length}일 · ${state.stops.length}개 일정`, `${days.length} days · ${state.stops.length} stops`)}</span></p>
      </section>
      <div class="j-watchbar"><strong>${icon('check')}${t('여행 관리 화면', 'Your travel workspace')}</strong><span>${t('입력한 일정으로 둘러보는 데모', 'A demo using your itinerary')}</span></div>
      <div class="j-daybar">
        <div class="j-day-tabs" role="group" aria-label="${t('여행 일차', 'Travel days')}">${days.map((date, index) => `<button type="button" id="j-day-${index}" data-j-action="w-day" data-value="${e(date)}" aria-pressed="${date === day}">${t(`${index + 1}일차`, `Day ${index + 1}`)}<span>${e(date.slice(5).replace('-', '.'))}</span></button>`).join('')}</div>
        <button type="button" class="j-button j-secondary" data-j-action="w-edit">${icon('edit')}${t('일정 수정', 'Edit itinerary')}</button>
      </div>
      ${navigation}
      <div class="j-workspace-grid">
        <section class="j-pane" id="j-pane-schedule" data-active="${pane === 'schedule'}" aria-labelledby="j-schedule-heading">
          <header class="j-panehead"><h2 id="j-schedule-heading">${dayText} ${t('일정', 'schedule')}</h2><span class="j-badge">${t(`${stops.length}개`, `${stops.length} stops`)}</span></header>
          <div class="j-timeline">${stops.map((stop, index) => {
            const expanded = state.expandedId === stop.id;
            return `<article class="j-stop" data-selected="${selected?.id === stop.id}">
              <button type="button" class="j-stophead" id="j-stop-trigger-${index}" data-j-action="w-stop" data-id="${e(stop.id)}" aria-expanded="${expanded}" aria-controls="j-stop-detail-${index}">
                <time>${e(stop.time)}</time><span class="j-stop-copy"><strong>${e(stop.title)}</strong><span class="j-stop-tags"><span class="j-badge">${bookingLabel(stop, t)}</span>${stop.originalTime && stop.originalTime !== stop.time ? `<span class="j-badge">${t('시간 조정', 'Time adjusted')}</span>` : ''}</span></span><span class="j-icon" aria-hidden="true">${expanded ? '−' : '+'}</span>
              </button>
              <div class="j-stop-details" id="j-stop-detail-${index}"${expanded ? '' : ' hidden'}>${details(stop, stops[index + 1])}<div class="j-detail-actions"><button type="button" class="j-button j-secondary" data-j-action="w-map" data-id="${e(stop.id)}">${icon('pin')}${t('방문 순서 보기', 'Show visit order')}</button><button type="button" class="j-button j-secondary" data-j-action="w-ask" data-id="${e(stop.id)}">${icon('chat')}${t('이 일정 질문하기', 'Ask about this stop')}</button></div></div>
            </article>${index < stops.length - 1 ? `<p class="j-movement">${icon('arrow')}${t('다음 일정으로', 'Next stop')}</p>` : ''}`;
          }).join('') || `<p class="j-empty">${t('이 날짜에는 등록한 일정이 없어요.', 'There are no stops for this date.')}</p>`}</div>
        </section>
        <section class="j-pane j-map-pane" id="j-pane-map" data-active="${pane === 'map'}" aria-labelledby="j-map-heading">
          <header class="j-panehead"><h2 id="j-map-heading">${t('방문 순서 개념도', 'Visit order diagram')}</h2><span class="j-muted">${dayText}</span></header>
          ${stops.length ? `<div class="j-map-diagram" style="aspect-ratio:360/${diagramHeight}"><svg viewBox="0 0 360 ${diagramHeight}" aria-hidden="true" focusable="false"><polyline class="j-map-path" points="${points.map(point => `${point.x},${point.y}`).join(' ')}" fill="none"/></svg><div class="j-map-points">${points.map(({ stop, index, x, y }) => `<button type="button" class="j-map-point" id="j-map-point-${index}" style="left:${x / 360 * 100}%;top:${y / diagramHeight * 100}%" data-j-action="w-map" data-id="${e(stop.id)}" aria-pressed="${selected?.id === stop.id}" aria-label="${index + 1}. ${e(stop.title)}"><span class="j-map-number">${index + 1}</span><span class="j-map-label">${e(stop.title)}</span></button>`).join('')}</div></div>` : `<p class="j-empty">${t('일정을 등록하면 방문 순서가 표시돼요.', 'Add stops to see their visit order.')}</p>`}
          <p class="j-chatnote">${t('번호는 방문 순서입니다. 실제 위치·거리·이동 경로를 표시하지 않습니다.', 'Numbers show visit order, not actual locations, distances, or routes.')}</p>
          <div class="j-map-selection">${selected ? `<p class="j-eyebrow">${t('선택한 일정', 'SELECTED STOP')}</p><h3>${e(selected.title)}</h3><p class="j-muted">${e(selected.time)} · ${bookingLabel(selected, t)}</p><p>${e(selected.notes || t('등록된 메모가 없어요.', 'No notes added.'))}</p><div class="j-detail-actions"><button type="button" class="j-button j-secondary" data-j-action="w-details" data-id="${e(selected.id)}">${t('일정 상세 보기', 'View details')}${icon('arrow')}</button><button type="button" class="j-button j-secondary" data-j-action="w-ask" data-id="${e(selected.id)}">${icon('chat')}${t('채팅으로 질문', 'Ask in chat')}</button></div>` : `<p class="j-muted">${t('일정을 선택하면 상세가 표시돼요.', 'Select a stop to see its details.')}</p>`}</div>
        </section>
        <section class="j-pane j-chat-pane" id="j-pane-chat" data-active="${pane === 'chat'}" aria-labelledby="j-chat-heading">
          <header class="j-panehead"><h2 id="j-chat-heading">${t('여행 채팅', 'Travel chat')}</h2><span class="j-badge">${t('데모', 'Demo')}</span></header>
          <div class="j-chatlog" id="j-chat-log" role="log" aria-label="${t('여행 대화 이력', 'Travel conversation')}" aria-live="polite" aria-relevant="additions text">
            <div class="j-chatcontext"><strong>${dayText} · ${e(day)}</strong><span>${selected ? e(t(`선택: ${selected.title}`, `Selected: ${selected.title}`)) : t('선택한 일정이 없어요.', 'No stop selected.')}</span></div>
            ${state.messages.length ? state.messages.map(message => `<article class="j-message" data-role="${message.role === 'user' ? 'user' : 'assistant'}"><p class="j-message-meta">${message.role === 'user' ? t('나', 'You') : 'triPilot'}</p><p class="j-message-bubble">${e(message.text)}</p></article>`).join('') : `<article class="j-message" data-role="assistant"><p class="j-message-meta">triPilot</p><p class="j-message-bubble">${t('등록한 일정에서 궁금한 내용을 골라 주세요. 하루 요약, 선택한 장소와 다음 일정을 함께 살펴볼 수 있어요.', 'Explore your saved itinerary. Ask for a day summary, details of your selected stop, or what comes next.')}</p></article>`}
          </div>
          <div class="j-composer"><div class="j-prompts"><button type="button" class="j-button j-quiet" data-j-action="w-prompt" data-value="day">${t('하루 요약', 'Day summary')}</button><button type="button" class="j-button j-quiet" data-j-action="w-prompt" data-value="selected"${selected ? '' : ' disabled'}>${t('선택 일정', 'Selected stop')}</button><button type="button" class="j-button j-quiet" data-j-action="w-prompt" data-value="next"${selected ? '' : ' disabled'}>${t('다음 일정', 'Next stop')}</button><button type="button" class="j-button j-quiet" data-j-action="w-prompt" data-value="booking">${t('예약 표시', 'Booking notes')}</button></div>
            <form class="j-chat-form" data-j-form="chat" novalidate><label class="j-sr-only" for="j-chat-message">${t('여행 메시지', 'Travel message')}</label><input class="j-chat-input" id="j-chat-message" name="message" value="${e(state.draft)}" maxlength="600" autocomplete="off" placeholder="${t('일정에 대해 궁금한 점을 입력하세요', 'Ask about your itinerary')}" aria-describedby="j-chat-error"><button type="submit" class="j-button j-primary" aria-label="${t('메시지 전송', 'Send message')}">${icon('send')}<span>${t('전송', 'Send')}</span></button><p class="j-error" id="j-chat-error" role="alert"></p></form>
            <p class="j-chatnote">${t('등록된 일정에 대한 시연 응답입니다. 실제 일정·예약 변경은 실행되지 않습니다.', 'Demo replies use your itinerary. No actual itinerary or booking changes are performed.')}</p>
          </div>
        </section>
      </div>
      <footer class="j-workspace-footer"><span>${icon('leaf')}${t('예약 표시는 입력한 정보 기준입니다.', 'Booking notes reflect the information you entered.')}</span><button type="button" class="j-button j-quiet" data-j-action="w-results">${t('검증 결과 다시 보기', 'Review verification results')}${icon('arrow')}</button></footer>
    </div>`;
  }

  function reply(intent, ctx) {
    const { t } = ctx;
    const { day, stops, selected } = view(ctx);
    if (intent === 'change') return t('이 데모에서는 실제 일정·예약을 변경하거나 취소하지 않아요. 「일정 수정」에서 계획을 고치고 다시 검증할 수 있어요.', 'This demo does not change or cancel actual plans or bookings. Use “Edit itinerary” to revise your plan and check it again.');
    if (!stops.length) return t('이 날짜에는 등록된 일정이 없어요. 일정 수정에서 계획을 추가해 주세요.', 'No stops are saved for this date. Add your plans with “Edit itinerary”.');
    if (intent === 'day') return `${day}\n${stops.map((stop, index) => `${index + 1}. ${stop.time} · ${stop.title}`).join('\n')}`;
    if (intent === 'selected' && selected) {
      const next = stops[stops.indexOf(selected) + 1];
      return `${selected.date} ${selected.time} · ${selected.title}\n${bookingLabel(selected, t)}\n${selected.notes || t('등록된 메모가 없어요.', 'No notes added.')}${selected.originalTime && selected.originalTime !== selected.time ? `\n${t('시간 조정', 'Time adjustment')}: ${selected.originalTime} → ${selected.time}` : ''}\n${next ? t(`다음 일정: ${next.time} · ${next.title}`, `Next stop: ${next.time} · ${next.title}`) : t('이날 마지막 일정이에요.', 'This is the last stop of the day.')}`;
    }
    if (intent === 'next' && selected) {
      const next = stops[stops.indexOf(selected) + 1];
      return next ? t(`${selected.title} 다음은 ${next.time} · ${next.title}입니다. 실제 이동 경로와 소요 시간은 이 개념도에서 계산하지 않아요.`, `After ${selected.title}: ${next.time} · ${next.title}. The diagram does not calculate actual routes or travel times.`) : t(`${selected.title}는 이날 마지막으로 등록한 일정이에요.`, `${selected.title} is the last saved stop for this day.`);
    }
    if (intent === 'booking') {
      const booked = stops.filter(stop => stop.booking === 'booked');
      return booked.length ? `${t('예약 있음으로 입력된 일정:', 'Stops marked as booked:')}\n${booked.map(stop => `${stop.time} · ${stop.title}`).join('\n')}\n${t('입력한 표시이며 실제 예약 내역을 조회한 결과는 아닙니다.', 'These are your entered notes, not a live booking lookup.')}` : t('이 날짜에는 예약 있음으로 입력된 일정이 없어요. 실제 예약 여부는 예약 내역에서 확인해 주세요.', 'No stops on this date are marked as booked. Check your booking records for actual reservations.');
    }
    return t('이 화면은 등록된 일정의 하루 요약·선택 일정·다음 일정·예약 표시를 조회하는 시연입니다. 아래 질문 버튼으로 확인할 내용을 골라 주세요. 자유로운 요청에 대한 실제 조회나 변경은 실행되지 않아요.', 'This preview provides day summaries, selected-stop details, next stops, and booking notes from your itinerary. Choose a question below. Open-ended requests do not run live lookups or changes.');
  }

  function intentFor(text) {
    if (/변경|취소|환불|바꿔|미뤄|앞당|예약해|change|cancel|refund|reschedule|book (?:it|this|the)/i.test(text)) return 'change';
    if (/다음|next/i.test(text)) return 'next';
    if (/선택|상세|selected|detail/i.test(text)) return 'selected';
    if (/예약|booking|reservation|booked/i.test(text)) return 'booking';
    if (/요약|일정|오늘|summary|schedule|today|day/i.test(text)) return 'day';
    return 'unknown';
  }

  function refresh(ctx, focusId) {
    ctx.render();
    if (focusId) document.getElementById(focusId)?.focus({ preventScroll: true });
  }

  function send(ctx, text, intent, clearDraft) {
    ctx.state.messages.push({ role: 'user', text }, { role: 'assistant', text: reply(intent, ctx) });
    if (clearDraft) ctx.state.draft = '';
    ctx.state.pane = 'chat';
    refresh(ctx, 'j-chat-message');
    const log = document.getElementById('j-chat-log');
    if (log) log.scrollTop = log.scrollHeight;
  }

  function action(name, el, ctx) {
    const { state, t } = ctx;
    const { days, day, stops, selected } = view(ctx);
    const stop = state.stops.find(item => item.id === el.dataset.id);
    switch (name) {
      case 'w-day': {
        if (!days.includes(el.dataset.value)) return true;
        state.day = el.dataset.value;
        state.selectedId = state.stops.find(item => item.date === state.day)?.id || null;
        state.expandedId = null;
        refresh(ctx, `j-day-${days.indexOf(state.day)}`);
        return true;
      }
      case 'w-pane':
        if (!['schedule', 'map', 'chat'].includes(el.dataset.value)) return true;
        state.pane = el.dataset.value;
        refresh(ctx, navMode==='floating'?'j-nav-toggle':`j-pane-button-${state.pane}`);
        return true;
      case 'w-stop':
        if (!stop) return true;
        state.selectedId = stop.id;
        state.expandedId = state.expandedId === stop.id ? null : stop.id;
        refresh(ctx, `j-stop-trigger-${stops.indexOf(stop)}`);
        return true;
      case 'w-map':
        if (!stop) return true;
        state.day = stop.date;
        state.selectedId = stop.id;
        state.pane = 'map';
        refresh(ctx, `j-map-point-${view(ctx).stops.indexOf(stop)}`);
        return true;
      case 'w-details':
        if (!stop) return true;
        state.day = stop.date;
        state.selectedId = stop.id;
        state.expandedId = stop.id;
        state.pane = 'schedule';
        refresh(ctx, `j-stop-trigger-${view(ctx).stops.indexOf(stop)}`);
        document.getElementById(`j-stop-trigger-${view(ctx).stops.indexOf(stop)}`)?.scrollIntoView({ block: 'nearest', behavior: 'auto' });
        return true;
      case 'w-ask':
        if (!stop) return true;
        state.day = stop.date;
        state.selectedId = stop.id;
        send(ctx, t(`${stop.title} 일정의 상세를 알려 주세요.`, `Tell me about the ${stop.title} stop.`), 'selected', false);
        return true;
      case 'w-prompt': {
        const prompts = {
          day: t(`${day} 하루 일정을 요약해 주세요.`, `Summarize the itinerary for ${day}.`),
          selected: selected ? t(`${selected.title} 일정의 상세를 알려 주세요.`, `Tell me about the ${selected.title} stop.`) : '',
          next: selected ? t(`${selected.title} 다음 일정을 알려 주세요.`, `What comes after ${selected.title}?`) : '',
          booking: t(`${day} 예약 표시를 알려 주세요.`, `Show booking notes for ${day}.`)
        };
        if (Object.hasOwn(prompts, el.dataset.value) && prompts[el.dataset.value]) send(ctx, prompts[el.dataset.value], el.dataset.value, false);
        return true;
      }
      case 'w-edit': ctx.navigate('registration'); return true;
      case 'w-results': ctx.navigate('results'); return true;
      default: return false;
    }
  }

  function submit(form, ctx) {
    if (form.dataset.jForm !== 'chat') return false;
    const input = form.querySelector('[name="message"]');
    const text = String(input?.value ?? ctx.state.draft).trim();
    if (!text) {
      const error = form.querySelector('#j-chat-error');
      if (error) error.textContent = ctx.t('메시지를 입력해 주세요.', 'Enter a message.');
      input?.setAttribute('aria-invalid', 'true');
      input?.focus();
      return true;
    }
    send(ctx, text, intentFor(text), true);
    return true;
  }

  window.triPilotWorkspace = { render, action, submit };
})();
