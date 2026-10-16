#!/usr/bin/env python3
"""Conferência estrutural do design; não valida semântica nem implementa o agente."""
from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "docs" / "contratos"
schema = json.loads((CONTRACTS / "agente-turno-v1.schema.json").read_text())
Draft202012Validator.check_schema(schema)
validator = Draft202012Validator(schema)
examples = {}
for path in sorted((CONTRACTS / "exemplos-agente").glob("*.json")):
    value = json.loads(path.read_text())
    validator.validate(value)
    examples[path.name] = value
assert len(examples) == 5, "Conferir a lista de exemplos ao alterar o contrato."

mutations = []
noop = examples["01-conversa-sem-cadastro.json"]
study = examples["03-estudo-livro-agenda.json"]
assert study["resultado"]["comandos"][0]["campos"]["titulo"]["tipo"] == "texto_planejamento", \
    "O agente pode redigir títulos de planejamento sem depender de texto pré-extraído."

value = deepcopy(noop)
value["extrato_bruto"] = "campo que não pertence ao envelope"
mutations.append(("campo extra", value))
value = deepcopy(noop)
value["resultado"]["comandos"] = study["resultado"]["comandos"]
mutations.append(("noop com comandos", value))
value = deepcopy(study)
value["resultado"]["confirmado"] = True
mutations.append(("autoaprovação pelo agente", value))

# Localiza uma quantidade sem acoplar a verificação à posição do comando.
for name, replacement in [
    ("quantidade fracionária", {"tipo": "quantidade", "valor": 30.5, "unidade": "minutos"}),
    ("unidade desconhecida", {"tipo": "quantidade", "valor": 30, "unidade": "reais"}),
    ("texto livre em referência", {"tipo": "referencia", "ref": "um nome privado"}),
]:
    value = deepcopy(study)
    command = next(c for c in value["resultado"]["comandos"] if "duracao_estimada" in c.get("campos", {}))
    command["campos"]["duracao_estimada"] = replacement
    mutations.append((name, value))
value = deepcopy(study)
del value["resultado"]["comandos"][0]["proveniencia"]
mutations.append(("proveniência ausente", value))

for name, value in mutations:
    assert not validator.is_valid(value), f"Adulteração aceita: {name}"
print(f"Contrato proposto: {len(examples)} exemplos válidos; {len(mutations)} adulterações recusadas.")

# O contexto reutiliza o mesmo contrato de valores do turno, sem buscar schemas
# na rede. Isto valida somente forma/paginação; não prova a cobertura do app.
context_schema = json.loads((CONTRACTS / "agente-contexto-v1.schema.json").read_text())
Draft202012Validator.check_schema(context_schema)
registry = Registry().with_resource(schema["$id"], Resource.from_contents(schema))
context_validator = Draft202012Validator(context_schema, registry=registry)
context = json.loads((CONTRACTS / "exemplos-contexto" / "01-panorama-paginado.json").read_text())
context_validator.validate(context)
context_mutations = []
value = deepcopy(context)
value["pagina"]["proximo_cursor"] = None
context_mutations.append(("página parcial sem cursor", value))
value = deepcopy(context)
value["pagina"]["estado"] = "completa"
context_mutations.append(("página completa com continuação", value))
value = deepcopy(context)
del value["base_revisao"]
context_mutations.append(("snapshot sem revisão", value))
value = deepcopy(context)
value["pagina"]["itens"][0]["campos"]["titulo"] = {"tipo": "texto_livre_desconhecido", "valor": "texto"}
context_mutations.append(("valor fora do contrato comum", value))
for name, value in context_mutations:
    assert not context_validator.is_valid(value), f"Adulteração aceita: {name}"
print(f"Contexto proposto: 1 exemplo válido; {len(context_mutations)} adulterações recusadas.")
print("Conferência de forma apenas; interpretação, cobertura, escopo e efeitos ainda não implementados.")
