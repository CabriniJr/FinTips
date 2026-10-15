import asyncio,json,mimetypes,ssl,tempfile,subprocess,threading,os,shutil
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime,timezone
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=Path(os.environ.get('FINTIPS_UI_QA_OUTPUT',ROOT/'kotlin/conector/build/reports/triagem-ui'));OUT.mkdir(parents=True,exist_ok=True)
LIFE={'schema_version':1,'tarefas':[{'id':'base-task','titulo':'BASE_TASK_CANARY','atributo':'FOC','inicio':'2026-10-15','repetir':True}],'registros':[],'planos':[{'id':'base-plan','titulo':'BASE_PLAN_CANARY','atributo':'FOC','porque':'Escolha sintética','proximoPasso':'Passo sintético','prazo':'','concluido':False}],'medidas':[]}
READING={'schema_version':1,'livros':[{'id':'base-book','titulo':'BASE_BOOK_CANARY','fonte':'librera','chave':'BASE_FILE_CANARY.epub','perfil':'BASE_PROFILE_CANARY','prazo':'2026-11-30','dias_semana':3,'observacoes':[{'dia':'2026-10-12','progresso_bp':1000,'tempo_ms':1791806400000,'origem':'librera'},{'dia':'2026-10-15','progresso_bp':2000,'tempo_ms':1792065600000,'origem':'librera'}]}]}
requests=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  assert self.path=='/v1/responses';body=json.loads(self.rfile.read(int(self.headers['content-length'])));requests.append(body)
  assert body['model']=='gpt-4.1-mini' and body['store'] is False
  public=json.loads(body['input']);raw=json.dumps(body);assert 'CANARY' not in raw and 'origem_real' not in raw and 'destino_real' not in raw and 'mapa_local' not in raw and 'sk-' not in raw
  assert public['metricas']
  if body['text']['format']['name']=='fintips_agente_v2':
   vals=public['valores_disponiveis'];records=[];links=[]
   for draft in public['rascunhos']:
    fields=[]
    if draft['tipo']=='livro':
     for field in ['titulo','dias_semana','progresso_bp']:
      candidates=[v for v in vals if v['dono']==draft['ref'] and v['campo']==field]
      chosen=next((v for v in candidates if v['papel']=='titulo_curto'),next(iter(candidates),None))
      if chosen:fields.append({'campo':field,'valor':chosen['ref']})
    if fields:records.append({'ref':draft['ref'],'tipo':draft['tipo'],'campos':fields})
   if len(public['rascunhos'])>=2:links=[{'de':public['rascunhos'][1]['ref'],'para':public['rascunhos'][0]['ref'],'tipo':'apoia'}]
   missing=next((d for d in public['rascunhos'] if d['faltantes']),None)
   choice={'registros':records,'relacoes':links,'pergunta':{'ref':missing['ref'],'campo':missing['faltantes'][0],'texto':'Qual área faz sentido para {{'+missing['ref']+'}}?'} if missing else None}
  else:
   options=public['opcoes'];o=next((o for o in options if o['acao']=='perguntar'),None)
   if o is None:o=next((o for o in options if o['acao']=='sugerir_valor' and o['campo']=='dias_semana'),options[0])
   choice={'escolha':o['id'],'valor':3 if o['acao']=='sugerir_valor' else None,'motivo':'ritmo_realista' if o['acao']=='sugerir_valor' else 'preencher_necessario' if o['acao']=='perguntar' else 'revisar_em_lote'}
  data=json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(choice)}]}]}).encode()
  self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.send_header('Connection','close');self.end_headers();self.wfile.write(data)
async def main():
 with tempfile.TemporaryDirectory(prefix='fintips-triage-ui-') as tmp:
  cert,key=Path(tmp)/'cert.pem',Path(tmp)/'key.pem'
  subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1','-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(cert,key);server.socket=tls.wrap_socket(server.socket,server_side=True);threading.Thread(target=server.serve_forever,daemon=True).start()
  origin='https://localhost:'+str(server.server_port)
  java=Path(os.environ['JAVA_HOME'])/'bin/java' if os.environ.get('JAVA_HOME') else Path(shutil.which('java') or 'java')
  phone=await asyncio.create_subprocess_exec(str(java),'-cp',(ROOT/'kotlin/conector/build/test-classpath.txt').read_text(),'com.fintips.mcp.FixtureAppKt',stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE)
  phone.stdin.write((json.dumps({'certificate':str(cert),'api_origin':origin})+'\n').encode());await phone.stdin.drain()
  lock=asyncio.Lock();errors=[];webrequests=[];calls=[]
  async def send(op,i={}):
   async with lock:
    phone.stdin.write((json.dumps({'operation':op,'input':i})+'\n').encode());await phone.stdin.drain();line=await phone.stdout.readline();assert line,op;return json.loads(line)
  async def native(raw):
   r=json.loads(raw);result=await send(r['operation'],r['input']);calls.append({'op':r['operation'],'error':result.get('harness_error',False),'code':result.get('code'),'class':result.get('harness_class'),'options':result.get('publico',{}).get('opcoes',[])});return json.dumps({'id':r['id'],'error':'Pedido recusado pelo motor Kotlin.'} if result.get('harness_error') else {'id':r['id'],'result':result})
  try:
   async with async_playwright() as pw:
    browser=await pw.chromium.launch(executable_path=os.environ.get('CHROME_BIN') or shutil.which('chromium') or shutil.which('google-chrome'),headless=True,args=['--no-sandbox'])
    context=await browser.new_context(viewport={'width':390,'height':844},reduced_motion='reduce',timezone_id='UTC',accept_downloads=True)
    async def route(r):
     u=urlparse(r.request.url);webrequests.append(u.hostname);assert u.hostname=='appassets.androidplatform.net'
     file=ROOT/'fintips/web'/u.path.lstrip('/');await r.fulfill(body=file.read_bytes(),content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
    await context.route('**/*',route);await context.expose_function('nativeRequest',native)
    await context.add_init_script('window.FinTipsMotor={postMessage(raw){window.nativeRequest(raw).then(data=>window.FinTipsMotor.onmessage({data}));}};')
    await context.add_init_script("if(!localStorage.getItem('fintips.vida.v1'))localStorage.setItem('fintips.vida.v1',"+json.dumps(json.dumps(LIFE))+");if(!localStorage.getItem('fintips.leitura.v1'))localStorage.setItem('fintips.leitura.v1',"+json.dumps(json.dumps(READING))+");")
    page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));await page.clock.install(time=datetime(2026,10,15,12,tzinfo=timezone.utc))
    await page.goto('https://appassets.androidplatform.net/index.html#contexto');await page.get_by_role('link',name='Vamos organizar seus planos?',exact=False).click();await page.get_by_role('heading',name='Conversa',exact=True).wait_for()
    msg=page.get_by_label('Mensagem de triagem')
    await msg.fill('Plano: LOCAL_TRIAGE_CANARY organizar o semestre porque isso é importante\nLivro: “LOCAL_BOOK_CANARY” 3 dias por semana\nTarefa: estudar LOCAL_TASK_CANARY todos os dias\nAssinatura: LOCAL_SERVICE_CANARY R$ 123,45')
    await page.get_by_role('button',name='Enviar',exact=True).click();await page.get_by_text('Em qual área da vida ele entra?',exact=True).first.wait_for()
    assert await page.evaluate("localStorage.getItem('fintips.client.v1')===null")
    assert not requests
    # Ativação acontece na própria conversa; o diálogo de chave é simulado no harness.
    await page.get_by_role('button',name='Conectar minha OpenAI',exact=True).click();await page.evaluate("dispatchEvent(new Event('fintips:chave-triagem'))")
    await page.get_by_text('SÓ MAIS UMA COISA',exact=True).wait_for()
    await page.locator('.triage-current').get_by_role('button',name='Estudos',exact=True).click()
    await page.get_by_text('DEIXEI ORGANIZADO',exact=True).wait_for()
    await page.get_by_text('Ver o que será guardado',exact=False).click()
    # A IA preenche dias, restaura o título privado e relaciona sem aprovações por campo.
    pending=json.loads(await page.evaluate("localStorage.getItem('fintips.triagem.chat.v1')"))
    assert pending['drafts'][1]['campos']['titulo']=='LOCAL_BOOK_CANARY'
    assert pending['drafts'][1]['campos']['dias_semana']==3 and pending['links']
    assert 'progresso_bp' not in pending['drafts'][1]['campos']
    before_calls=len(requests);await page.wait_for_timeout(350);assert len(requests)==before_calls # não realimenta o agente com a própria escrita
    await msg.fill('Na verdade, 4 dias por semana');await page.get_by_role('button',name='Enviar',exact=True).click()
    await page.get_by_text('DEIXEI ORGANIZADO',exact=True).wait_for()
    corrected=json.loads(await page.evaluate("localStorage.getItem('fintips.triagem.chat.v1')"));assert len(corrected['drafts'])==4 and corrected['drafts'][1]['campos']['dias_semana']==4
    # Campos privados continuam na conversa local e jamais no pedido HTTPS.
    service=page.locator('.triage-draft').filter(has=page.get_by_role('heading',name='LOCAL_SERVICE_CANARY R$ 123,45',exact=True))
    await service.get_by_text('Refinar com detalhes opcionais',exact=True).click()
    for field,value in [('Qual a origem?','ORIGEM_ONLY_CANARY'),('Qual o destino?','DESTINO_ONLY_CANARY')]:
     await service.locator('dl > div').filter(has_text=field).get_by_role('button',name='Ajustar',exact=True).click();await msg.fill(value);await page.get_by_role('button',name='Enviar',exact=True).click()
    await page.get_by_role('button',name='Confirmar 4 registro(s)',exact=True).wait_for();assert not await page.get_by_role('button',name='Confirmar 4 registro(s)',exact=True).is_disabled()
    for width in [320,390,768]:
     await page.set_viewport_size({'width':width,'height':844});assert await page.evaluate('document.body.scrollWidth<=innerWidth+1'),width
    await page.set_viewport_size({'width':390,'height':844});await page.screenshot(path=str(OUT/'triagem-revisao.png'),full_page=True);await page.locator('.triage-ready').screenshot(path=str(OUT/'resumo-inline.png'))
    await page.get_by_role('button',name='Está certo, salvar',exact=True).click();await page.get_by_text('4 registro(s) salvo(s) no aparelho',exact=True).wait_for()
    state=json.loads(await page.evaluate("localStorage.getItem('fintips.client.v1')"));assert len(state['vida']['tarefas'])==len(LIFE['tarefas'])+1;assert len(state['vida']['planos'])==len(LIFE['planos'])+1;assert len(state['leitura']['livros'])==len(READING['livros'])+1
    book=next(b for b in state['leitura']['livros'] if b['titulo']=='LOCAL_BOOK_CANARY');assert book['observacoes']==[] and book['dias_semana']==4
    assert state['caderno']['assets'][0]['campos']['origem_real']=='ORIGEM_ONLY_CANARY'
    assert state['vida']['registros']==LIFE['registros'];assert len(state['caderno']['aplicacoes'])==1
    await page.get_by_role('button',name='Anotações',exact=False).click();await page.get_by_role('heading',name='LOCAL_SERVICE_CANARY R$ 123,45',exact=True).wait_for()
    await page.get_by_role('link',name='Hoje',exact=True).click();await page.get_by_text('estudar LOCAL_TASK_CANARY todos os dias',exact=False).click()
    after=json.loads(await page.evaluate("localStorage.getItem('fintips.client.v1')"));assert len(after['vida']['registros'])==len(state['vida']['registros'])+1
    await page.get_by_role('link',name='Planos',exact=True).click();await page.get_by_text('LOCAL_TRIAGE_CANARY organizar o semestre',exact=True).wait_for()
    await page.goto('https://appassets.androidplatform.net/index.html#vida/INT');await page.get_by_text('LOCAL_BOOK_CANARY',exact=True).wait_for()
    await page.get_by_role('link',name='Contexto',exact=True).click()
    async with page.expect_download() as download:await page.get_by_role('button',name='Baixar cópia local',exact=True).click()
    saved=await download.value;backup=json.loads(Path(await saved.path()).read_text());assert backup['tipo']=='fintips_backup' and backup['schema_version']==2;assert backup['bundle']['leitura']['livros'][-1]['titulo']=='LOCAL_BOOK_CANARY';assert 'sk-' not in json.dumps(backup)
    await page.get_by_role('link',name='Vamos organizar seus planos?',exact=False).click();await page.get_by_role('heading',name='Conversa',exact=True).wait_for()
    before_reload=len(requests);await page.reload();await page.get_by_role('heading',name='Conversa',exact=True).wait_for();await page.wait_for_timeout(250);assert len(requests)==before_reload;assert await page.evaluate("JSON.parse(localStorage.getItem('fintips.client.v1')).caderno.aplicacoes.length===1")
    await page.get_by_role('button',name='Nova conversa',exact=True).click();await page.get_by_role('button',name='Limpar conversa',exact=True).click()
    await msg.fill('Plano: LOCAL_TRIAGE_CANARY organizar o semestre');await page.get_by_role('button',name='Enviar',exact=True).click()
    await page.get_by_text('DEIXEI ORGANIZADO',exact=True).wait_for()
    existing=json.loads(await page.evaluate("localStorage.getItem('fintips.triagem.chat.v1')"));assert existing['drafts'][0]['acao']=='atualizar'
    await page.get_by_role('button',name='Está certo, salvar',exact=True).click();await page.get_by_text('1 registro(s) salvo(s) no aparelho',exact=True).wait_for()
    now=json.loads(await page.evaluate("localStorage.getItem('fintips.client.v1')"));assert len(now['vida']['planos'])==len(state['vida']['planos'])
    # Agente/API importa uma proposta: continua pendente até confirmação, depois é removível.
    await page.get_by_role('button',name='Nova conversa',exact=True).click();await page.get_by_role('button',name='Limpar conversa',exact=True).click()
    base=json.loads(await page.evaluate("localStorage.getItem('fintips.client.v1')"))
    draft={'id':'import-fact','tipo':'fato','campos':{'titulo':'IMPORTED_FACT_CANARY','descricao':'DESCRIPTION_ONLY_CANARY'},'porque':'Confirmação sintética','acao':'criar'}
    relation={'de':{'tipo':'fato','id':'import-fact'},'para':{'tipo':'plano','id':base['vida']['planos'][-1]['id']},'tipo':'apoia','porque':'Vínculo escolhido pela pessoa'}
    proposal=await send('triagem.preparar',{'bundle':base,'rascunhos':[draft],'relacoes':[relation],'id':'import-proposal'})
    file=Path(tmp)/'proposta.json';file.write_text(json.dumps(proposal))
    await page.get_by_text('Conexão e detalhes',exact=True).click();await page.get_by_text('Integrar uma proposta por contrato',exact=True).click();await page.get_by_label('Proposta de triagem em JSON').set_input_files(str(file))
    await page.get_by_role('button',name='Está certo, salvar',exact=True).wait_for()
    assert json.loads(await page.evaluate("localStorage.getItem('fintips.client.v1')"))==base
    await page.get_by_role('button',name='Está certo, salvar',exact=True).click();await page.get_by_text('1 registro(s) salvo(s) no aparelho',exact=True).wait_for()
    await page.get_by_role('button',name='Anotações',exact=False).click()
    article=page.locator('article').filter(has=page.get_by_role('heading',name='IMPORTED_FACT_CANARY',exact=True))
    await article.get_by_role('button',name='Remover registro',exact=True).click();await page.get_by_role('button',name='Confirmar remoção',exact=True).click();await page.get_by_text('Registro removido do aparelho',exact=True).wait_for()
    deleted=json.loads(await page.evaluate("localStorage.getItem('fintips.client.v1')"));assert len(deleted['caderno']['assets'])==len(base['caderno']['assets']) and deleted['caderno']['relacoes']==base['caderno']['relacoes']
    assert not errors,errors;assert requests and all(h=='appassets.androidplatform.net' for h in webrequests)
    await browser.close()
   (OUT/'resultado.json').write_text(json.dumps({'ui':[320,390,768],'motor_kotlin_real':True,'cliente_https_real':True,'api_openai_simulada':True,'chave_dialogo_simulado':True,'agente_preenche_campos_e_relaciona':True,'sem_loop_de_chamadas':True,'ativacao_inline':True,'correcao_conversada_sem_novo_registro':True,'lote_autopopula_abas':True,'sem_registro_nao_vira_zero':True,'backup_todos_dados_sem_chave':True,'duplicata_atualiza_existente':True,'importacao_por_contrato_somente_revisao':True,'remocao_limpa_relacoes':True,'webview_sem_fetch_externo':True,'requisicoes_api':len(requests),'erros_js':errors},indent=2)+'\n');print('ok: chat móvel, Kotlin real, HTTPS com API simulada; lote nas abas, privacidade de números/aliases, backup, reload, edição e duplicatas')
  except Exception:
   if 'page' in locals():
    try:
     (OUT/'falha.txt').write_text(await page.locator('body').inner_text());await page.screenshot(path=str(OUT/'falha.png'),full_page=True)
    except Exception:pass
   print('QA: chamadas HTTPS',len(requests),'erros JS',errors)
   raise
  finally:
   phone.stdin.close()
   try:await asyncio.wait_for(phone.wait(),8)
   except asyncio.TimeoutError:phone.kill();await phone.wait()
   server.shutdown();server.server_close()
asyncio.run(main())
