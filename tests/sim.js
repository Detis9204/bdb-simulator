// 무작위 자동 대전으로 엔진 검증 (브라이트 규칙)
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');
const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const ctx = {};
new Function('ctx', code + '\nctx.Engine=Engine;ctx.DEFS=DEFS;ctx.RED=DECK_RED;ctx.BLUE=DECK_BLUE;ctx.DECKS=DECKS;ctx.RULES=RULES;')(ctx);
const { Engine, DEFS, RED, BLUE, RULES, DECKS } = ctx;
const SAMPLES = Object.keys(DECKS).filter(k => DECKS[k].sample);
const PAIRS = [['bocchi','bocchi'],['bocchi','red'],['blue','bocchi'],['red','blue'], null, null, null, null];
const pick = a => a[Math.floor(Math.random() * a.length)];

function check(s) {
  for (let p = 0; p < 2; p++) {
    const P = s.players[p];
    const n = P.deck.length + P.hand.length + P.life.length + P.energy.length + P.drop.length + (P.remove||[]).length
      + s.field.filter(u => u.owner === p).length + (s.pending?.type === 'shot' && s.pending.player === p ? 1 : 0);
    if (n !== s.size[p]) throw new Error(`카드 수 불일치 P${p + 1}: ${n} / ${s.size[p]}`);
  }
  for (const u of s.field) { const pw = Engine.power(s, u); if (pw <= 0 || u.damage >= pw) throw new Error('파괴되지 않은 유닛'); }
  if (s.winner == null && !s.pending && (s.queue.length || s.conts.length)) throw new Error('처리 대기열이 남은 채 멈춤');
}

const st = { games: 0, turns: 0, wins: [0, 0], events: {} };
const ev = k => st.events[k] = (st.events[k] || 0) + 1;
console.log('덱 검사:', Object.fromEntries(Object.entries(DECKS).map(([k,d])=>[k,Engine.validateDeck(d)])));
for (let g = 0; g < 1200; g++) {
  const pr = PAIRS[g % PAIRS.length] || [pick(SAMPLES), pick(SAMPLES)];
  let s = Engine.newGame(DECKS[pr[0]], DECKS[pr[1]]);
  const size = pr.map(k => DECKS[k].main.reduce((t, [, n]) => t + n, 0));
  s.size = size;
  let steps = 0;
  const act = a => { s = Engine.apply(s, a); s.size = size; check(s); };
  const ALL = s2 => { const r = []; for (let q = 0; q < 2; q++) for (const z of ['hand','drop','energy','life','deck']) for (const c of s2.players[q][z]) r.push(c.uid); s2.field.forEach(u => r.push(u.uid)); return r; };
  const OPS = [['move','hand'],['move','drop'],['move','energy'],['move','life'],['move','deckTop'],['move','deckBottom'],['move','field'],['rest'],['pow'],['hitmod'],['dmg'],['draw'],['shuffle'],['lifeFromDeck'],['lifeToHand'],['move','remove']];
  while (s.winner == null) {
    if (++steps > 8000) throw new Error('게임이 끝나지 않음');
    const pd = s.pending;
    if (pd) {
      ev(pd.type);
      const P = s.players[pd.player];
      if (pd.type === 'mulligan') act({ type: 'MULLIGAN', redraw: Math.random() < .3 });
      else if (pd.type === 'block') {
        const bl = s.field.filter(u => u.owner === pd.player && !u.rested && u.uid !== pd.target);
        act({ type: 'BLOCK', blocker: Math.random() < .5 ? pick(bl).uid : null });
      } else if (pd.type === 'shot') {
        const d = DEFS[pd.card.id], ts = Engine.targetsFor(s, pd.player, d);
        act({ type: 'SHOT', play: Math.random() < .85, target: ts.length ? pick(ts) : undefined });
      } else if (pd.type === 'discard') act({ type: 'DISCARD', uid: pick(P.hand).uid });
      else if (pd.type === 'territory') {
        const can = P.energy.filter(e => !e.rested).length >= pd.cost;
        act({ type: 'TERRITORY', open: can && Math.random() < .9 });
      } else if (pd.type === 'bright') {
        const b = DEFS[Engine.findUnit(s, pd.uid).id].bright;
        const ok = P.hand.filter(c => DEFS[c.id].attr.some(a => b.attrs.includes(a)));
        // 일부러 틀린 카드도 시도
        const bad = P.hand.find(c => !ok.includes(c));
        if (bad) { try { Engine.apply(s, { type: 'BRIGHT', discard: bad.uid }); throw new Error('잘못된 브라이트가 통과됨'); } catch (e) { if (e.message.includes('통과')) throw e; } }
        act({ type: 'BRIGHT', discard: Math.random() < .8 ? pick(ok).uid : null });
      } else if (pd.type === 'scout') {
        const ids = P.deck.slice(0, pd.n).map(c => c.uid), top = [], bottom = [];
        for (const u of ids) (Math.random() < .5 ? top : bottom).push(u);
        act({ type: 'SCOUT', top, bottom });
      } else if (pd.type === 'seika') {
        if (pd.step === 'discard') act({ type: 'SEIKA', uid: Math.random() < .8 ? pick(P.hand).uid : null });
        else act({ type: 'SEIKA', uid: pick(Engine.seikaTargets(s, pd.player)) });
      } else if (pd.type === 'flashback') {
        act({ type: 'FLASHBACK', uid: Math.random() < .85 ? pick(Engine.flashTargets(s, pd.player)) : null });
      } else throw new Error('알 수 없는 선택: ' + pd.type);
      continue;
    }
    if (Math.random() < .04) {   // 수동 조작 무작위 시도
      const [op, to] = pick(OPS), a = { type: 'MANUAL', op, to, uid: pick(ALL(s)), p: Math.random() < .5 ? 0 : 1, v: pick([1000, -1000, 1, -1]) };
      try { act(a); ev('manual_' + op); } catch (e) { if (!/찾을 수|아닙니다|유닛만|비었|없습니다/.test(e.message)) throw e; }
      continue;
    }
    const p = s.active;
    if (s.phase === 'main') {
      { const Q = s.players[p]; if (!Q.energySet && Q.hand.length && Math.random() < .85) act({ type: 'SET_ENERGY', uid: pick(Q.hand).uid }); }
      for (let k = 0; k < 6 && !s.pending && s.winner == null; k++) {
        const Q = s.players[p];
        const playable = Q.hand.filter(c => Engine.canPay(Q, DEFS[c.id]));
        if (!playable.length) break;
        const c = pick(playable), d = DEFS[c.id], need = Engine.needsTarget(d), ts = Engine.targetsFor(s, p, d);
        if (need && !ts.length) continue;
        act({ type: 'PLAY', uid: c.uid, target: ts.length ? pick(ts) : undefined });
      }
      if (!s.pending && s.winner == null && s.phase === 'main') act({ type: 'NEXT_PHASE' });
    } else if (s.phase === 'attack') {
      const ready = Engine.unitsOf(s, p).filter(u => Engine.canAttack(s, u));
      const must = Engine.mustAttack(s);
      if (must.length) {
        // 버서크 상태로 턴 종료 시도는 막혀야 함
        try { Engine.apply(s, { type: 'NEXT_PHASE' }); throw new Error('버서크 무시가 통과됨'); } catch (e) { if (e.message.includes('통과')) throw e; ev('berserkBlocked'); }
        const u = must[0]; act({ type: 'ATTACK', attacker: u.uid, target: pick(Engine.attackTargets(s, p, u.uid)) });
      } else if (ready.length && Math.random() < .85) {
        const u = pick(ready); act({ type: 'ATTACK', attacker: u.uid, target: pick(Engine.attackTargets(s, p, u.uid)) });
      } else act({ type: 'NEXT_PHASE' });
    } else throw new Error('멈춘 상태: ' + s.phase);
  }
  for (const l of s.log) {
    if (l.m.includes('개방!')) ev('terrOpened');
    if (l.m.startsWith('브라이트!')) ev('brightDone');
    if (l.m.startsWith('버스트')) ev('burst');
    if (l.m.includes('블리츠')) ev('blitz');
    if (l.m.includes('레드 존')) ev('redzoneLog');
    if (l.m.startsWith('[드롭 시]')) ev('dropTrigger');
    if (l.m.startsWith('[배틀 시]')) ev('battleTrigger');
    if (l.m.includes('남은 데미지가 사라짐')) ev('damageCancelled');
    if (l.m.startsWith('[결속]')) ev('kesso');
    if (l.m.includes('드롭 존에서 패로')) ev('seikaRecovered');
    if (l.m.includes('라이프 맨 앞을 에너지로')) ev('flashbackDone');
    if (l.m.includes('효과로 드롭')) ev('destroyLE');
    if (l.m.includes('상대 턴이라')) ev('standOnOppTurn');
    if (/파워 -5000, 히트 -2/.test(l.m)) ev('debuff');
  }
  st.games++; st.turns += s.turnCount; st.wins[s.winner]++;
}
st.avgTurns = (st.turns / st.games).toFixed(1);
console.log(JSON.stringify(st, null, 1));
