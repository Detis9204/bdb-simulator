// 같은 시드 + 같은 행동 → 같은 상태인지 (온라인 동기화 전제) 확인
const fs=require('fs');const code=fs.readFileSync((process.argv[2] || require('path').join(__dirname, '../simulator/index.html')),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const ctx={};new Function('ctx',code+'\nctx.Engine=Engine;ctx.DEFS=DEFS;ctx.DECKS=DECKS;')(ctx);
const {Engine,DEFS,DECKS}=ctx;
let pr=1; const pick=a=>a[(pr=(pr*48271)%2147483647)%a.length];
function play(seed, actionsIn){
  let s=Engine.newGame(DECKS.bocchi,DECKS.bocchi,seed); const acts=[];
  const act=a=>{s=Engine.apply(s,a);acts.push(a);};
  if(actionsIn){ for(const a of actionsIn) s=Engine.apply(s,a); return s; }
  let g=0;
  while(s.winner==null && g++<4000){
    const pd=s.pending;
    if(pd){const P=s.players[pd.player];
      if(pd.type==='mulligan')act({type:'MULLIGAN',redraw:true});
      else if(pd.type==='block'){const bl=s.field.filter(u=>u.owner===pd.player&&!u.rested&&u.uid!==pd.target);act({type:'BLOCK',blocker:bl.length?pick(bl).uid:null});}
      else if(pd.type==='shot'){const ts=Engine.targetsFor(s,pd.player,DEFS[pd.card.id]);act({type:'SHOT',play:true,target:ts.length?pick(ts):undefined});}
      else if(pd.type==='discard')act({type:'DISCARD',uid:P.hand[0].uid});
      else if(pd.type==='territory')act({type:'TERRITORY',open:P.energy.filter(e=>!e.rested).length>=pd.cost});
      else if(pd.type==='bright')act({type:'BRIGHT',discard:null});
      else if(pd.type==='scout')act({type:'SCOUT',top:[],bottom:P.deck.slice(0,pd.n).map(c=>c.uid)});
      else if(pd.type==='seika')act({type:'SEIKA',uid:null});
      else if(pd.type==='flashback')act({type:'FLASHBACK',uid:Engine.flashTargets(s,pd.player)[0]});
      continue;}
    const p=s.active,P=s.players[p];
    if(s.phase==='main'){ if(!P.energySet&&P.hand.length)act({type:'SET_ENERGY',uid:P.hand[0].uid});
      const pl=s.players[p].hand.filter(c=>Engine.canPay(s.players[p],DEFS[c.id])&&!Engine.needsTarget(DEFS[c.id]));
      if(pl.length)act({type:'PLAY',uid:pl[0].uid}); if(!s.pending&&s.phase==='main')act({type:'NEXT_PHASE'});}
    else if(s.phase==='attack'){const r=Engine.unitsOf(s,p).filter(u=>Engine.canAttack(s,u));
      if(r.length)act({type:'ATTACK',attacker:r[0].uid,target:pick(Engine.attackTargets(s,p,r[0].uid))});else act({type:'NEXT_PHASE'});}
  }
  return {s,acts};
}
let ok=0;
for(let k=0;k<50;k++){
  const seed=1000+k; const a=play(seed); const b=play(seed,JSON.parse(JSON.stringify(a.acts)));
  if(JSON.stringify(a.s)!==JSON.stringify(b)) throw new Error('불일치 seed '+seed);
  ok++;
}
const x=Engine.newGame(DECKS.bocchi,DECKS.bocchi,5), y=Engine.newGame(DECKS.bocchi,DECKS.bocchi,6);
console.log('재현 일치', ok, '판 / 시드가 다르면 덱 순서도 다름:', JSON.stringify(x.players[0].deck)!==JSON.stringify(y.players[0].deck));
