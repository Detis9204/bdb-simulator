import asyncio, sys
from playwright.async_api import async_playwright
W,H = int(sys.argv[1]), int(sys.argv[2])
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
        ctx = await b.new_context(viewport={'width':W,'height':H}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://127.0.0.1:8790/index.html'); await pg.wait_for_timeout(1000)
        await pg.tap('[data-b=goPlay]'); await pg.wait_for_timeout(400)
        await pg.screenshot(path=f'/tmp/mob/{W}_lobby.png')
        await pg.tap('[data-b=startLocal]'); await pg.wait_for_timeout(500)
        await pg.screenshot(path=f'/tmp/mob/{W}_mull.png')
        for _ in range(2):
            await pg.tap('[data-b=keep]'); await pg.wait_for_timeout(300)
        await pg.evaluate("""() => { const s=structuredClone(S),p=s.active,o=1-p;
          for (const q of [p,o]) for (let i=0;i<3;i++){ const c=s.players[q].deck.find(c=>DEFS[c.id].type==='unit'); s.players[q].deck.splice(s.players[q].deck.indexOf(c),1); s.field.push({uid:c.uid,id:c.id,owner:q,rested:i==2,damage:0,tmp:{power:0,hit:0,kw:[]},att:[]}); }
          for (const q of [p,o]) for (let i=0;i<4;i++){ const c=s.players[q].deck.shift(); s.players[q].energy.push({...c,rested:false}); }
          for (let i=0;i<3;i++) s.players[p].hand.push(s.players[p].deck.shift());
          S=s; render(); }""")
        await pg.wait_for_timeout(1500)
        await pg.screenshot(path=f'/tmp/mob/{W}_game.png')
        await pg.screenshot(path=f'/tmp/mob/{W}_gamefull.png', full_page=True)
        # 패 카드 누르기
        await pg.tap('.hand.me .handrow .card'); await pg.wait_for_timeout(400)
        await pg.screenshot(path=f'/tmp/mob/{W}_tap.png')
        await pg.tap('.log [data-s=card]'); await pg.wait_for_timeout(400)
        await pg.screenshot(path=f'/tmp/mob/{W}_sheet.png')
        dims = await pg.evaluate("() => ({sw: document.documentElement.scrollWidth, iw: innerWidth, sh: document.documentElement.scrollHeight})")
        print(dims, errs)
        await b.close()
asyncio.run(main())
