const BASE = "";

async function req(path, opts = {}) {
  const r = await fetch(BASE + path, {
    headers: { "content-type": "application/json" },
    ...opts,
  });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      detail = (await r.json()).detail || detail;
    } catch {
      /* resposta sem corpo JSON */
    }
    throw new Error(detail);
  }
  return r.json();
}

const post = (path, body) => req(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => req("/api/health"),
  context: () => req("/api/context"),
  transactions: (params) => req("/api/transactions?" + new URLSearchParams(params)),
  projection: (cenario, meses = 12) =>
    req(`/api/projection?cenario=${cenario}&meses=${meses}`),
  profile: () => req("/api/profile"),
  levers: () => req("/api/levers"),

  // escrita — o painel usa as mesmas primitivas que o agente
  definirRegra: (body) => post("/api/rules", body),
  removerRegra: (id) => req(`/api/rules/${encodeURIComponent(id)}`, { method: "DELETE" }),
  criarCategoria: (body) => post("/api/categories", body),
  definirCustoFixo: (body) => post("/api/commitments", body),
  removerCustoFixo: (id) => req(`/api/commitments/${encodeURIComponent(id)}`, { method: "DELETE" }),
  gravarFato: (body) => post("/api/facts", body),
  assinarPerfil: (eixo, body) => post(`/api/profile/${encodeURIComponent(eixo)}`, body),
  esquecerPerfil: (eixo) => req(`/api/profile/${encodeURIComponent(eixo)}`, { method: "DELETE" }),
  resolverItem: (id, oQueFoiFeito, adiar = false) =>
    post(`/api/triage/${encodeURIComponent(id)}/resolve`, { o_que_foi_feito: oQueFoiFeito, adiar }),

  savePlan: (body) => post("/api/plans", body),
  deletePlan: (id) => req(`/api/plans/${encodeURIComponent(id)}`, { method: "DELETE" }),
  purchase: (body) => post("/api/purchase", body),
  holdings: (posicoes) => post("/api/holdings", { posicoes }),
  import: (file) => {
    const fd = new FormData();
    fd.append("arquivo", file);
    return fetch("/api/import", { method: "POST", body: fd }).then((r) => {
      if (!r.ok) throw new Error("falha ao importar");
      return r.json();
    });
  },
};

export const brl = (v, casas = 2) =>
  "R$ " +
  Number(v || 0).toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });

export const brl0 = (v) =>
  "R$ " + Number(v || 0).toLocaleString("pt-BR", { maximumFractionDigits: 0 });

export const pct = (v, casas = 1) =>
  Number(v || 0).toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  }) + "%";

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
export const mesLabel = (m) => {
  if (!m) return "";
  const [y, mm] = m.split("-");
  return `${MESES[Number(mm) - 1]}/${y.slice(2)}`;
};

export const dataBR = (iso) => (iso ? iso.split("-").reverse().join("/") : "");

export const titulo = (s) =>
  (s || "").charAt(0).toUpperCase() + (s || "").slice(1).replace(/_/g, " ");
