"""Contexto do usuário: núcleo demarcado + fatos livres.

O híbrido existe porque as duas coisas são verdade ao mesmo tempo:

- Há perguntas que valem para qualquer pessoa — onde mora, se tem cartão de
  crédito, se a renda é fixa. Essas ficam no **núcleo**, com chave estável, para
  que o motor saiba calcular a lacuna e o impacto sem depender do agente.
- E há o que só existe na vida daquela pessoa — "divido a internet com meu
  irmão", "todo mês mando X para a minha avó", "meu trabalho reembolsa
  transporte". Essas são **fatos livres**: o agente cria a chave que precisar.

O app valida a forma e calcula o impacto de não saber. Quem formula a pergunta,
conversa e conclui é o agente.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .contracts import Fato, Proveniencia, agora

CONTEXT_SCHEMA = 1


@dataclass
class ChaveDoNucleo:
    chave: str
    o_que_e: str
    porque_importa: str          # qual cálculo muda — texto do APP, não do agente
    tipo: str = "texto"
    afeta: tuple[str, ...] = ()  # cálculos afetados
    peso: float = 1.0            # multiplicador de impacto quando ausente
    opcoes: tuple[str, ...] = () # quando faz sentido restringir; vazio = livre


# Núcleo: o mínimo que muda conta para qualquer pessoa. Note que NENHUM texto
# aqui é uma pergunta pronta — é a descrição do que falta e do que isso afeta.
# A pergunta é trabalho do agente, que sabe com quem está falando.
NUCLEO: tuple[ChaveDoNucleo, ...] = (
    ChaveDoNucleo(
        chave="moradia.situacao",
        o_que_e="como a pessoa mora e quanto isso custa por mês",
        porque_importa=(
            "o custo de moradia é o maior componente do custo de vida e define a "
            "reserva de emergência; se ele não aparece no extrato, ou alguém paga "
            "por ela, ou sai de outra conta — e as duas hipóteses mudam a projeção"
        ),
        afeta=("reserva", "projecao", "custo_de_vida"), peso=1.4,
        opcoes=("com_familia", "com_familia_contribuo", "aluguel", "proprio", "republica"),
    ),
    ChaveDoNucleo(
        chave="cartao_credito.usa",
        o_que_e="se há fatura de cartão fora desta conta",
        porque_importa=(
            "se existe fatura não importada, parte do consumo real está invisível e "
            "a taxa de poupança calculada está otimista"
        ),
        afeta=("taxa_poupanca", "despesa", "score"), peso=1.3,
        opcoes=("nao", "sim_mesmo_banco", "sim_outro_banco"),
    ),
    ChaveDoNucleo(
        chave="renda.natureza",
        o_que_e="se a renda é fixa, variável ou mista, e quais fontes se repetem",
        porque_importa=(
            "entrada pontual não pode entrar na capacidade de aporte; se entrar, o "
            "plano fecha no papel e não na vida"
        ),
        afeta=("capacidade_de_aporte", "planos", "projecao"), peso=1.1,
        opcoes=("fixa", "mista", "variavel"),
    ),
    ChaveDoNucleo(
        chave="patrimonio.contas_externas",
        o_que_e="dinheiro guardado fora desta conta",
        porque_importa=(
            "patrimônio incompleto subestima a reserva e trava compras que na "
            "verdade cabem"
        ),
        afeta=("reserva", "avaliar_compra"), peso=1.1,
        opcoes=("nao", "sim_pequeno", "sim_relevante"),
    ),
    ChaveDoNucleo(
        chave="reserva.alvo_meses",
        o_que_e="quantos meses de despesa a reserva deve cobrir",
        porque_importa=(
            "define o excedente disponível — o número que libera ou trava cada "
            "compra grande"
        ),
        tipo="numero", afeta=("reserva", "avaliar_compra"), peso=0.8,
    ),
    ChaveDoNucleo(
        chave="objetivos.horizonte",
        o_que_e="o que a pessoa quer fazer com o dinheiro nos próximos meses",
        porque_importa=(
            "sem objetivo declarado o score de planos fica na média e o consultor "
            "de compras não tem contra o que comparar uma compra nova"
        ),
        tipo="lista", afeta=("planos", "score", "avaliar_compra"), peso=1.0,
    ),
    ChaveDoNucleo(
        chave="dependentes.quantos",
        o_que_e="pessoas que dependem financeiramente do usuário",
        porque_importa="muda o alvo de reserva e a leitura de repasses recorrentes",
        tipo="numero", afeta=("reserva", "pessoas"), peso=0.7,
    ),
)

NUCLEO_POR_CHAVE = {k.chave: k for k in NUCLEO}


class ContextStore:
    """Fatos sobre o usuário, com proveniência. Chave do núcleo ou livre."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.fatos: dict[str, Fato] = {}
        self._load()

    # ------------------------------------------------------------------ io
    def _load(self) -> None:
        if not self.path.exists():
            return
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        for d in data.get("fatos") or []:
            self.fatos[d["chave"]] = Fato.from_dict(d)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": CONTEXT_SCHEMA,
                    "atualizado_em": agora(),
                    "fatos": [f.to_dict() for f in sorted(self.fatos.values(), key=lambda x: x.chave)],
                },
                allow_unicode=True, sort_keys=False,
            ),
            encoding="utf-8",
        )

    # -------------------------------------------------------------- escrita
    def gravar(
        self,
        chave: str,
        valor: Any,
        *,
        tipo: str = "",
        proveniencia: Proveniencia | None = None,
        expira_em: str | None = None,
    ) -> Fato:
        """Grava um fato. Chave do núcleo ou qualquer outra que o agente criar.

        Um fato de autoridade menor não sobrescreve um de autoridade maior: o
        palpite do agente não apaga o que o usuário afirmou.
        """
        if not chave or " " in chave:
            raise ValueError("chave deve ser um identificador sem espaços, ex.: 'transporte.reembolsado'")
        prov = proveniencia or Proveniencia(origem="agente", confianca=0.8)
        atual = self.fatos.get(chave)
        if atual and atual.proveniencia.autoridade > prov.autoridade and not atual.vencido():
            return atual
        nucleo = NUCLEO_POR_CHAVE.get(chave)
        fato = Fato(
            chave=chave,
            valor=valor,
            tipo=tipo or (nucleo.tipo if nucleo else _infere_tipo(valor)),
            proveniencia=prov,
            expira_em=expira_em,
            substituiu=str(atual.valor) if atual and atual.valor != valor else None,
        )
        self.fatos[chave] = fato
        self.save()
        return fato

    def esquecer(self, chave: str) -> bool:
        if chave in self.fatos:
            del self.fatos[chave]
            self.save()
            return True
        return False

    # -------------------------------------------------------------- leitura
    def valor(self, chave: str, padrao: Any = None) -> Any:
        f = self.fatos.get(chave)
        if not f or f.vencido():
            return padrao
        return f.valor

    def conhecido(self, chave: str) -> bool:
        f = self.fatos.get(chave)
        return bool(f and not f.vencido())

    def todos(self) -> list[dict]:
        return [f.to_dict() for f in sorted(self.fatos.values(), key=lambda x: x.chave)]

    def livres(self) -> list[dict]:
        """Fatos que o agente criou fora do núcleo — a parte específica da pessoa."""
        return [f.to_dict() for f in self.fatos.values() if f.chave not in NUCLEO_POR_CHAVE]

    # -------------------------------------------------------------- lacunas
    def lacunas(self, base: dict) -> list[dict]:
        """O que falta saber do núcleo, com o impacto em reais de não saber.

        O impacto é uma estimativa deliberadamente grosseira: serve para ordenar
        a fila, não para virar número em relatório. O texto do `porque_importa`
        é do app (descreve o cálculo); a pergunta é do agente.
        """
        despesa = float(base.get("despesa_media_mes", 0) or 0)
        out = []
        for k in NUCLEO:
            if self.conhecido(k.chave):
                continue
            out.append({
                "chave": k.chave,
                "o_que_e": k.o_que_e,
                "porque_importa": k.porque_importa,
                "tipo": k.tipo,
                "opcoes": list(k.opcoes),
                "afeta": list(k.afeta),
                "impacto_estimado_mes": round(despesa * 0.15 * k.peso, 2),
            })
        vencidos = [f for f in self.fatos.values() if f.vencido()]
        for f in vencidos:
            out.append({
                "chave": f.chave,
                "o_que_e": f"fato vencido em {f.expira_em}",
                "porque_importa": "a informação tinha prazo e pode não valer mais",
                "tipo": f.tipo,
                "opcoes": [],
                "afeta": [],
                "impacto_estimado_mes": round(despesa * 0.05, 2),
            })
        return sorted(out, key=lambda d: d["impacto_estimado_mes"], reverse=True)

    def cobertura(self) -> dict:
        conhecidas = [k.chave for k in NUCLEO if self.conhecido(k.chave)]
        return {
            "nucleo_conhecido": len(conhecidas),
            "nucleo_total": len(NUCLEO),
            "cobertura_pct": round(len(conhecidas) / len(NUCLEO) * 100),
            "faltando": [k.chave for k in NUCLEO if not self.conhecido(k.chave)],
            "fatos_livres": len(self.livres()),
            "por_origem": _conta_origens(self.fatos.values()),
        }

    def resumo(self) -> dict:
        """O que o agente deve ler antes de aconselhar."""
        return {
            "nucleo": {k.chave: self.valor(k.chave) for k in NUCLEO},
            "especificos": {f["chave"]: f["valor"] for f in self.livres()},
            "cobertura": self.cobertura(),
        }


def _infere_tipo(valor: Any) -> str:
    if isinstance(valor, bool):
        return "bool"
    if isinstance(valor, (int, float)):
        return "numero"
    if isinstance(valor, (list, tuple)):
        return "lista"
    return "texto"


def _conta_origens(fatos) -> dict:
    out: dict[str, int] = {}
    for f in fatos:
        o = f.proveniencia.origem
        out[o] = out.get(o, 0) + 1
    return out
