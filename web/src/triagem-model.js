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
  if (type === "livro") { const p = clean.match(/(?:j[aá]\s+li|estou\s+em|progresso\s*(?:de|:)?)\s*(\d+(?:[,.]\d{1,2})?)\s*%/i) || (!/\b(quero|meta|chegar|alvo)\b/i.test(clean) && clean.match(/\b(\d+(?:[,.]\d{1,2})?)\s*%/)); if (p) fields.progresso_bp = Math.round(Number(p[1].replace(",", ".")) * 100); }
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

// Pré-processamento privado: captura evidência explícita, sem escolher metas pela pessoa.
export function inlineFields(raw, type, today = localDay()) {
  const text = raw.trim(), t = normal(text), fields = {};
  const area = inferArea(text);
  if (area && ["plano", "tarefa", "objetivo", "perfil"].includes(type)) fields.atributo = area;
  if (type === "livro") {
    const days = t.match(/\b([1-7])\s*(?:dias?|vezes|x)\s*(?:por\s*|na\s*|\/\s*)semana\b/);
    if (days) fields.dias_semana = Number(days[1]);
    const p = t.match(/(?:ja\s+li|estou\s+em|progresso\s*(?:de|:)?)\s*(\d+(?:[,.]\d{1,2})?)\s*%/);
    if (p && Number(p[1].replace(",", ".")) <= 100) fields.progresso_bp = Math.round(Number(p[1].replace(",", ".")) * 100);
  }
  const date = text.match(/\b(\d{4}-\d{2}-\d{2})\b/);
  if (date && ["plano", "livro", "objetivo", "decisao", "plano_financeiro"].includes(type)) fields.prazo = answerField(date[1], { tipo: "data" }, "prazo");
  if (/\bamanha\b/.test(t) && type === "tarefa") fields.inicio = shiftDay(today, 1);
  if (/\b(?:todo dia|todos os dias|diariamente)\b/.test(t) && type === "tarefa") fields.repetir = true;
  const reason = text.match(/\bporque\s+(.+)/i);
  if (reason && ["plano", "objetivo", "causa", "compromisso", "plano_financeiro", "regra", "perfil", "patrimonio", "decisao"].includes(type)) fields.porque = reason[1].trim();
  return fields;
}
export function inlineAnswer(raw, spec, field, type) {
  const fields = inlineFields(raw, type);
  if (fields[field] !== undefined) return fields;
  let value = raw;
  if (field === "dias_semana") {
    const brief = normal(raw).match(/^\s*(?:(?:na verdade|prefiro|pode ser)[, ]*)?([1-7])\s*dias?\b/);
    if (brief) return { ...fields, dias_semana: Number(brief[1]) };
  }
  if (spec.tipo === "inteiro") {
    // Aceita unidades na resposta curta, sem truncar um segundo valor/qualificador.
    value = value.replace(/^\s*(?:na verdade,?\s*|prefiro\s*|pode ser\s*)/i, "");
    if (field === "dias_semana") value = value.replace(/\s*dias?(?:\s*(?:por|na|\/)\s*semana)?\s*$/i, "");
    if (field === "minutos") value = value.replace(/\s*(?:minutos?|min)\s*$/i, "");
  }
  if (spec.tipo === "opcao" && field === "atributo") value = inferArea(raw) || raw;
  fields[field] = answerField(value, spec, field);
  return fields;
}
export function splitIntents(raw) {
  return raw.split(/\n+|;\s*|\s+e\s+(?=(?:tamb[eé]m\s+)?(?:quero|preciso|pretendo|planejo)\b)/i)
    .map((s) => s.replace(/^[-*•]\s*/, "").trim()).filter(Boolean);
}
export function correctionCandidates(raw, drafts) {
  const t = normal(raw);
  if (/\b(?:novo|outro|outra|adicionar)\b/.test(t)) return [];
  const named = drafts.filter((d) => {
    const title = normal(d.campos.titulo || d.campos.rotulo || "");
    return title.length >= 4 && t.includes(title);
  });
  if (named.length) return named;
  const reading = /\b[1-7]\s*dias?\s*(?:por|na|\/)\s*semana\b|(?:ja li|estou em)\s*\d.*%/.test(t);
  const candidates = reading ? drafts.filter((d) => d.tipo === "livro") : drafts;
  return /^(?:na verdade|muda|troca|ajusta|corrige|prefiro|quero mudar)\b/.test(t) || reading ? candidates : [];
}
