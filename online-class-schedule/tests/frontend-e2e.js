const { chromium } = require('playwright');
// usage: node frontend-e2e.js ./online-class-schedule/index.html   (needs: npm i playwright)
const path = require('path');
const URL = 'file://' + path.resolve(process.argv[2] || './index.html');
const results = [];
function rec(name, ok, info) { results.push({ name, ok, info: info || '' }); console.log((ok ? 'PASS ' : 'FAIL ') + name + (info ? '  -> ' + info : '')); }

(async () => {
  const b = await chromium.launch();
  async function fresh(w = 1280, h = 900) {
    const ctx = await b.newContext({ viewport: { width: w, height: h } });
    const p = await ctx.newPage();
    p.msgs = []; p.errs = [];
    p.on('dialog', d => { p.msgs.push(d.message()); d.accept(); });
    p.on('pageerror', e => p.errs.push(e.message));
    await p.goto(URL);
    return p;
  }
  async function login(p, email, pw) {
    await p.fill('input[type=email]', email);
    await p.fill('input[type=password]', pw);
    await p.click('.login-form .btn, button[type=submit]');
    await p.waitForTimeout(150);
  }
  const ACCTS = [
    ['student@kbtu.kz','student123','student'],['a.sadvakassova@kbtu.kz','student123','student'],
    ['m.zhaksybekova@kbtu.kz','student123','student'],['a.kim@kbtu.kz','student123','student'],
    ['d.omarov@kbtu.kz','student123','student'],['a.tleuov@kbtu.kz','student123','student'],
    ['teacher@kbtu.kz','teacher123','teacher'],['timur.akhmetov@kbtu.kz','teacher123','teacher'],
    ['olga.ivanova@kbtu.kz','teacher123','teacher'],['admin@kbtu.kz','admin123','admin']];

  // independent GPA expectation
  const GP = {"A":4,"A-":3.67,"B+":3.33,"B":3,"B-":2.67,"C+":2.33,"C":2,"C-":1.67,"D+":1.33,"D":1,"F":0};
  const CRED = [[5,3,3,5,2],[5,5,3,3,2],[5,4,4,3,2],[4,3,3,5,3],[5,4,4,4,3],[5,5,3,4,3]];
  const G = {
    'student@kbtu.kz':[["A-","A","B+","B","A"],["A","B+","A-","B","A"],["A","B+","B","A-","A"],["B+","A","B","A-","B+"]],
    'a.sadvakassova@kbtu.kz':[["A","A","A-","A","A"],["A","A-","A","A","A"],["A","A","A-","A","A"],["A-","A","A","A","A-"],["A","A-","A","B+","A"],["A","A","A-","A","A"]],
    'm.zhaksybekova@kbtu.kz':[["B","A-","B","C+","A"],["B-","C","B","B","A-"],["C+","F","C","B","A"],["B","B+","C+","B-","B"]],
    'a.kim@kbtu.kz':[["B+","B","B+","B","A"],["B","B+","B","B-","A"],["B+","B","B+","B","A-"],["B","B+","B","B+","B"]],
    'd.omarov@kbtu.kz':[["A-","A","B+","A-","A"],["A","B+","A","A-","A"]],
    'a.tleuov@kbtu.kz':[]};
  function exp(email){ let pts=0,cr=0,earned=0; G[email].forEach((row,i)=>row.forEach((g,k)=>{const c=CRED[i][k];pts+=GP[g]*c;cr+=c;if(g!=='F')earned+=c;})); return {gpa:cr?(pts/cr).toFixed(2):'—',earned}; }

  // 1. all accounts log in and see the dashboard page
  for (const [e,pw,role] of ACCTS) {
    const p = await fresh();
    await login(p, e, pw);
    const ok = await p.evaluate(() => !!document.querySelector('.header .user-info'));
    let info = '';
    let good = ok && p.errs.length === 0;
    if (good) {
      await p.evaluate(() => navigate('student'));
      if (role === 'student') {
        const v = await p.evaluate(() => [...document.querySelectorAll('.sd-stats .stat-number')].map(x=>x.textContent.trim()));
        const x = exp(e);
        good = v[0] === x.gpa && v[1] === String(x.earned);
        info = `GPA ${v[0]} (expected ${x.gpa}), earned ${v[1]} (expected ${x.earned})`;
      } else {
        const rows = await p.evaluate(() => document.querySelector('.sd-fields').textContent.replace(/\s+/g,' '));
        good = /Position/.test(rows) && /Department/.test(rows);
        info = 'staff profile rows: ' + (good ? 'ok' : rows);
      }
    }
    rec('login+dashboard ' + e, good, info + (p.errs.length ? ' JSERR ' + p.errs[0] : ''));
    await p.context().close();
  }

  // 2. wrong password lockout
  { const p = await fresh();
    for (let i=0;i<3;i++){ await login(p,'student@kbtu.kz','wrong'+i); }
    await login(p,'student@kbtu.kz','student123');
    const logged = await p.evaluate(() => !!document.querySelector('.header .user-info'));
    rec('lockout after 3 wrong passwords blocks even correct password', !logged);
    await p.context().close(); }

  // 3. every course: default registration should save the course's REAL day/time
  { const p = await fresh();
    const courses = await p.evaluate(() => CourseAPI.getAll().map(c => ({id:c.id,code:c.code,day:c.day,start:c.start,end:c.end,instructor:c.instructor})));
    const bad = [];
    for (const c of courses) {
      const q = await fresh();
      await login(q,'d.omarov@kbtu.kz','student123');
      await q.evaluate(id => { openCourse(id); }, c.id);
      await q.evaluate(id => registerCourse(id), c.id);
      const sec = await q.evaluate(([email,id]) => CourseAPI.getSection(email,id), ['d.omarov@kbtu.kz', c.id]);
      const regd = await q.evaluate(id => CourseAPI.getRegisteredIds('d.omarov@kbtu.kz').includes(id), c.id);
      if (!regd || sec.day !== c.day || sec.start !== c.start || sec.end !== c.end)
        bad.push(`${c.code}: registered=${regd} saved ${sec.day} ${sec.start}-${sec.end}, real ${c.day} ${c.start}-${c.end}`);
      await q.context().close();
    }
    rec('default registration keeps the real day/time for all ' + courses.length + ' courses', bad.length === 0, bad.join(' | '));
    await p.context().close(); }

  // 4. overlap detection, duplicate, seats, wrong instructor, teacher cannot register
  { const p = await fresh();
    await login(p,'a.kim@kbtu.kz','student123');
    const r = await p.evaluate(() => {
      const out = {};
      const all = CourseAPI.getAll();
      const a = all[0];
      const same = all.find(c => c.id !== a.id && c.day === a.day && c.start === a.start);
      out.first = CourseAPI.register('a.kim@kbtu.kz', a.id, {instructor:a.instructor, day:a.day, start:a.start, end:a.end});
      out.dup = CourseAPI.register('a.kim@kbtu.kz', a.id, {instructor:a.instructor, day:a.day, start:a.start, end:a.end});
      out.sameSlotExists = !!same;
      if (same) out.overlap = CourseAPI.register('a.kim@kbtu.kz', same.id, {instructor:same.instructor, day:same.day, start:same.start, end:same.end});
      // overlap via the picker: pick another course and force it into course a's slot
      const other = all.find(c => c.id !== a.id && c.id !== (same && same.id) && c.day !== a.day);
      out.forced = CourseAPI.register('a.kim@kbtu.kz', other.id, {instructor:other.instructor, day:a.day, start:a.start, end:a.end});
      // partial overlap (13:00-14:50 vs 14:00-15:50)
      out.credits = CourseAPI.getTotalCredits('a.kim@kbtu.kz');
      out.wrongInstr = CourseAPI.canRegister('d.omarov@kbtu.kz', all[5].id, {instructor: all[6].instructor, day: all[5].day, start: all[5].start, end: all[5].end});
      return out;
    });
    rec('first registration works', r.first.success);
    rec('duplicate registration rejected', !r.dup.success && r.dup.error === 'err.alreadyRegistered');
    rec('same-slot course rejected (err.conflict)', !r.sameSlotExists || (!r.overlap.success && r.overlap.error === 'err.conflict'), r.sameSlotExists ? '' : 'no pair in data');
    rec('forced picker slot overlapping an existing course is rejected', !r.forced.success && r.forced.error === 'err.conflict', JSON.stringify(r.forced));
    rec('choosing a different instructor is rejected', !r.wrongInstr.success, 'meaningless picker: ' + JSON.stringify(r.wrongInstr));
    await p.context().close(); }


  // 4b. partial overlap / adjacent slots / preselected option equals real time
  { const p = await fresh();
    await login(p,'a.kim@kbtu.kz','student123');
    const r = await p.evaluate(() => {
      const all = CourseAPI.getAll(); const me = 'a.kim@kbtu.kz';
      const a = all[0], b = all[1], c = all[2];
      const mk = (x, day, start, end) => ({instructor:x.instructor, day, start, end});
      CourseAPI.register(me, a.id, mk(a,'mon','13:00','14:50'));
      return {
        partial: CourseAPI.register(me, b.id, mk(b,'mon','14:00','15:50')),
        adjacent: CourseAPI.register(me, c.id, mk(c,'mon','14:50','15:40')),
        otherDay: CourseAPI.register(me, b.id, mk(b,'tue','13:00','14:50'))
      };
    });
    rec('partial overlap 13:00-14:50 vs 14:00-15:50 rejected', !r.partial.success && r.partial.error === 'err.conflict');
    rec('back-to-back slots (14:50 start after 14:50 end) allowed', r.adjacent.success, JSON.stringify(r.adjacent));
    rec('same time on another day allowed', r.otherDay.success);
    await p.context().close(); }
  { const p = await fresh();
    await login(p,'d.omarov@kbtu.kz','student123');
    const bad = [];
    for (const id of [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21]) {
      await p.evaluate(i => { selectedCourseId = i; navigate('details'); }, id);
      const m = await p.evaluate(i => { const c = CourseAPI.getById(i); return { sel: document.getElementById('sectionTime').value, want: c.start + '|' + c.end,
         instrDisabled: document.getElementById('sectionInstructor').disabled, opts: document.getElementById('sectionInstructor').options.length }; }, id);
      if (m.sel !== m.want) bad.push('course ' + id + ' preselects ' + m.sel + ' not ' + m.want);
      if (!m.instrDisabled || m.opts !== 1) bad.push('course ' + id + ' instructor select not fixed');
    }
    rec('details page preselects the real time + fixed instructor for all 21 courses', bad.length === 0, bad.join(' | '));
    await p.context().close(); }

  // 5. seats: fill a course and try to register
  { const p = await fresh();
    await login(p,'d.omarov@kbtu.kz','student123');
    const r = await p.evaluate(() => {
      const c = CourseAPI.getById(21);
      const data = JSON.parse(localStorage.getItem(REGISTRATIONS_KEY) || '{}');
      for (let i = 0; i < c.seats; i++) data['fake'+i+'@x.kz'] = [21];
      localStorage.setItem(REGISTRATIONS_KEY, JSON.stringify(data));
      return { left: CourseAPI.getSeatsLeft(21), res: CourseAPI.register('d.omarov@kbtu.kz', 21, {instructor:c.instructor, day:c.day, start:c.start, end:c.end}) };
    });
    rec('full course rejects registration', r.left === 0 && !r.res.success && r.res.error === 'err.noSeats', JSON.stringify(r));
    await p.context().close(); }

  // 6. UI flow: register then unregister, credits and my courses
  { const p = await fresh();
    await login(p,'a.kim@kbtu.kz','student123');
    await p.evaluate(() => { openCourse(1); });
    await p.evaluate(() => registerCourse(1));
    const my = await p.evaluate(() => CourseAPI.getRegisteredIds('a.kim@kbtu.kz'));
    rec('UI register -> my courses', my.includes(1) && p.msgs.some(m => /regist|записан|тіркел/i.test(m)), p.msgs.join(' | '));
    await p.evaluate(() => unregisterCourse(1));
    const my2 = await p.evaluate(() => CourseAPI.getRegisteredIds('a.kim@kbtu.kz'));
    rec('UI unregister', !my2.includes(1));
    await p.context().close(); }

  // 7. teacher / admin cannot register
  for (const [e,pw] of [['teacher@kbtu.kz','teacher123'],['admin@kbtu.kz','admin123']]) {
    const p = await fresh(); await login(p,e,pw);
    await p.evaluate(() => { selectedCourseId = 1; });
    await p.evaluate(() => registerCourse(1));
    const my = await p.evaluate(email => CourseAPI.getRegisteredIds(email), e);
    rec('role cannot register: ' + e, my.length === 0);
    await p.context().close(); }

  // 8. new user: sign up through the form, survives reload, can log in
  { const p = await fresh();
    await p.evaluate(() => showRegister());
    await p.fill('input[name=name]', 'Test Student');
    await p.fill('input[name=studentId]', '25B061999');
    await p.fill('input[name=email]', 'new.user@kbtu.kz');
    await p.fill('input[name=password]', 'secret123');
    await p.click('form button[type=submit], .login-form .btn');
    await p.waitForTimeout(200);
    await p.reload();
    await login(p, 'new.user@kbtu.kz', 'secret123');
    const ok = await p.evaluate(() => !!document.querySelector('.header .user-info'));
    rec('new account persists after reload and can log in', ok, p.msgs.join(' | '));
    if (ok) { await p.evaluate(() => navigate('student'));
      const t = await p.evaluate(() => document.querySelector('.sd-fields').textContent.replace(/\s+/g,' '));
      rec('new student dashboard derives year from ID (25B -> Year 2)', /Year 2/.test(t), t); }
    await p.context().close(); }

  // 9. languages + mobile no overflow on every page
  for (const w of [1280, 375, 320]) {
    const p = await fresh(w, 800);
    await login(p,'student@kbtu.kz','student123');
    const bad = [];
    for (const lang of ['kk','ru','en']) for (const page of ['dashboard','courses','mycourses','schedule','student']) {
      await p.evaluate(([l,pg]) => { setLanguage(l); navigate(pg); }, [lang,page]);
      const m = await p.evaluate(() => ({ sw: document.documentElement.scrollWidth, w: innerWidth, key: /\b(sd|nav|err|dash|sched|course|section)\.[a-zA-Z]+/.test(document.body.innerText),
        nameVis: (() => { const u=document.querySelector('.header-right .user-info'); if(!u) return false; const r=u.getBoundingClientRect(); return getComputedStyle(u).display!=='none' && r.width>0 && r.right<=innerWidth+1 && r.left>=0; })() }));
      if (m.sw > m.w) bad.push(`${lang}/${page} overflow ${m.sw}>${m.w}`);
      if (m.key) bad.push(`${lang}/${page} raw key`);
      if (!m.nameVis) bad.push(`${lang}/${page} name hidden`);
    }
    rec('no overflow / raw keys / hidden name @' + w + 'px', bad.length === 0 && p.errs.length === 0, bad.slice(0,6).join(' | ') + (p.errs[0]||''));
    await p.context().close();
  }

  const fails = results.filter(r => !r.ok).length;
  console.log(`\nTOTAL ${results.length}, FAILED ${fails}`);
  await b.close();
})();
