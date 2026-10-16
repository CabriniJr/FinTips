#!/usr/bin/env python3
"""Conferência estrutural do design; não valida semântica nem implementa o agente."""
from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

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

value = deepcopy(noop)
value["mensagem_privada"] = "texto que não pertence ao envelope"
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
print("Conferência de forma apenas; interpretação, escopo e efeitos ainda não implementados.")
