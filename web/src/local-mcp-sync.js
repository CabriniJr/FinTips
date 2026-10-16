import { hasNativeStorage } from "./native-storage.js";
import { useEffect, useState } from "react";
import { isAndroid, nativeMotor } from "./native-motor.js";
import { projectContext } from "./ai-projection.js";

/** Atualiza apenas o servidor já iniciado e os escopos aprovados naquela sessão.
 * Nunca inicia serviço ou amplia consentimento em segundo plano.
 */
export function useLocalMcpSync(life) {
  const [issue, setIssue] = useState("");
  useEffect(() => {
    if (!isAndroid()) return;
    let ended = false, working = false, again = false, timer;
    const sync = async () => {
      if (ended || document.visibilityState === "hidden") return;
      if (working) { again = true; return; }
      working = true;
      let session;
      try {
        const status = await nativeMotor("servidor.status");
        if (ended) return;
        if (!status.ativo || status.pausado) { setIssue(""); return; }
        session = status.sessao;
        if (life.blocked) throw new Error("dados indisponíveis");
        if (hasNativeStorage()) await nativeMotor("servidor.atualizar_nativo", { sessao: session });
        else {
          const context = await projectContext(life.state, status.escopos);
          if (ended) return;
          await nativeMotor("servidor.atualizar", { sessao: session, context });
        }
        if (!ended) setIssue("");
      } catch {
        if (!ended && session) {
          const current = await nativeMotor("servidor.status").catch(() => null);
          if (ended || !current?.ativo || current.pausado || current.sessao !== session) return;
          const invalid = await nativeMotor("servidor.invalidar", { sessao: session }).catch(() => null);
          if (!ended) setIssue(invalid ? "O contexto local não pôde ser atualizado. As consultas ficam sem dados até uma atualização válida." : "Não foi possível atualizar o contexto. Confira o estado do servidor local.");
        }
      } finally {
        working = false;
        if (again && !ended) { again = false; schedule(); }
      }
    };
    const schedule = () => { clearTimeout(timer); timer = setTimeout(sync, 250); };
    const events = ["focus", "fintips:resume", "fintips:reading-changed", "fintips:mcp-state", "storage"];
    events.forEach((e) => addEventListener(e, schedule));
    document.addEventListener("visibilitychange", schedule);
    const interval = setInterval(schedule, 60000); schedule();
    return () => { ended = true; clearTimeout(timer); clearInterval(interval); events.forEach((e) => removeEventListener(e, schedule)); document.removeEventListener("visibilitychange", schedule); };
  }, [life.state, life.blocked]);
  return issue;
}
