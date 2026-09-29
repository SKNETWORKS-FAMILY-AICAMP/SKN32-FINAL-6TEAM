/* Decorative background only: no form data, storage, or network services. */
(() => {
  'use strict';

  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
  const scene = document.createElement('div');
  scene.className = 'onboarding-scene';
  scene.setAttribute('aria-hidden', 'true');
  const camera = document.createElement('div');
  camera.className = 'scene-camera';
  scene.append(camera);

  const sources = [
    ['paper', 'tripilot-home-02-paper-seoul.png'],
    ['river', 'tripilot-home-01-han-river.png'],
    ['journey', 'tripilot-home-03-journey.png'],
  ];
  const layers = sources.map(([name, source], index) => {
    const layer = document.createElement('div');
    layer.className = 'scene-layer' + (index === 0 ? ' is-active' : '');
    layer.dataset.scene = name;
    const image = document.createElement('img');
    image.alt = '';
    image.draggable = false;
    image.decoding = 'async';
    image.fetchPriority = index === 0 ? 'high' : 'low';
    image.addEventListener('load', () => layer.classList.add('is-loaded'), { once: true });
    image.src = source;
    layer.append(image);
    camera.append(layer);
    return layer;
  });
  const veil = document.createElement('div');
  veil.className = 'scene-veil';
  const light = document.createElement('div');
  light.className = 'scene-light';
  scene.append(veil, light);
  document.body.prepend(scene);

  let stage = 0;
  let step = 0;
  let totalSteps = 1;
  let complete = false;
  let pointerX = 0;
  let pointerY = 0;
  let frame = 0;
  let pulse = null;

  function paintPosition() {
    frame = 0;
    const scrollRange = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    const scroll = Math.min(1, Math.max(0, window.scrollY / scrollRange));
    const moving = !motion.matches;
    scene.style.setProperty('--scene-x', (moving ? pointerX * 7 : 0) + 'px');
    scene.style.setProperty('--scene-y', (moving ? pointerY * 5 - scroll * 9 : 0) + 'px');
    scene.style.setProperty('--scene-progress', (moving && stage === 2 ? (step / Math.max(1, totalSteps - 1) - .5) * 12 : 0) + 'px');
  }

  function queuePosition() {
    if (!frame && !document.hidden) frame = window.requestAnimationFrame(paintPosition);
  }

  function feedback(kind) {
    if (!kind || motion.matches || document.hidden) return;
    pulse?.cancel();
    const finishing = kind === 'complete';
    pulse = light.animate([
      { opacity: 0, transform: 'scale(.98)' },
      { opacity: finishing ? .7 : .32, transform: 'scale(1)', offset: .35 },
      { opacity: 0, transform: 'scale(1.025)' },
    ], { duration: finishing ? 1250 : 700, easing: 'ease-out' });
  }

  window.triPilotScene = {
    update(next) {
      if ([0, 1, 2].includes(next.stage)) stage = next.stage;
      if (Number.isInteger(next.totalSteps) && next.totalSteps > 0) totalSteps = next.totalSteps;
      if (Number.isFinite(next.step)) step = Math.max(0, Math.min(totalSteps - 1, next.step));
      complete = Boolean(next.complete);
      // Return to the welcoming paper landscape when setup is complete.
      const active = complete ? 0 : stage;
      layers.forEach((layer, index) => layer.classList.toggle('is-active', index === active));
      scene.dataset.stage = String(stage);
      scene.dataset.step = String(step);
      scene.dataset.complete = String(complete);
      scene.dataset.scene = sources[active][0];
      queuePosition();
      feedback(next.feedback);
    },
  };

  document.addEventListener('pointermove', event => {
    if (!finePointer.matches || motion.matches || event.pointerType === 'touch') return;
    pointerX = Math.max(-1, Math.min(1, event.clientX / window.innerWidth * 2 - 1));
    pointerY = Math.max(-1, Math.min(1, event.clientY / window.innerHeight * 2 - 1));
    queuePosition();
  }, { passive: true });
  document.documentElement.addEventListener('pointerleave', () => {
    pointerX = 0;
    pointerY = 0;
    queuePosition();
  });
  window.addEventListener('scroll', queuePosition, { passive: true });
  window.addEventListener('resize', queuePosition, { passive: true });
  motion.addEventListener('change', () => {
    pulse?.cancel();
    pointerX = 0;
    pointerY = 0;
    queuePosition();
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      window.cancelAnimationFrame(frame);
      frame = 0;
      pulse?.cancel();
    } else queuePosition();
  });
  window.triPilotScene.update({ stage: 0, step: 0, complete: false });
})();
