import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { randomBytes, createHash } from 'node:crypto';
import { WebSocket } from 'ws';
import { createRelay } from './relay.mjs';
const ORIGIN='https://relay.example';
const INVITE=randomBytes(32).toString('base64url');
const callbacks=[{uri:'https://chatgpt.example/callback',provider:'chatgpt'},{uri:'https://claude.example/callback',provider:'claude'}];
const ctx={schema_version:1,leitura:{estados:['estimado'],fontes:['usuario']}};
async function fixture(t, opts={}) {
 const server=createRelay({baseUrl:ORIGIN,redirects:callbacks,joinSecret:INVITE,...opts});server.listen(0,'127.0.0.1');await once(server,'listening');
 const url='http://127.0.0.1:'+server.address().port;const sockets=[];
 t.after(async()=>{for(const w of sockets)w.terminate();server.closeAllConnections();await new Promise(r=>server.close(r));});
 async function post(path,data={},token) {return fetch(url+path,{method:'POST',headers:{'content-type':'application/json',...(token?{authorization:'Bearer '+token}:{})},body:JSON.stringify(data)});}
 async function phone() {
  const d=await (await post('/phone/enroll',{protocol:1,invite:INVITE})).json();
  const w=new WebSocket(url.replace('http:','ws:')+'/phone/channel','fintips-phone-v1',{headers:{authorization:'Bearer '+d.token}});sockets.push(w);
  const [ready]=await once(w,'message');assert.equal(JSON.parse(ready).type,'ready');
  return {...d,w};
 }
 async function authorization(provider='chatgpt') {
  const redirect=callbacks.find(c=>c.provider===provider).uri;
  const c=await(await post('/oauth/register',{redirect_uris:[redirect],token_endpoint_auth_method:'none',grant_types:['authorization_code','refresh_token'],response_types:['code']})).json();
  const verifier=randomBytes(32).toString('base64url');const q=new URLSearchParams({client_id:c.client_id,redirect_uri:redirect,response_type:'code',scope:'context:read',resource:ORIGIN+'/mcp',state:randomBytes(16).toString('hex'),code_challenge:createHash('sha256').update(verifier).digest('base64url'),code_challenge_method:'S256'});
  const html=await(await fetch(url+'/oauth/authorize?'+q)).text();
  const code=/class="code">([A-Z2-7-]+)</.exec(html)[1].replaceAll('-','');const poll=/data-poll="([^"]+)"/.exec(html)[1];
  return {client:c.client_id,redirect,verifier,code,poll};
 }
 async function approve(d,a,scopes=['leitura']) {
  const info=await(await post('/phone/authorization',{code:a.code},d.token)).json();assert.ok(['chatgpt','claude'].includes(info.provider));
  const grant=await(await post('/phone/approve',{code:a.code,scopes},d.token)).json();assert.equal(grant.status,'approved');
  const p=await(await post('/api/poll',{poll:a.poll})).json();const redirect=new URL(p.redirect);assert.equal(redirect.searchParams.get('iss'),ORIGIN);
  const args={grant_type:'authorization_code',client_id:a.client,code:redirect.searchParams.get('code'),redirect_uri:a.redirect,resource:ORIGIN+'/mcp',code_verifier:a.verifier};
  const token=await(await post('/oauth/token',args)).json();assert.ok(token.access_token);return {...token,grant:grant.grant,args};
 }
 async function call(token,params={name:'ler_contexto_revisado',arguments:{}}){return post('/mcp',{jsonrpc:'2.0',id:1,method:'tools/call',params},token);}
 return {url,post,phone,authorization,approve,call};
}

test('mesmo MCP para ambos: cada consulta vai ao celular, sem snapshot reutilizado',async t=>{
 const f=await fixture(t);const d=await f.phone();let state='estimado',requests=0;
 d.w.on('message',raw=>{const b=JSON.parse(raw);if(b.type!=='request')return;requests++;d.w.send(JSON.stringify({type:'result',id:b.id,nonce:b.nonce,contexto:{...ctx,leitura:{estados:[state],fontes:['usuario']}},validade_restante_segundos:100}));});
 for(const provider of ['chatgpt','claude']){
  const a=await f.authorization(provider),token=await f.approve(d,a);
  for(const value of ['estimado','sem_avanco']){state=value;const r=await(await f.call(token.access_token)).json();assert.equal(r.result.isError,false);assert.deepEqual(r.result.structuredContent.contexto.leitura.estados,[value]);assert.equal(r.result.structuredContent.sincronizacao,'consulta_ao_celular');}
 }
 assert.equal(requests,4);
 d.w.close();await once(d.w,'close');const a=await f.authorization(),offline=await f.post('/phone/approve',{code:a.code,scopes:['leitura']},d.token);assert.equal(offline.status,409);
});

test('offline e timeout não entregam contexto anterior; OAuth/PKCE e audience são obrigatórios',async t=>{
 const f=await fixture(t,{queryTimeout:50}),d=await f.phone(),a=await f.authorization();const token=await f.approve(d,a);
 assert.equal((await f.call()).status,401);
 assert.equal((await f.post('/oauth/token',{...token.args,code_verifier:randomBytes(32).toString('base64url')})).status,400);
 assert.equal((await f.post('/oauth/token',{...token.args,resource:'https://wrong.example/mcp'})).status,400);
 assert.equal((await f.post('/oauth/token',token.args)).status,400); // uso único
 const timeout=await(await f.call(token.access_token)).json();assert.equal(timeout.result.isError,true);assert.equal(timeout.result.structuredContent,undefined);
 d.w.close();await once(d.w,'close');const offline=await(await f.call(token.access_token)).json();assert.equal(offline.result.isError,true);assert.equal(offline.result.structuredContent,undefined);
});

test('resposta de outro aparelho, nonce incorreto e replay não atendem uma consulta',async t=>{
 const f=await fixture(t,{queryTimeout:300}),a=await f.phone(),b=await f.phone(),auth=await f.authorization(),token=await f.approve(a,auth);
 const event=once(a.w,'message');const pending=f.call(token.access_token);const [raw]=await event;const job=JSON.parse(raw);assert.equal(job.type,'request');
 const response={type:'result',id:job.id,nonce:job.nonce,contexto:ctx,validade_restante_segundos:300};
 b.w.send(JSON.stringify(response));a.w.send(JSON.stringify({...response,nonce:randomBytes(32).toString('base64url')}));
 a.w.send(JSON.stringify(response));const result=await(await pending).json();assert.equal(result.result.isError,false);
 a.w.send(JSON.stringify(response));const next=await(await f.call(token.access_token)).json();assert.equal(next.result.isError,true);
});

test('o relay recusa PII e ampliação de áreas antes de devolver conteúdo ao chat',async t=>{
 for(const context of [{...ctx,titulo:'CANARY_PRIVADO'}, {...ctx,planos:[]}]){
  const f=await fixture(t),d=await f.phone(),a=await f.authorization(),token=await f.approve(d,a);
  d.w.on('message',raw=>{const b=JSON.parse(raw);if(b.type==='request')d.w.send(JSON.stringify({type:'result',id:b.id,nonce:b.nonce,contexto:context,validade_restante_segundos:10}));});
  const r=await(await f.call(token.access_token)).json();assert.equal(r.result.isError,true);assert.equal(r.result.structuredContent,undefined);assert.ok(!JSON.stringify(r).includes('CANARY_PRIVADO'));
 }
});

test('revogar pelo telefone invalida OAuth, refresh e consulta pendente; desconectar revoga todos',async t=>{
 const f=await fixture(t),d=await f.phone(),a=await f.authorization(),token=await f.approve(d,a);
 const event=once(d.w,'message'),pending=f.call(token.access_token);await event;
 assert.equal((await f.post('/phone/revoke',{grant:token.grant},d.token)).status,200);
 assert.equal((await(await pending).json()).result.isError,true);assert.equal((await f.call(token.access_token)).status,401);
 assert.equal((await f.post('/oauth/token',{grant_type:'refresh_token',client_id:a.client,refresh_token:token.refresh_token,resource:ORIGIN+'/mcp'})).status,400);
 const next=await f.approve(d,await f.authorization('claude'));
 await f.post('/phone/disconnect',{},d.token);assert.equal((await f.call(next.access_token)).status,401);
 assert.equal((await f.post('/phone/authorization',{code:a.code},d.token)).status,401);
});

test('refresh rotativo: replay revoga o vínculo sem expor dados',async t=>{
 const f=await fixture(t),d=await f.phone(),a=await f.authorization(),token=await f.approve(d,a);
 const args={grant_type:'refresh_token',client_id:a.client,refresh_token:token.refresh_token,resource:ORIGIN+'/mcp'};
 const renewed=await(await f.post('/oauth/token',args)).json();assert.ok(renewed.access_token);
 assert.equal((await f.post('/oauth/token',args)).status,400);assert.equal((await f.call(renewed.access_token)).status,401);
});

test('negação volta com issuer; callbacks, Origin, escrita e payloads extras são recusados',async t=>{
 const f=await fixture(t),d=await f.phone(),a=await f.authorization();
 assert.equal((await f.post('/oauth/register',{redirect_uris:['https://evil.example/cb'],token_endpoint_auth_method:'none'})).status,400);
 assert.equal((await f.post('/phone/approve',{code:a.code,scopes:['leitura'],context:ctx},d.token)).status,400);
 assert.equal((await f.post('/phone/deny',{code:a.code},d.token)).status,200);
 const p=await(await f.post('/api/poll',{poll:a.poll})).json(),u=new URL(p.redirect);assert.equal(u.searchParams.get('error'),'access_denied');assert.equal(u.searchParams.get('iss'),ORIGIN);
 assert.equal((await fetch(f.url+'/phone/enroll',{method:'POST',headers:{origin:'https://evil.example','content-type':'application/json'},body:'{"protocol":1}'})).status,403);
 const token=await f.approve(d,await f.authorization());const bad=await(await f.call(token.access_token,{name:'escrever_registro',arguments:{}})).json();assert.equal(bad.error.code,-32602);
});
