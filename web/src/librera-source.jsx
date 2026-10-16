import React, { useCallback, useEffect, useState } from "react";
import { nativeMotor } from "./native-motor.js";
import { hasNativeStorage } from "./native-storage.js";

const errors = { permissao_revogada: "O acesso ao arquivo foi revogado. Reconecte a fonte.", arquivo_indisponivel: "O arquivo não estava acessível. O Android tentará novamente.", arquivo_invalido: "O arquivo ainda não pôde ser interpretado. Os registros anteriores foram preservados.", limite_atingido: "A guarda atingiu seu limite. Faça uma cópia antes de reorganizar os registros." };
export function LibreraSource({ toast }) {
  const [status,setStatus]=useState(null),[issue,setIssue]=useState(""),[busy,setBusy]=useState(false),[profile,setProfile]=useState("principal");
  const read=useCallback(async () => {
    try { setStatus(await nativeMotor("librera.status")); }
    catch { setIssue("Não foi possível ler o estado da fonte automática."); }
  },[]);
  useEffect(() => {
    if(!hasNativeStorage()) return;
    let ended=false;
    const refresh=()=>{ if(!ended) read(); };
    const failed=(e)=>{ if(!ended) setIssue(e.detail); };
    const events=["fintips:librera-state","fintips:librera-updated","fintips:resume"];
    events.forEach((e)=>addEventListener(e,refresh));addEventListener("fintips:librera-error",failed);refresh();
    return ()=>{ended=true;events.forEach((e)=>removeEventListener(e,refresh));removeEventListener("fintips:librera-error",failed);};
  },[read]);
  if(!hasNativeStorage()) return null;
  const act=async (operation,input={}) => {
    if(busy) return;setBusy(true);setIssue("");
    try { await nativeMotor(operation,input);await read();if(operation==="librera.desconectar") toast?.("Fonte desconectada. Livros e histórico preservados."); }
    catch { setIssue("Não foi possível concluir. Sua fonte e os registros anteriores foram preservados."); }
    finally { setBusy(false); }
  };
  return <section className="librera-source" aria-label="Fonte automática Librera"><span className="manual-tag">LIBRERA / AUTOMÁTICO</span>
    <h3>{status?.conectada ? "Seu progresso, sem reimportar" : "Conecte uma vez. Continue lendo."}</h3>
    <p>Escolha o <b>app-Progress.json que o Librera atualiza</b>. O Android relê esse documento e atualiza os livros no aparelho, mesmo com o app fechado.</p>
    {status?.conectada && <><p className="reading-caption">Perfil {status.perfil} · {status.sucesso_ms ? `arquivo lido em ${new Date(status.sucesso_ms).toLocaleString("pt-BR")}` : "aguardando leitura"}</p>
      <p className="reading-caption">{status.agendada ? "Verificação periódica agendada. O Android decide quando executar, a partir de 15 minutos; pode atrasar com economia de bateria." : "O agendamento não foi confirmado. Abrir o app permite tentar novamente."} O timestamp do livro mostra quando a posição realmente mudou.</p>
      {errors[status.estado] && <p className="reading-warning" role="status">{errors[status.estado]}</p>}
      <div className="reading-toolbar"><button className="life-button" disabled={busy} onClick={()=>act("librera.sincronizar")}>{busy ? "Lendo…" : "Verificar agora"}</button><button className="text-button" disabled={busy} onClick={()=>act("librera.desconectar")}>Desconectar</button><button className="text-button" disabled={busy} onClick={()=>act("librera.conectar",{perfil:status.perfil||profile})}>Trocar ou reconectar arquivo</button></div>
    </>}
    {!status?.conectada && <><button className="life-button primary" disabled={busy} onClick={()=>act("librera.conectar",{perfil:profile.trim()||"principal"})}>Conectar arquivo do Librera</button>
      <details><summary>Outro perfil do Librera</summary><label className="life-field">Perfil da fonte<input maxLength={100} value={profile} onChange={(e)=>setProfile(e.target.value)}/></label><p className="reading-caption">Use o mesmo nome de perfil de importações anteriores para manter os livros e vínculos.</p></details></>}
    <p className="reading-caption">O FinTips lê apenas o documento escolhido. Para nuvem, o provedor precisa oferecer acesso persistente à versão atualizada. Uma cópia que nunca muda continuará com a mesma posição.</p>
    {issue && <p className="form-error" role="alert">{issue}</p>}
  </section>;
}
