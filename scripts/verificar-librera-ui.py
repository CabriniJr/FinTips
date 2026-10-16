#!/usr/bin/env python3
"""UI da fonte automática com transporte/guarda simulados. Job real: instrumentação."""
import asyncio,json,mimetypes,shutil,sys
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fintips.librera import merge_reading
from fintips.reading import pacing
from playwright.async_api import async_playwright,expect
NOW=1792152000000
EMPTY=dict(schema_version=1,vida=dict(schema_version=1,tarefas=[],registros=[],planos=[],medidas=[]),leitura=dict(schema_version=1,livros=[]),caderno=dict(schema_version=1,assets=[],relacoes=[],aplicacoes=[]))
FIRST=merge_reading(EMPTY['leitura'],{'Livro Sintético.epub':dict(p=.25,t=NOW-86400000,pt='PAGE_CANARY')},'principal',NOW,'UTC')['leitura']
SECOND=merge_reading(FIRST,{'Livro Sintético.epub':dict(p=.4,t=NOW-1000)},'principal',NOW,'UTC')['leitura']

async def main():
 out=ROOT/'kotlin/conector/build/reports/librera-ui';out.mkdir(parents=True,exist_ok=True)
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(executable_path=shutil.which('chromium') or shutil.which('google-chrome'),headless=True,args=['--no-sandbox'])
  for width in [320,390,768]:
   context=await browser.new_context(viewport=dict(width=width,height=844),timezone_id='UTC',reduced_motion='reduce')
   await context.add_init_script('''(() => {
    const seed=SEED;
    localStorage.setItem('fintips.client.v1',JSON.stringify(seed));
    window.__state=null;window.__source={conectada:false};
    window.FinTipsState={
      status:()=>JSON.stringify({result:{existe:!!window.__state,...(window.__state?{revisao:window.__state.revisao,revisao_bundle:window.__state.revisao_bundle}:{}),librera:window.__source}}),
      inicializar:(raw)=>{const i=JSON.parse(raw);window.__state={revisao:1,revisao_bundle:1,revisao_chat:1,bundle:i.bundle,chat:i.chat};return JSON.stringify({result:window.__state});},
      snapshot:()=>JSON.stringify({result:window.__state}),
      salvar:(raw)=>{const i=JSON.parse(raw),s=window.__state,k='revisao_'+i.chave;if(s[k]!==i.revisao)return JSON.stringify({error:'stale'});s[i.chave]=i.valor;s[k]++;s.revisao++;return JSON.stringify({result:s});},
    };
    window.FinTipsMotor={postMessage(raw){window.nativeRequest(raw).then(data=>window.FinTipsMotor.onmessage({data}));}};
   })();'''.replace('SEED',json.dumps(EMPTY,ensure_ascii=False)))
   page=await context.new_page();errors=[];hosts=set()
   page.on('pageerror',lambda e:errors.append(str(e)))
   async def route(r):
    u=urlparse(r.request.url);hosts.add(u.hostname);assert u.hostname=='appassets.androidplatform.net'
    file=ROOT/'fintips/web'/u.path.lstrip('/')
    await r.fulfill(body=file.read_bytes(),content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
   await context.route('**/*',route)
   async def native(raw):
    r=json.loads(raw);op=r['operation'];i=r['input']
    if op=='servidor.status':result={'ativo':False}
    elif op=='librera.status':result=await page.evaluate('window.__source')
    elif op in ('librera.conectar','librera.sincronizar'):
     reading=FIRST if op.endswith('conectar') else SECOND
     await page.evaluate('''([reading,now])=>{const s=window.__state;s.bundle.leitura=reading;s.revisao++;s.revisao_bundle++;window.__source={conectada:true,perfil:'principal',agendada:true,estado:'atualizada',sucesso_ms:now};dispatchEvent(new Event('fintips:librera-updated'));}''',[reading,NOW])
     result={'status':'selecao_simulada'}
    elif op=='librera.desconectar':
     await page.evaluate("window.__source={conectada:false};dispatchEvent(new Event('fintips:librera-updated'))")
     result={'conectada':False}
    elif op=='leitura.ritmo':result=pacing(i['points'],today=i['today'],deadline=i.get('deadline'),reading_days=i.get('reading_days'))
    else:raise AssertionError(op)
    return json.dumps({'id':r['id'],'result':result})
   await context.expose_function('nativeRequest',native)
   await page.goto('https://appassets.androidplatform.net/index.html#vida/INT')
   await page.get_by_role('button',name='Conectar arquivo do Librera').click()
   await expect(page.get_by_role('heading',name='Livro Sintético',exact=True)).to_be_visible()
   await expect(page.locator('.reading-book')).to_contain_text('25%')
   await page.get_by_role('button',name='Verificar agora',exact=True).click()
   await expect(page.locator('.reading-book')).to_contain_text('40%')
   assert await page.evaluate("JSON.parse(localStorage.getItem('fintips.client.v1')).leitura.livros.length===0")
   await page.get_by_role('button',name='Desconectar',exact=True).click()
   await expect(page.get_by_role('button',name='Conectar arquivo do Librera')).to_be_visible()
   await expect(page.locator('.reading-book')).to_contain_text('40%')
   assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
   await page.screenshot(path=str(out/f'librera-{width}.png'),full_page=True)
   assert not errors,errors
   assert hosts=={'appassets.androidplatform.net'}
   print(f'UI {width}: migração, conectar, progresso automático, legado intacto e desconectar preservando histórico OK (bridge simulado).')
   await context.close()
  await browser.close()

if __name__=='__main__':asyncio.run(main())
