/* TeamFlow 스프린트 4개 생성 + 에픽 13개 배정
 *
 * 왜 스크립트인가: 관리자가 토큰의 스프린트 관리 권한을 꺼두면 API 로 스프린트를 만들 수 없다.
 *   꺼진 상태의 POST /api/sprints?projectId=84 는 403 이다(2026-08-28 에는 401 이었다).
 *   권한을 켜면 토큰으로도 되므로, 이 스크립트는 켤 수 없을 때의 대안이다.
 *   이슈 쪽은 토큰으로 CRUD 가 모두 된다(2026-08-30 확인). PUT 은 id 를 쿼리스트링에 넣는다.
 *   그래서 로그인한 브라우저 세션에서 실행한다. 이 페이지가 쓰는 API를 그대로 부른다.
 *
 * 쓰는 법
 *   1. https://jira-for-me.vercel.app 에 로그인하고 SKN32_FINAL_TEAM4 를 연다.
 *   2. F12 → Console 탭.
 *   3. 이 파일 전체를 붙여넣고 Enter.
 *   4. 끝나면 화면을 새로고침한다.
 *
 * 안전장치
 *   - 지우는 동작이 없다. 만들고 배정만 한다.
 *   - 같은 이름의 스프린트가 이미 있으면 새로 만들지 않고 그것을 쓴다. 두 번 돌려도 안전하다.
 *   - 에픽 수정은 기존 값을 그대로 다시 보내고 sprint 만 바꾼다. 다른 필드가 지워지지 않는다.
 *   - 이미 스프린트가 배정된 이슈는 건드리지 않는다.
 */
(async () => {
  const PROJECT_ID = 84;                    // SKN32_FINAL_TEAM4
  const SPRINTS = [
    { name: 'S1 기반 계약 고정', start: '2026-08-28', end: '2026-09-15',
      goal: 'Core 계약과 stub 고정. 중간발표(9/15)로 끝난다.' },
    { name: 'S2 도메인 팀 구현', start: '2026-09-16', end: '2026-09-30',
      goal: 'CS Pack 두 팀과 진입 경로. 추석 구간을 포함한다.' },
    { name: 'S3 평가와 통합', start: '2026-10-01', end: '2026-10-14',
      goal: '골든셋·harness·통계와 Commerce Ops 통합.' },
    { name: 'S4 배포와 시연', start: '2026-10-15', end: '2026-10-26',
      goal: '운영 콘솔·Composer·산출물. 최종발표(10/26)로 끝난다.' },
  ];

  const api = async (path, options = {}) => {
    const opts = { method: 'GET', credentials: 'same-origin', ...options, headers: {} };
    if (opts.body !== undefined && typeof opts.body !== 'string') {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(path, opts);
    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) throw new Error((data && data.error) || `요청 실패 (${res.status})`);
    return data;
  };

  const state0 = await api(`/api/state?projectId=${PROJECT_ID}`);
  const before = (state0.sprints || []).map(s => s.name);
  console.log(`현재 스프린트 ${before.length}개:`, before.length ? before : '(없음)');

  // ── 1) 스프린트 생성 (이름이 같으면 건너뛴다) ──────────────────────
  let created = 0, reused = 0;
  for (const s of SPRINTS) {
    if (before.includes(s.name)) { reused++; console.log(`  = 이미 있음  ${s.name}`); continue; }
    await api(`/api/sprints?projectId=${PROJECT_ID}`, { method: 'POST', body: s });
    created++;
    console.log(`  + 생성       ${s.name}  (${s.start} ~ ${s.end})`);
    await new Promise(r => setTimeout(r, 300));
  }

  // ── 2) 에픽에 스프린트 배정 ────────────────────────────────────────
  const state = await api(`/api/state?projectId=${PROJECT_ID}`);
  const idByName = Object.fromEntries((state.sprints || []).map(s => [s.name, s.id]));
  const sprintOf = { S1: idByName[SPRINTS[0].name], S2: idByName[SPRINTS[1].name],
                     S3: idByName[SPRINTS[2].name], S4: idByName[SPRINTS[3].name] };

  // 에픽 제목이 "E01 …" 로 시작한다. 설계 문서의 목표 스프린트와 같은 배정이다.
  const PLAN = { E01: 'S1', E02: 'S1', E03: 'S1', E04: 'S1',
                 E05: 'S2', E06: 'S2', E07: 'S2', E08: 'S2', E10: 'S2',
                 E09: 'S3', E11: 'S3',
                 E12: 'S4', E13: 'S4' };

  let assigned = 0, skipped = 0, missing = [];
  for (const [eid, key] of Object.entries(PLAN)) {
    const iss = (state.issues || []).find(i => i.type === 'epic' && (i.title || '').startsWith(eid + ' '));
    if (!iss) { missing.push(eid); continue; }
    if (iss.sprint) { skipped++; console.log(`  = 배정돼 있음 ${iss.key} ${iss.title}`); continue; }
    const target = sprintOf[key];
    if (!target) { missing.push(eid + '(스프린트 없음)'); continue; }

    // ★기존 값을 그대로 다시 보낸다. PUT 은 전체 교체라 빠뜨리면 그 필드가 지워진다.
    const payload = {
      title: iss.title, type: iss.type, priority: iss.priority, status: iss.status,
      assignee: iss.assignee || '', sprint: target, version: iss.version || '',
      component: iss.component || '', parent: iss.parent || '',
      start: iss.start || '', due: iss.due || '',
      labels: iss.labels || [], points: iss.points || 0, desc: iss.desc || '',
    };
    await api(`/api/issues?id=${encodeURIComponent(iss.id)}&projectId=${PROJECT_ID}`,
              { method: 'PUT', body: payload });
    assigned++;
    console.log(`  → 배정       ${iss.key} ${iss.title}  ⇒ ${key}`);
    await new Promise(r => setTimeout(r, 300));
  }

  console.log(`\n스프린트: 생성 ${created} · 기존 재사용 ${reused}`);
  console.log(`에픽 배정: ${assigned}건 · 이미 배정 ${skipped}건`);
  if (missing.length) console.log('★못 찾은 에픽:', missing.join(', '));
  console.log('화면을 새로고침하면 반영됩니다.');
})();
