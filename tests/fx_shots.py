import asyncio, json
from playwright.async_api import async_playwright
db = json.load(open('/home/claude/bdb-simulator/simulator/cards_db.json'))['defs']
trig0 = [k for k,d in db.items() if d.get('type')=='unit' and any(a.get('k')=='auto' and a.get('on')=='attackStart' and a.get('src')=='me' and not a.get('if') and not a.get('cost') for a in d.get('ab',[]))]
seen=set(); trig=[]
for k in trig0:
    if db[k]['name'] not in seen: seen.add(db[k]['name']); trig.append(k)
trig=trig[:2]
print('trig cards', trig, [db[k]['name'] for k in trig])
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
        pg = await b.new_page(viewport={'width':1500,'height':860})
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://127.0.0.1:8790/index.html'); await pg.wait_for_timeout(800)
        await pg.evaluate("localStorage.setItem('bdb-fx','normal')")
        await pg.click('[data-b=goPlay]'); await pg.click('[data-b=startLocal]'); await pg.wait_for_timeout(1500)
        await pg.click('[data-b=keep]'); await pg.wait_for_timeout(300); await pg.click('[data-b=keep]'); await pg.wait_for_timeout(1500)
        await pg.evaluate("window.__db=" + json.dumps({k:db[k] for k in trig}))
        await pg.evaluate("""(tr) => { for (const k of tr) if(!DEFS[k]) def(k,Object.assign({},__db[k],{id:k}));
          const s=structuredClone(S),p=s.active,o=1-p; s.pending=null;
          const take=(q)=>{const c=s.players[q].deck.find(c=>DEFS[c.id].type==='unit'&&!DEFS[c.id].ab?.length); s.players[q].deck.splice(s.players[q].deck.indexOf(c),1); return c;};
          const c1=take(p); s.field.push({uid:'A1',id:c1.id,owner:p,rested:false,damage:0,tmp:{power:20000,hit:0,kw:[]},att:[]});
          const c2=take(o); s.field.push({uid:'B1',id:c2.id,owner:o,rested:true,damage:0,tmp:{power:0,hit:0,kw:[]},att:[]});
          tr.forEach((k,i)=>s.field.push({uid:'T'+i,id:k,owner:p,rested:false,damage:0,tmp:{power:0,hit:0,kw:[]},att:[]}));
          S=s; Fx.seen=S.fxSeq||0; render(); }""", trig)
        await pg.wait_for_timeout(500)
        await pg.click('[data-b=next]'); await pg.wait_for_timeout(1300)
        await pg.screenshot(path='/tmp/mob/fx_order.png')
        print('pending', await pg.evaluate("S.pending&&S.pending.type"))
        if await pg.evaluate("S.pending&&S.pending.type==='order'"):
            await pg.click('[data-b=order][data-i="1"]'); await pg.wait_for_timeout(200)
            await pg.screenshot(path='/tmp/mob/fx_trig.png')
            await pg.wait_for_timeout(2500)
        print('log', await pg.evaluate("S.log.slice(-6).map(l=>l.m)"))
        await pg.evaluate("dispatch({type:'ATTACK',attacker:'A1',target:'B1'})")
        await pg.wait_for_timeout(350); await pg.screenshot(path='/tmp/mob/fx_atk.png')
        if await pg.evaluate("S.pending&&S.pending.type==='block'"):
            await pg.wait_for_timeout(900)
            await pg.evaluate("dispatch({type:'BLOCK',blocker:null})")
        await pg.wait_for_timeout(450); await pg.screenshot(path='/tmp/mob/fx_battle.png')
        await pg.wait_for_timeout(1050); await pg.screenshot(path='/tmp/mob/fx_dmg.png')
        await pg.wait_for_timeout(400); await pg.screenshot(path='/tmp/mob/fx_gone.png')
        print(errs); await b.close()
asyncio.run(main())
