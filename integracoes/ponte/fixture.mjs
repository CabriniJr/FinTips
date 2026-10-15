// Somente fixture de interoperabilidade. Não é entrypoint do container.
import { createServer } from 'node:https';
import { readFileSync } from 'node:fs';
import { createInterface } from 'node:readline';
import { randomBytes } from 'node:crypto';
import { createRelay } from './relay.mjs';
const lines=createInterface({input:process.stdin});
const config=JSON.parse(await new Promise(resolve=>lines.once('line',resolve)));
const server=createServer({key:readFileSync(config.key),cert:readFileSync(config.cert)});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const origin='https://localhost:'+server.address().port,invite=randomBytes(32).toString('base64url');
createRelay({baseUrl:origin,joinSecret:invite,httpServer:server,redirects:[
 {uri:'https://chatgpt.com/connector_platform_oauth_redirect',provider:'chatgpt'},
 {uri:'https://claude.ai/api/mcp/auth_callback',provider:'claude'},
]});
process.stdout.write(JSON.stringify({origin,invite})+'\n');
lines.on('close',()=>process.exit(0));
