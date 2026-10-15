import { useEffect, useState } from "react";
import { hasNativeMotor, isAndroid, nativeMotor } from "./native-motor.js";
import { pacing } from "./reading-model.js";

export function usePacing(points, options) {
  const key = JSON.stringify({ points: points.map(({ dia, progresso_bp }) => ({ dia, progresso_bp })), ...options });
  const [result, setResult] = useState(null);
  useEffect(() => {
    if (!isAndroid()) return;
    let current = true;
    nativeMotor("leitura.ritmo", JSON.parse(key)).then((data) => { if (current) setResult({ key, data }); })
      .catch((e) => { if (current) setResult({ key, error: e.message }); });
    return () => { current = false; };
  }, [key]);
  if (!isAndroid()) {
    try { return { data: pacing(points, options) }; }
    catch { return { error: "Há uma data inconsistente neste histórico. Confira o relógio e preserve uma cópia local." }; }
  }
  if (!hasNativeMotor()) return { error: "Atualize o Android System WebView para usar o motor embarcado. Seus registros foram preservados." };
  return result?.key === key ? result : { loading: true };
}

export function useDailyMotor(state, today, tasksForDay, isDone) {
  const key = JSON.stringify({ today, tasks: tasksForDay(state, today).map((t) => ({ id: t.id, area: t.atributo, done: isDone(state, t.id, today) })) });
  const [result, setResult] = useState(null);
  useEffect(() => {
    if (!isAndroid()) return;
    let active = true;
    nativeMotor("vida.frentes", JSON.parse(key)).then((data) => { if (active) setResult({ key, data }); })
      .catch(() => { if (active) setResult({ key, error: true }); });
    return () => { active = false; };
  }, [key]);
  return result?.key === key ? result : null;
}
