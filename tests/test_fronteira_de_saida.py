"""A fronteira de saída: o que atravessa a rede, campo por campo.

O esclarecimento do usuário em 16/10/2026 desenhou a linha num lugar estreito:
texto de planejamento sai, valor sai, **identidade financeira não sai**. O
agente precisa ler "certificação de observabilidade" para decompor um
objetivo; ele não precisa saber para qual estabelecimento o dinheiro foi.

Estes testes travam três coisas que, sem eles, se desfazem em silêncio:

1. **O default é fechar.** Campo que ninguém classificou não sai.
2. **O portão cobra a classificação.** Fechar em silêncio é seguro e é também
   como se perde um campo que devia sair — então a omissão quebra o `--conferir`.
3. **A tela não mente.** O que sai pelo tipo próprio a IA *recebe*; chamar isso
   de "a IA nunca recebe" seria repetir o erro da lista escrita à mão.

O que estes testes **não** podem provar, e que não deve ser prometido depois:
que o app detecta o nome de um estabelecimento que ninguém cadastrou. Ele não
detecta, e nenhuma expressão regular detecta. A proteção é o campo não sair.
"""

from __future__ import annotations

import dataclasses as dc
from datetime import date, datetime
from decimal import Decimal

import pytest

from fintips import configuracao as cfg
from fintips.contracts import (
    FECHADO,
    POLITICAS_DE_SAIDA,
    POR_TIPO,
    TIPOS_DA_FRONTEIRA,
    UNIDADES,
    CampoAberto,
    alias_financeiro,
    conferir_fronteira,
    politica_do_campo,
    projetar,
)


# --------------------------------------------------------------------------
# O registro é honesto com o código
# --------------------------------------------------------------------------

def test_a_fronteira_classifica_todo_campo_de_todo_tipo():
    r = conferir_fronteira()
    assert r["ok"], r


def test_todo_tipo_declarado_resolve_para_uma_classe_de_verdade():
    import importlib

    for t in TIPOS_DA_FRONTEIRA:
        modulo, _, classe = t.classe.partition(":")
        alvo = getattr(importlib.import_module(modulo), classe)
        assert dc.is_dataclass(alvo), t.nome


def test_campo_novo_na_classe_quebra_o_portao(monkeypatch):
    """A sabotagem: acrescentar um campo a um tipo da fronteira sem classificar.

    É exatamente o que vai acontecer na vida real — alguém acrescenta um campo
    a `Etapa` e não passa por aqui. O campo não sai, porque fechar é o default;
    o que este teste garante é que ninguém descubra isso meses depois.
    """
    etapa = POR_TIPO["etapa"]
    sem_um = dc.replace(etapa, abre=etapa.abre[1:])
    monkeypatch.setattr(
        "fintips.contracts.TIPOS_DA_FRONTEIRA",
        tuple(sem_um if t.nome == "etapa" else t for t in TIPOS_DA_FRONTEIRA),
    )
    r = conferir_fronteira()
    assert not r["ok"]
    assert r["campo_sem_politica"] == [f"etapa.{etapa.abre[0].campo}"]


def test_politica_para_campo_que_sumiu_quebra_o_portao(monkeypatch):
    etapa = POR_TIPO["etapa"]
    inventado = CampoAberto("campo_que_nao_existe", "rotulo_tecnico", "nada")
    monkeypatch.setattr(
        "fintips.contracts.TIPOS_DA_FRONTEIRA",
        tuple(dc.replace(etapa, abre=etapa.abre + (inventado,))
              if t.nome == "etapa" else t for t in TIPOS_DA_FRONTEIRA),
    )
    r = conferir_fronteira()
    assert not r["ok"]
    assert r["declarado_e_fora_do_codigo"] == ["etapa.campo_que_nao_existe"]


def test_valor_financeiro_sem_unidade_quebra_o_portao(monkeypatch):
    """Centavo sem unidade declarada é como centavo vira real na outra ponta."""
    etapa = POR_TIPO["etapa"]
    trocado = tuple(
        dc.replace(c, unidade="") if c.campo == "custo" else c for c in etapa.abre
    )
    monkeypatch.setattr(
        "fintips.contracts.TIPOS_DA_FRONTEIRA",
        tuple(dc.replace(etapa, abre=trocado) if t.nome == "etapa" else t
              for t in TIPOS_DA_FRONTEIRA),
    )
    r = conferir_fronteira()
    assert not r["ok"]
    assert r["valor_financeiro_sem_unidade"] == ["etapa.custo"]


def test_toda_abertura_carrega_porque():
    """Não sair é o padrão e não precisa de defesa. Sair precisa."""
    for t in TIPOS_DA_FRONTEIRA:
        for c in t.abre:
            assert c.porque.strip(), f"{t.nome}.{c.campo} abre sem dizer por quê"
            assert c.politica in POLITICAS_DE_SAIDA
            if c.politica == "valor_financeiro":
                assert c.unidade in UNIDADES


def test_nenhum_campo_esta_nos_dois_lados():
    for t in TIPOS_DA_FRONTEIRA:
        abertos = {c.campo for c in t.abre}
        assert not abertos & set(t.nao_sai_neste_campo), t.nome
        assert not set(t.fecha) & set(t.projeta_a_parte), t.nome


# --------------------------------------------------------------------------
# O default é fechar
# --------------------------------------------------------------------------

def test_campo_nao_declarado_e_fechado():
    assert politica_do_campo("etapa", "campo_inventado") == FECHADO
    assert politica_do_campo("tipo_inventado", "titulo") == FECHADO


def test_projetar_recusa_tipo_de_fora_da_fronteira():
    with pytest.raises(ValueError, match="não está na fronteira"):
        projetar("tipo_que_nao_existe", {})


def test_campo_fechado_nao_aparece_nos_campos_projetados():
    out = projetar("transacao", {"memo_raw": "PIX LOJA DO ZE", "flow": "expense"})
    assert "memo_raw" not in out["campos"]
    assert out["campos"]["flow"] == "expense"
    retido = next(r for r in out["retidos"] if r["campo"] == "memo_raw")
    assert retido["politica"] == FECHADO


def test_o_valor_do_campo_retido_nunca_viaja_no_motivo():
    """O nome do campo retido sai; o valor não.

    Saber que existe uma lacuna é o que permite ao agente pedir a informação
    pelo caminho certo. Mandar o valor dentro da explicação seria o vazamento
    com outro nome.
    """
    segredo = "PIX ENVIADO PARA FULANO DE TAL CPF 000.000.000-00"
    out = projetar("transacao", {"memo_raw": segredo})
    assert segredo not in repr(out)


def test_campo_nao_classificado_diz_que_o_portao_cobra():
    out = projetar("etapa", {"campo_novo_de_alguem": "x"})
    assert "portão cobra" in out["retidos"][0]["porque"]


# --------------------------------------------------------------------------
# Identidade financeira: alias, e só alias
# --------------------------------------------------------------------------

def test_contraparte_sai_como_alias_do_mapa_local():
    out = projetar(
        "transacao",
        {"counterparty": "LOJA DO ZE LTDA"},
        identidades={"loja do zé ltda": "estab-7"},
    )
    assert out["campos"]["counterparty"] == {"tipo": "codigo", "valor": "estab-7"}


def test_o_mapa_casa_apesar_de_acento_e_caixa():
    """Quem escreve o mapa escreve "loja do zé"; o extrato traz "LOJA DO ZE".

    Comparar as formas cruas erra sempre, e errar aqui significa emitir
    pseudônimo onde a pessoa tinha dado um rótulo.
    """
    assert alias_financeiro(
        "PADARIA AVO MARIA", identidades={"Padaria Avó Maria": "padaria-1"}
    ) == "padaria-1"


def test_sem_mapa_o_aparelho_emite_pseudonimo_com_o_salt():
    a = alias_financeiro("LOJA NOVA", identidades={}, salt="sal-local")
    b = alias_financeiro("LOJA NOVA", identidades={}, salt="sal-local")
    assert a == b and a.startswith("PF:")
    assert "LOJA NOVA" not in a


def test_sem_mapa_e_sem_salt_a_identidade_fica_retida():
    out = projetar("transacao", {"counterparty": "LOJA NOVA"}, salt="")
    assert "counterparty" not in out["campos"]
    assert "LOJA NOVA" not in repr(out)


def test_o_nome_nao_sai_escondido_em_texto_de_planejamento():
    """A regra do plano: um nome protegido não pode sair dentro de `titulo`.

    O limite é o mapa: isto troca o que está cadastrado. Um estabelecimento
    que ninguém cadastrou não é detectado — por isso a proteção de verdade é o
    campo fechado, não a varredura.
    """
    out = projetar(
        "objetivo",
        {"titulo": "Parar de pedir na Loja do Ze", "porque": "gasto alto"},
        identidades={"loja do ze": "estab-7"},
    )
    assert out["campos"]["titulo"]["valor"] == "Parar de pedir na estab-7"
    assert out["campos"]["titulo"]["identidade_substituida"] is True
    assert "identidade_substituida" not in out["campos"]["porque"]


# --------------------------------------------------------------------------
# Valor: inteiro com unidade, nunca fração
# --------------------------------------------------------------------------

def test_dinheiro_atravessa_em_centavos_inteiros():
    out = projetar("etapa", {"custo": Decimal("1899.90")})
    assert out["campos"]["custo"] == {
        "tipo": "quantidade", "valor": 189990, "unidade": "centavos_brl",
    }


def test_centavo_arredonda_como_o_resto_do_motor():
    """HALF_EVEN, igual ao `round()` do Python e ao `arredondar()` do Kotlin."""
    assert projetar("etapa", {"custo": Decimal("10.005")})["campos"]["custo"]["valor"] == 1000
    assert projetar("etapa", {"custo": Decimal("10.015")})["campos"]["custo"]["valor"] == 1002


def test_saida_de_dinheiro_mantem_o_sinal():
    """Fluxo negativo é metade do P8: comparar cenário sem sinal não compara nada."""
    out = projetar("transacao", {"amount": Decimal("-128.45")})
    assert out["campos"]["amount"]["valor"] == -12845


def test_data_atravessa_em_iso_e_nao_como_objeto_do_python():
    out = projetar("etapa", {"prazo": date(2026, 11, 3)})
    assert out["campos"]["prazo"] == "2026-11-03"
    out = projetar("transacao", {"ts": datetime(2026, 10, 16, 9, 30)})
    assert out["campos"]["ts"] == "2026-10-16T09:30:00"


def test_none_atravessa_como_none_e_nao_como_zero():
    """Sem base é `null`, nunca zero — a regra dos indicadores vale aqui."""
    out = projetar("missao", {"valor_mensal": None})
    assert out["campos"]["valor_mensal"] is None


# --------------------------------------------------------------------------
# As decisões de produto que ficaram registradas em código
# --------------------------------------------------------------------------

def test_causa_e_o_tipo_mais_fechado():
    """Causa explica um padrão do extrato, e a tabela do plano não a libera.

    O `enunciado` está nas palavras da pessoa sobre para onde o dinheiro vai, e
    é o lugar mais provável de um nome de estabelecimento aparecer sem ninguém
    ter decidido liberá-lo. Fica fechado até o usuário decidir.
    """
    assert politica_do_campo("causa", "enunciado") == FECHADO
    assert politica_do_campo("causa", "efeito_ref") == FECHADO
    # Decisão, sim: é uma bifurcação de compra, que o plano libera.
    assert politica_do_campo("decisao", "situacao") == "texto_planejamento"


def test_proveniencia_atravessa_porque_e_ela_que_separa_palpite_de_fato():
    out = projetar("proveniencia", {"origem": "heuristica", "porque": "cadência mensal"})
    assert out["campos"]["origem"] == "heuristica"
    assert politica_do_campo("proveniencia", "evidencia") == FECHADO


def test_o_que_sai_pelo_tipo_proprio_nao_e_chamado_de_fechado():
    """`objetivo.etapas` não sai neste campo — mas cada etapa sai.

    Dizer "a IA nunca recebe as etapas do objetivo" numa tela de privacidade
    seria repetir, com outra roupa, o erro da lista escrita à mão.
    """
    out = projetar("objetivo", {"etapas": [{"id": "e1"}]})
    retido = next(r for r in out["retidos"] if r["campo"] == "etapas")
    assert "tipo próprio" in retido["porque"]
    assert "fechado" not in retido["porque"]


# --------------------------------------------------------------------------
# A aba de configuração deriva disto, e não transcreve
# --------------------------------------------------------------------------

def test_a_tela_lista_os_campos_fechados_sem_escrever_a_lista(tmp_path):
    from fintips.workspace import Workspace

    ia = cfg.ligacao_com_a_ia(Workspace(tmp_path))
    nunca = ia["o_que_a_ia_nunca_recebe"]
    assert "transacao.memo_raw" in nunca
    assert "causa.enunciado" in nunca
    # O que sai pelo tipo próprio a IA recebe: não pode estar nesta lista.
    assert "objetivo.etapas" not in nunca
    assert "decisao.alternativas" not in nunca


def test_a_tela_diz_o_limite_da_substituicao_em_texto():
    fr = cfg.o_que_atravessa()
    assert fr["confere"] is True
    assert "não detecta" in fr["o_limite"] or "ninguém cadastrou" in fr["o_limite"]


def test_a_tela_nao_tem_lista_de_campos_escrita_a_mao():
    """Se alguém transcrever a fronteira para dentro do módulo da tela, quebra."""
    fonte = open("fintips/configuracao.py", encoding="utf-8").read()
    for campo in ("memo_raw", "counterparty_kind", "prazo_original", "atitude_nota"):
        assert f'"{campo}"' not in fonte, f"{campo} foi transcrito para a tela"
