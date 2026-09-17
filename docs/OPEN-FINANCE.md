# Open Finance

## Por que não dá para ser receptora direta

Para consumir as APIs reguladas do Open Finance Brasil como receptora, é
preciso: organização cadastrada no Diretório de Participantes, certificados de
transporte e assinatura (BRCAC), certificação de segurança
`BR-OF Adv. RP w/ Private Key, PAR (FAPI-BR v2)` junto à OpenID Foundation e
100% nos testes funcionais de conformidade — só depois a implementação pode ser
registrada no ambiente produtivo. Isso é infraestrutura de instituição
regulada, não de projeto pessoal.

## O caminho que funciona: agregador

Agregadores já são participantes certificados e revendem o acesso. Para uso
pessoal existe o **Meu Pluggy**: você conecta as suas próprias contas (nominais,
suas), cria uma aplicação no dashboard e recebe `clientId`/`clientSecret` para
ler seus dados via API, gratuitamente e sem prazo — vedado o uso comercial.
Os planos comerciais dos agregadores ficam na casa de milhares de reais por mês,
o que só faz sentido se o projeto virar produto.

`fintips/connectors/pluggy.py` já implementa esse caminho:

```
POST /auth              clientId + clientSecret -> apiKey (2h, só em memória)
GET  /accounts?itemId=  contas do vínculo
GET  /transactions?accountId=&from=&to=&page=   transações paginadas
```

Configuração:

```bash
setx PLUGGY_CLIENT_ID "..."
setx PLUGGY_CLIENT_SECRET "..."
setx PLUGGY_ITEM_IDS "item-1,item-2"
```

O consentimento é dado e revogado no próprio Meu Pluggy; o FinTips nunca vê
senha de banco.

## Segurança na integração

- Segredos em variável de ambiente ou keyring do Windows, nunca no repositório.
- `apiKey` em memória, renovada a cada ~110 minutos.
- Chamadas só por HTTPS para `api.pluggy.ai`; sem proxy, sem log de payload.
- Ingestão é **somente leitura**. O projeto não implementa iniciação de
  pagamento e não deve implementar: o risco não compensa o ganho.
- Dedup por `id` da transação, igual ao FITID do OFX — sincronizar duas vezes
  não duplica nada.

## Enquanto isso: OFX

O caminho OFX continua sendo o padrão e não depende de ninguém: baixar o
extrato no app do PagBank e rodar `fintips ingest`. O conector Open Finance é
uma otimização de conveniência (dados diários, sem download manual), não um
pré-requisito para o motor funcionar.

## Fontes

- [Guia de Certificação de Conformidade — Open Finance Brasil](https://openfinancebrasil.atlassian.net/wiki/spaces/OF/pages/155910145)
- [Meu Pluggy — API de Open Finance gratuita para uso pessoal](https://www.pluggy.ai/meu-pluggy)
- [Pluggy — Quickstart da API](https://docs.pluggy.ai/docs/quickstart)
