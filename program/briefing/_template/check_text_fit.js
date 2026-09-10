// 아키텍처 문서 관문 — 글자가 상자를 넘는지 브라우저에서 잰다.
// 문서를 브라우저로 연 뒤 이 파일 내용을 콘솔에 붙여 넣는다.
// 통과 조건: {넘침: 0, 겹침: 0, 선통과: 0}
//
// ★왜 필요한가 (2026-09-10). 좌표만 보고는 글자 폭을 모른다. v2 를 손으로 그리다
//   넘침 8 · 겹침 3 · 선통과 3 이 났고, DOM 에 요소가 있다는 것을 「보인다」로
//   착각해 한동안 못 잡았다. getComputedTextLength() 는 폰트 기준이라 정적
//   미리보기 창에서도 값이 나온다.
(() => {
  const out = { 넘침: 0, 겹침: 0, 선통과: 0, 상세: [] };
  document.querySelectorAll('svg').forEach((svg, si) => {
    const S = 'SVG' + (si + 1), vb = svg.viewBox.baseVal;
    const rects = [...svg.querySelectorAll('rect')].map(r => ({
      x: +r.getAttribute('x') || 0, y: +r.getAttribute('y') || 0,
      w: +r.getAttribute('width'), h: +r.getAttribute('height') }));
    const T = [...svg.querySelectorAll('text')].map(t => {
      let len = 0; try { len = t.getComputedTextLength(); } catch (e) {}
      const x = +t.getAttribute('x'), y = +t.getAttribute('y');
      const a = t.getAttribute('text-anchor') || getComputedStyle(t).textAnchor || 'start';
      const fs = parseFloat(getComputedStyle(t).fontSize) || 12;
      const x0 = a === 'middle' ? x - len / 2 : (a === 'end' ? x - len : x);
      return { x0, x1: x0 + len, y0: y - fs * 0.85, y1: y + fs * 0.28, y, txt: t.textContent.trim() };
    });
    // 넘침 — 글자를 담는 가장 작은 상자 기준 (도해 배경 전체 rect 는 뺀다)
    T.forEach(t => {
      const cx = (t.x0 + t.x1) / 2;
      const host = rects
        .filter(r => !(r.w >= vb.width - 1 && r.h >= vb.height - 1))
        .filter(r => t.y > r.y && t.y < r.y + r.h && cx > r.x && cx < r.x + r.w)
        .sort((a, b) => a.w * a.h - b.w * b.h)[0];
      if (host) {
        const o = Math.max(host.x - t.x0, t.x1 - (host.x + host.w));
        if (o > 3) { out.넘침++; out.상세.push(`${S} 넘침 +${Math.round(o)}px 「${t.txt.slice(0, 36)}」`); }
      }
      if (t.x0 < -2 || t.x1 > vb.width + 2) { out.넘침++; out.상세.push(`${S} 도해 밖 「${t.txt.slice(0, 36)}」`); }
    });
    // 겹침
    for (let i = 0; i < T.length; i++) for (let j = i + 1; j < T.length; j++) {
      const a = T[i], b = T[j];
      if (Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0) > 2 && Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0) > 1) {
        out.겹침++; out.상세.push(`${S} 겹침 「${a.txt.slice(0, 20)}」✕「${b.txt.slice(0, 20)}」`);
      }
    }
    // 선이 글자를 지나가나
    // ★2026-09-10 오탐 교정 — 규칙 6 대로 라벨 뒤에 불투명 가림 사각형이 있고 그것이
    //   선보다 나중에 그려졌으면 선은 눈에 안 보인다. 그리기 순서와 가림을 본다.
    const all = [...svg.querySelectorAll('*')];
    const order = el => all.indexOf(el);
    const opaque = r => {
      const f = (r.getAttribute('fill') || '').trim().toLowerCase();
      if (!f || f === 'none' || f === 'transparent') return false;
      if (f.startsWith('rgba(')) return parseFloat(f.split(',')[3]) >= 0.95;
      return true;
    };
    const masks = [...svg.querySelectorAll('rect')].filter(opaque).map(r => ({
      el: r, x: +r.getAttribute('x') || 0, y: +r.getAttribute('y') || 0,
      w: +r.getAttribute('width'), h: +r.getAttribute('height') }));
    const textEls = [...svg.querySelectorAll('text')];
    [...svg.querySelectorAll('line,path,polyline')].forEach(l => {
      let P = [];
      if (l.tagName === 'line') {
        const x1 = +l.getAttribute('x1'), y1 = +l.getAttribute('y1'), x2 = +l.getAttribute('x2'), y2 = +l.getAttribute('y2');
        for (let s = 0; s <= 32; s++) P.push([x1 + (x2 - x1) * s / 32, y1 + (y2 - y1) * s / 32]);
      } else {
        try { const L = l.getTotalLength(); for (let s = 0; s <= 32; s++) { const q = l.getPointAtLength(L * s / 32); P.push([q.x, q.y]); } } catch (e) {}
      }
      T.forEach((t, ti) => {
        for (const [px, py] of P) {
          if (px > t.x0 - 1 && px < t.x1 + 1 && py > t.y0 && py < t.y1) {
            // 선보다 나중에 그려진 불투명 사각형이 그 점을 덮고, 글자도 선보다 나중이면 안 보인다
            const hidden = order(textEls[ti]) > order(l) && masks.some(m =>
              order(m.el) > order(l) && px >= m.x && px <= m.x + m.w && py >= m.y && py <= m.y + m.h);
            if (!hidden) { out.선통과++; out.상세.push(`${S} 선통과 「${t.txt.slice(0, 30)}」`); }
            break;
          }
        }
      });
    });
  });
  // ★연결이 끊긴 선(떠 있는 끝)은 여기서 재지 않는다. 2026-09-10 에 기하로 재 봤더니
  //   오탐 40건에 정작 끊긴 반환선은 못 잡았다 — 화살촉을 같은 <path> 에 그리는 방식,
  //   장식 구분선, 「배경 상자에 닿음」과 「노드에 연결됨」을 기하로 못 가르기 때문이다.
  //   연결 여부는 검토자가 도해를 보고 판정한다(템플릿 §1 ⑥).
  out.글자수 = document.querySelectorAll('svg text').length;
  out.상세 = out.상세.slice(0, 40);
  return out;
})();
