#!/usr/bin/env python3
"""QA da UI com bridge simulado; persistência nativa é cobrada na instrumentação."""
import asyncio
import copy
import hashlib
import json
import mimetypes
from pathlib import Path
import shutil
import sys
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fintips.statement_context import statement_context, statement_views
from ouro_fluxos import ofx_flows, rows
from fintips.parsers.ofx import parse_ofx_text
from ouro_extratos import ofx
from playwright.async_api import async_playwright, expect

async def main():
    output=ROOT/'kotlin/conector/build/reports/extrato-ui'
    output.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(executable_path=shutil.which('chromium') or shutil.which('google-chrome'),headless=True,args=['--no-sandbox'])
        for width in [320,390,768]:
            files=[];calls=[];errors=[];hosts=set()
            def state():
                observed, flows = statement_views(files,'test')
                result={'contexto':observed,'fluxos':flows,'fontes':[]}
                for f in files:
                    stmt=parse_ofx_text(f['ofx'],salt='test')
                    result['fontes'].append({'ref':f['ref'],'inicio':stmt.period_start.isoformat(),'fim':stmt.period_end.isoformat(),'transacoes':len(stmt.transactions),'saldo_centavos':int(stmt.ledger_balance*100),'conciliacao':'nao_conferido','diferenca_centavos':None,'importado_em':1})
                return result
            async def native(raw):
                r=json.loads(raw);op=r['operation'];i=r['input'];calls.append(op)
                if op=='extrato.estado': result=state()
                elif op=='extrato.contexto': result=state()['contexto']
                elif op=='servidor.status': result={'ativo':False}
                elif op=='triagem.catalogo': result={'tipos':{}}
                elif op=='triagem.chave_status': result={'configurada':False}
                elif op=='triagem.cancelar': result={'status':'cancelado'}
                elif op=='extrato.importar':
                    try:
                        # Stub do transporte. Valida fonte antes de alterar sua cópia em memória.
                        entry={'ofx':i['ofx'],'saldo_inicial':i.get('saldo_inicial'),'ref':'fonte_'+hashlib.sha256(i['ofx'].encode()).hexdigest()}
                        index=next((n for n,f in enumerate(files) if f['ref']==entry['ref']),None)
                        next_files=copy.deepcopy(files)
                        if index is None: next_files.append(entry)
                        else: next_files[index]=entry
                        old=state()['contexto']['transacoes'];statement_context(next_files,'test')
                        files[:]=next_files;result={**state(),'duplicado':index is not None,'novas_transacoes':state()['contexto']['transacoes']-old}
                    except (ValueError,KeyError): return json.dumps({'id':r['id'],'error':'Arquivo recusado no teste.'})
                else: raise AssertionError(op)
                return json.dumps({'id':r['id'],'result':result})
            context=await browser.new_context(viewport={'width':width,'height':844},reduced_motion='reduce',timezone_id='UTC')
            async def route(r):
                u=urlparse(r.request.url);hosts.add(u.hostname);assert u.hostname=='appassets.androidplatform.net'
                file=ROOT/'fintips/web'/u.path.lstrip('/')
                await r.fulfill(body=file.read_bytes(),content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
            await context.route('**/*',route);await context.expose_function('nativeRequest',native)
            await context.add_init_script('window.FinTipsMotor={postMessage(raw){window.nativeRequest(raw).then(data=>window.FinTipsMotor.onmessage({data}));}};')
            page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            await page.goto('https://appassets.androidplatform.net/index.html#visao')
            raw=ofx([('a',1,'1000.00'),('b',2,'-250.00')]).encode()
            upload=page.get_by_label('Extrato OFX no aparelho')
            await upload.set_input_files({'name':'synthetic.ofx','mimeType':'application/x-ofx','buffer':raw})
            await page.get_by_role('button',name='Importar e registrar contexto').click()
            await expect(page.get_by_text('Extrato registrado no aparelho',exact=True)).to_be_visible()
            await expect(page.get_by_role('heading',name='2 movimentações no contexto')).to_be_visible()
            await upload.set_input_files({'name':'synthetic.ofx','mimeType':'application/x-ofx','buffer':raw})
            await page.get_by_role('button',name='Importar e registrar contexto').click()
            await expect(page.get_by_text('Este extrato já estava registrado',exact=True)).to_be_visible()
            assert len(files)==1
            await page.reload()
            await expect(page.get_by_role('heading',name='2 movimentações no contexto')).to_be_visible()
            await page.get_by_label('Extrato OFX no aparelho').set_input_files({'name':'invalid.ofx','mimeType':'application/x-ofx','buffer':b'invalid'})
            await page.get_by_role('button',name='Importar e registrar contexto').click()
            await expect(page.get_by_role('alert')).to_contain_text('Arquivo recusado')
            await expect(page.get_by_role('heading',name='2 movimentações no contexto')).to_be_visible()
            await page.locator('.bottom-nav a[href="#contexto"]').click()
            await expect(page.get_by_role('heading',name='2 movimentações disponíveis')).to_be_visible()
            await page.locator('a[href="#conversa"]').click()
            await expect(page.get_by_role('heading',name='2 movimentações disponíveis')).to_be_visible()
            await page.locator('.bottom-nav a[href="#visao"]').click()
            await expect(page.get_by_role('heading',name='2 movimentações no contexto')).to_be_visible()
            # O giro do investimento não pode ocupar os KPIs de recebimento/pagamento.
            flow_raw=ofx_flows(rows()).encode()
            await page.get_by_label('Extrato OFX no aparelho').set_input_files({'name':'flow-synthetic.ofx','mimeType':'application/x-ofx','buffer':flow_raw})
            await page.get_by_role('button',name='Importar e registrar contexto').click()
            await expect(page.get_by_role('heading',name='14 movimentações no contexto')).to_be_visible()
            flow_panel=page.get_by_label('Separação dos fluxos financeiros')
            await expect(flow_panel).to_contain_text('Recebimentos identificados')
            # synthetic.ofx has unknown memos: those 2 rows join the 6 pending.
            await expect(flow_panel.get_by_role('heading',name='8 movimentações a revisar')).to_be_visible()
            await expect(flow_panel.locator('.finance-primary')).to_contain_text('2.003,00')
            await expect(flow_panel.locator('.finance-primary')).to_contain_text('150,00')
            await expect(flow_panel).to_contain_text('1.200,00')
            gross=page.locator('.finance-gross')
            await expect(gross.locator('dl')).not_to_be_visible()
            await gross.locator('summary').click()
            await expect(gross).to_contain_text('Créditos brutos')
            await expect(gross.locator('dl')).to_be_visible()
            await gross.locator('summary').click()
            await page.reload()
            await expect(page.get_by_label('Separação dos fluxos financeiros').locator('.finance-primary')).to_contain_text('2.003,00')
            assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            await page.screenshot(path=str(output/f'financas-{width}.png'),full_page=True)
            assert not errors,errors
            assert hosts=={'appassets.androidplatform.net'}
            print(f'UI {width}: importação, repetição, reload, fonte inválida e contexto nas abas OK (bridge simulado).')
            await context.close()
        await browser.close()

if __name__=='__main__': asyncio.run(main())
