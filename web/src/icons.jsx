import React from "react";

const paths = {
  today: <><rect x="4" y="5" width="16" height="16" rx="3"/><path d="M8 3v4m8-4v4M4 11h16m-11 5 2 2 4-4"/></>,
  life: <><path d="M12 21V11m0 3C4 14 3 9 4 4c5-1 9 2 8 10Zm0 3c0-8 4-11 9-10 0 6-3 10-9 10Z"/></>,
  plans: <><path d="M5 21V3m0 1c5-4 9 4 14 0v10c-5 4-9-4-14 0"/></>,
  context: <><rect x="7" y="2" width="10" height="20" rx="3"/><path d="M10 18h4m-9-8H2m20 0h-3m-7-3v6m-3-3h6"/></>,
  wallet: <><path d="M20 8V5a2 2 0 0 0-2-2L5 6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h15V8H5"/><path d="M20 12h-5v5h5m-3-2.5h.1"/></>,
  strength: <><path d="M4 7v10m3-12v14m10-14v14m3-12v10M7 12h10"/></>,
  movement: <><path d="m4 19 5-7 4 3 3 5m-8-9 4-5 4 5h4m-9-5-3 4H4"/><circle cx="15" cy="3" r="1"/></>,
  heart: <path d="M20 5a5 5 0 0 0-8 1 5 5 0 0 0-8-1c-5 5 3 10 8 15 5-5 13-10 8-15Z"/>,
  book: <><path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1Zm0 0v15"/></>,
  focus: <><circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3"/></>,
  plus: <path d="M12 5v14M5 12h14"/>,
  arrow: <path d="m9 5 7 7-7 7"/>,
  back: <path d="m15 5-7 7 7 7"/>,
  close: <path d="m6 6 12 12M6 18 18 6"/>,
  check: <path d="m5 12 4 4 10-10"/>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v2"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  trash: <><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/></>,
};

export function Icon({ name, size = 22, ...props }) {
  return <svg style={{ width: size, height: size, flexShrink: 0 }} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name] || paths.life}</svg>;
}
