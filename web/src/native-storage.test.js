import test from "node:test";
import assert from "node:assert/strict";
import { CLIENT_STATE_KEY } from "./client-state.js";
import { clientStorage, installNativeStorage } from "./native-storage.js";

test("guarda nativa preserva legado, rejeita edição concorrente e separa revisão do chat", async () => {
  const legacy=new Map([[CLIENT_STATE_KEY,"LEGADO_INTACTO"]]);
  globalThis.localStorage={getItem:(k)=>legacy.get(k)||null,setItem:(k,v)=>legacy.set(k,v)};
  globalThis.StorageEvent=class extends Event { constructor(type,opts) { super(type);this.key=opts.key; } };
  globalThis.dispatchEvent=()=>true;
  let state={revisao_bundle:1,revisao_chat:1,bundle:{reading:"old"},chat:null};
  globalThis.FinTipsState={
    snapshot:()=>JSON.stringify({result:structuredClone(state)}),
    salvar:(raw)=>{
      const i=JSON.parse(raw),rk=`revisao_${i.chave}`;
      if(state[rk]!==i.revisao) return JSON.stringify({error:"revisão mudou"});
      state={...state,[i.chave]:i.valor,[rk]:state[rk]+1};
      return JSON.stringify({result:structuredClone(state)});
    },
  };
  installNativeStorage(state);
  const stale=clientStorage.getItem(CLIENT_STATE_KEY);
  state={...state,revisao_bundle:2,bundle:{reading:"worker"}};
  assert.throws(()=>clientStorage.setItem(CLIENT_STATE_KEY,stale),/revisão mudou/);
  assert.deepEqual(state.bundle,{reading:"worker"});
  clientStorage.getItem("fintips.triagem.chat.v1");
  clientStorage.getItem(CLIENT_STATE_KEY);
  clientStorage.setItem(CLIENT_STATE_KEY,JSON.stringify({reading:"user"}));
  clientStorage.setItem("fintips.triagem.chat.v1",JSON.stringify({text:"mensagem"}));
  assert.deepEqual(state.bundle,{reading:"user"});
  assert.deepEqual(state.chat,{text:"mensagem"});
  assert.equal(legacy.get(CLIENT_STATE_KEY),"LEGADO_INTACTO");
  assert.throws(()=>clientStorage.setItem("fintips.leitura.v1","{}"),/não reconhecida/);
  await new Promise(queueMicrotask);
});
