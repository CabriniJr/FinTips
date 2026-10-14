import { useEffect, useRef, useState } from "react";

export const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// Uma saída curta antes da entrada. Toques rápidos substituem o destino
// pendente; nada de fila de páginas antigas, nem cópias do DOM pessoal.
export function useRouteMotion(readRoute, group) {
  const [current, setCurrent] = useState(readRoute);
  const [target, setTarget] = useState(current);
  const [phase, setPhase] = useState("enter");
  const displayed = useRef(current);
  useEffect(() => {
    let timer;
    const commit = (next) => {
      const changed = group(displayed.current.page) !== group(next.page);
      displayed.current = next;
      setCurrent(next); setPhase("enter");
      if (changed) window.scrollTo({ top: 0, behavior: "instant" });
    };
    const change = () => {
      clearTimeout(timer);
      const next = readRoute();
      setTarget(next);
      if (reducedMotion() || group(displayed.current.page) === group(next.page)) commit(next);
      else {
        setPhase("leave");
        timer = setTimeout(() => commit(readRoute()), 130);
      }
    };
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    const reduce = () => { if (preference.matches) { clearTimeout(timer); commit(readRoute()); } };
    addEventListener("hashchange", change);
    preference.addEventListener("change", reduce);
    return () => { clearTimeout(timer); removeEventListener("hashchange", change); preference.removeEventListener("change", reduce); };
  }, [readRoute, group]);
  return { current, target, phase };
}

export function useTouchFeedback() {
  useEffect(() => {
    const running = new Set();
    const selector = ".life-button,.icon-button,.text-button,.segmented button,.week-strip button,.area-tabs button,.finance-tabs button,.bottom-nav a,.btn,.opts button";
    const wave = (target, x, y) => {
      if (reducedMotion() || !target || target.disabled || target.closest("[inert]")) return;
      const box = target.getBoundingClientRect();
      const size = Math.hypot(box.width, box.height) * 2;
      const dot = document.createElement("span");
      dot.className = "tap-wave"; dot.setAttribute("aria-hidden", "true");
      Object.assign(dot.style, { width: `${size}px`, height: `${size}px`,
        left: `${(x ?? box.width / 2) - size / 2}px`, top: `${(y ?? box.height / 2) - size / 2}px` });
      target.append(dot);
      const animation = dot.animate([{ transform: "scale(0)", opacity: .13 }, { transform: "scale(1)", opacity: 0 }],
        { duration: 380, easing: "cubic-bezier(.16,1,.3,1)" });
      running.add(animation);
      animation.finished.catch(() => {}).finally(() => { dot.remove(); running.delete(animation); });
    };
    const pointer = (e) => {
      if (!e.isPrimary || e.button !== 0) return;
      const target = e.target.closest?.(selector);
      if (target) { const box = target.getBoundingClientRect(); wave(target, e.clientX - box.left, e.clientY - box.top); }
    };
    const keyboard = (e) => {
      if (e.repeat || !["Enter", " "].includes(e.key)) return;
      const target = e.target.closest?.(selector);
      if (target?.tagName === "A" && e.key === " ") return;
      wave(target);
    };
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    const stop = () => { if (preference.matches) for (const animation of running) animation.cancel(); };
    addEventListener("pointerdown", pointer, true); addEventListener("keydown", keyboard, true);
    preference.addEventListener("change", stop);
    return () => {
      removeEventListener("pointerdown", pointer, true); removeEventListener("keydown", keyboard, true);
      preference.removeEventListener("change", stop);
      for (const animation of running) animation.cancel();
    };
  }, []);
}
