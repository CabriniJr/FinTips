import { localDay, newId, shiftDay } from "./life-store.js";
const normal = (s) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
export function inferType(text) {
  const t = normal(text);
  if (/^(livro|leitura)\s*[:\-]/.test(t) || /\b(livro|terminar de ler|estou lendo)\b/.test(t)) return "livro";
  if (/^(tarefa|todo)\s*[:\-]/.test(t) || /\b(todos os dias|diariamente|todo dia)\b/.test(t)) return "tarefa";
  if (/^(reserva|patrimonio)\s*:/.test(t)) return "patrimonio";
  if (/^(compromisso|assinatura)\s*:/.test(t)) return "compromisso";
  if (/^(objetivo|meta)\s*:/.test(t)) return "objetivo";
  if (/^decisao\s*:/.test(t)) return "decisao";
  if (/^(fato|contexto)\s*:/.test(t)) return "fato";
  return "plano";
}
export function inferArea(text) {
  const t = normal(text);
  const rules = [["FOR", /\b(academia|musculacao|treinar|forca)\b/], ["AGI", /\b(correr|caminhar|corrida|cardio)\b/],
    ["INT", /\b(ler|livro|estudar|curso|aprender)\b/], ["VIT", /\b(dormir|sono|saude|meditar)\b/],
    ["OURO", /\b(dinheiro|economizar|reserva|divida|financeiro|reais)\b/], ["FOC", /\b(foco|celular|atencao)\b/]];
  const matches = rules.filter(([, re]) => re.test(t));
  return matches.length === 1 ? matches[0][0] : null;
}
export function makeDraft(text, type = inferType(text), today = localDay()) {
  const clean = text.trim().replace(/^(?:plano|tarefa|todo|livro|leitura|reserva|patrim[oô]nio|compromisso|assinatura|objetivo|meta|decis[aã]o|fato|contexto)\s*[:\-]\s*/i, "");
  const parts = clean.split(/\s+porque\s+/i); const fields = { titulo: parts[0].trim() };
  const area = inferArea(clean); if (area && ["plano", "tarefa", "objetivo", "perfil"].includes(type)) fields.atributo = area;
  if (parts.length > 1 && ["plano", "objetivo", "causa", "compromisso", "plano_financeiro", "regra", "perfil", "patrimonio", "decisao"].includes(type)) fields.porque = parts.slice(1).join(" porque ").trim();
  const date = clean.match(/\b(\d{4}-\d{2}-\d{2})\b/); if (date && ["plano", "livro", "objetivo", "decisao", "plano_financeiro"].includes(type)) fields.prazo = date[1];
  if (type === "tarefa") { fields.inicio = /amanh[aã](?:\s|$)/i.test(clean) ? shiftDay(today, 1) : today; fields.repetir = /\b(todos os dias|todo dia|diariamente)\b/i.test(clean); }
  if (type === "livro") { const p = clean.match(/\b(\d+(?:[,.]\d{1,2})?)\s*%/); if (p) fields.progresso_bp = Math.round(Number(p[1].replace(",", ".")) * 100); }
  if (["compromisso", "patrimonio"].includes(type)) { const value = clean.match(/R\$\s*([\d.,]+)/i); if (value && /^\d+(?:[.,]\d{1,2})?$/.test(value[1])) fields.valor_centavos = Math.round(Number(value[1].replace(",", ".")) * 100); }
  if (type === "medida") { fields.rotulo = fields.titulo; delete fields.titulo; fields.dia = today; }
  if (type === "fato") fields.descricao = clean;
  if (type === "decisao") fields.pergunta = clean;
  return { id: newId(), tipo: type, campos: fields, porque: "Registrado a partir de conversa local e confirmado pela pessoa.", acao: "criar" };
}
export function answerField(raw, spec, field) {
  const text = raw.trim();
  if (!text) throw new Error("Responda ou escolha uma opção.");
  if (spec.tipo === "texto") return text;
  if (spec.tipo === "opcao") {
    const value = spec.opcoes.find((v) => normal(v) === normal(text));
    if (!value) throw new Error("Escolha uma das opções desta pergunta."); return value;
  }
  if (spec.tipo === "booleano") {
    if (/^(sim|true)$/i.test(text)) return true; if (/^(nao|não|false)$/i.test(text)) return false;
    throw new Error("Responda sim ou não.");
  }
  if (spec.tipo === "data") {
    const value = /^\d{2}\/\d{2}\/\d{4}$/.test(text) ? text.split("/").reverse().join("-") : text;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || localDay(new Date(`${value}T12:00:00`)) !== value) throw new Error("Use uma data válida, como 2026-12-31."); return value;
  }
  let value;
  if (field === "progresso_bp") {
    const s = text.replace(/%$/, "").trim(); if (!/^\d+(?:[,.]\d{1,2})?$/.test(s)) throw new Error("Informe uma porcentagem, por exemplo 25%.");
    value = Math.round(Number(s.replace(",", ".")) * 100);
  } else if (field.endsWith("_centavos")) {
    const s = text.replace(/^R\$\s*/i, ""); if (!/^\d+(?:[,.]\d{1,2})?$/.test(s)) throw new Error("Informe reais sem separador de milhar, como 1500,50."); value = Math.round(Number(s.replace(",", ".")) * 100);
  } else { if (!/^\d+$/.test(text)) throw new Error("Informe um número inteiro."); value = Number(text); }
  if (!Number.isSafeInteger(value) || value < spec.minimo || value > spec.maximo) throw new Error("Esse valor está fora do intervalo permitido.");
  return value;
}
export function displayValue(field, value) {
  if (field.endsWith("_centavos")) return (value / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  if (field === "progresso_bp") return `${value / 100}%`;
  if (typeof value === "boolean") return value ? "Sim" : "Não";
  return String(value);
}
export const containsKey = (text) => /\bsk-[A-Za-z0-9_-]{16,}/.test(text);
