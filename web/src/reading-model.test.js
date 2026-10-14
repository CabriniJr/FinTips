import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { emptyReading, libreraPositions, mergeLibrera, pacing, readReading, validateReading } from "./reading-model.js";

const gold = JSON.parse(readFileSync(new URL("../../kotlin/motor/src/jvmTest/resources/ouro/leitura.json", import.meta.url), "utf8"));

test("pacing e projeção mínima do Librera reproduzem a referência Python", () => {
  for (const c of gold.casos) { const { points, ...options } = c.entrada; assert.deepEqual(pacing(points, options), c.resultado, c.nome); }
  for (const c of gold.parser) assert.deepEqual(libreraPositions(c.entrada), c.resultado, c.nome);
});

test("importar o mesmo arquivo não multiplica dias ou inventa sessões", () => {
  const positions = [{ chave: "Exemplo.epub", progresso_bp: 3000, tempo_ms: Date.parse("2026-10-14T12:00:00") }];
  const now = Date.parse("2026-10-14T20:00:00");
  const first = mergeLibrera(emptyReading(), positions, "principal", now, () => "book1");
  assert.equal(first.added, 1); assert.equal(first.updated, 1);
  const second = mergeLibrera(first.state, positions, "principal", now, () => "unused");
  assert.equal(second.added, 0); assert.equal(second.updated, 0);
  assert.equal(second.state.livros[0].observacoes.length, 1);
  assert.equal(validateReading(second.state), true);
});

test("arquivo atrasado não sobrescreve posição mais nova do mesmo dia", () => {
  const now = Date.parse("2026-10-14T20:00:00");
  const latest = { chave: "Exemplo.epub", progresso_bp: 4500, tempo_ms: Date.parse("2026-10-14T18:00:00") };
  const first = mergeLibrera(emptyReading(), [latest], "principal", now, () => "book1");
  const second = mergeLibrera(first.state, [{ ...latest, progresso_bp: 3000, tempo_ms: latest.tempo_ms - 3600000 }], "principal", now);
  assert.equal(second.state.livros[0].observacoes[0].progresso_bp, 4500);
});

test("correção manual prevalece sobre importação no mesmo dia", () => {
  const now = Date.parse("2026-10-14T20:00:00");
  const p = { chave: "Exemplo.epub", progresso_bp: 4500, tempo_ms: Date.parse("2026-10-14T18:00:00") };
  const first = mergeLibrera(emptyReading(), [p], "principal", now, () => "book1");
  first.state.livros[0].observacoes[0].origem = "usuario";
  first.state.livros[0].observacoes[0].progresso_bp = 4200;
  assert.equal(mergeLibrera(first.state, [{ ...p, tempo_ms: now }], "principal", now).state.livros[0].observacoes[0].progresso_bp, 4200);
});

test("o perfil separa livros com o mesmo nome; datas futuras são omitidas", () => {
  const now = Date.parse("2026-10-14T20:00:00");
  const p = { chave: "Exemplo.epub", progresso_bp: 4500, tempo_ms: Date.parse("2026-10-14T18:00:00") };
  const first = mergeLibrera(emptyReading(), [p], "principal", now, () => "book1");
  const second = mergeLibrera(first.state, [p], "outro", now, () => "book2");
  assert.equal(second.state.livros.length, 2);
  assert.equal(mergeLibrera(emptyReading(), [{ ...p, tempo_ms: now + 86400000 }], "principal", now).ignored, 1);
});

test("projeção não preserva conteúdo da página ou campos desconhecidos", () => {
  const parsed = libreraPositions({ "Exemplo.epub": { p: .3, t: 1, pt: "CONTEUDO_PRIVADO", path: "CAMINHO_PRIVADO", extra: "NAO_EXPORTAR" } });
  assert.equal(JSON.stringify(parsed).includes("PRIVADO"), false);
  assert.deepEqual(Object.keys(parsed.posicoes[0]), ["chave", "progresso_bp", "tempo_ms"]);
});

test("armazenamento inválido e futuro não são transformados em progresso zero", () => {
  assert.throws(() => readReading({ getItem: () => "{broken" }));
  assert.throws(() => pacing([{ dia: "2026-10-15", progresso_bp: 1000 }], { today: "2026-10-14" }));
  assert.throws(() => libreraPositions([]));
});

test("nome contendo só extensão tem título válido; nome vazio é ignorado", () => {
  const now = Date.parse("2026-10-14T20:00:00");
  const parsed = libreraPositions({ ".epub": { p: .1, t: now }, "   ": { p: .5, t: now } });
  assert.equal(parsed.ignorados, 1);
  const result = mergeLibrera(emptyReading(), parsed.posicoes, "principal", now, () => "book1");
  assert.equal(result.state.livros[0].titulo, ".epub");
  assert.equal(validateReading(result.state), true);
});
