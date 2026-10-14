# UI de vida para celular

Esta entrega evolui o painel React existente para uma interface responsiva de
vida. O destino continua sendo o app Kotlin/Compose; aqui já é possível testar
os fluxos no navegador, antes de ligar os adaptadores nativos.

## Navegação

- **Hoje:** tarefas do dia, progresso registrado e acesso às seis áreas.
- **Vida:** abas Força, Movimento, Saúde, Estudos, Foco e Finanças, alinhadas a
  FOR/AGI/VIT/INT/FOC/OURO; Estudos inclui tracker de leitura e pacing local.
- **Finanças:** as nove seções anteriores, agora dentro da área financeira.
- **Planos:** planos de vida com motivo, próximo passo, prazo opcional e
  conclusão; metas financeiras continuam no motor e não são duplicadas aqui.
- **Contexto:** registro manual de minutos por app, capacidades Android/iPhone
  em estudo e download de cópia local.

O desenho usa navegação inferior, controles de toque, safe areas, formulários
em bottom sheets no celular, foco por teclado e tema escuro. A linguagem segue
as interfaces de Neon Genesis Evangelion indicadas pelo usuário:
[tokens e regras visuais](LINGUAGEM-VISUAL.md). Títulos usam Barlow Condensed
distribuída localmente; texto usa fontes do sistema. Não há requisição a
Google Fonts. [Contratos para o motor e app nativo](NECESSIDADES-UI.md).

## Tarefas e registros

Uma tarefa pode valer só para o dia escolhido ou repetir diariamente a partir
dele. Cumprimento pertence ao dia local e tem origem `usuario`. Amanhã a tarefa
diária volta pendente; cumprir ou desmarcar um dia não altera os outros.
Excluir oferece desfazer. As barras medem apenas tarefas registradas, sem XP
ou números de exemplo carregados no produto.

As áreas seguem as siglas do modelo Kotlin, mas a UI ainda não executa esse
motor para tarefas nem sincroniza seus registros com o workspace. O estado
web inclui tarefas pontuais e usa um schema local próprio. A ligação ao modelo
nativo e a migração da persistência são uma próxima entrega, não uma capacidade
implícita desta UI.

## Persistência e PII

Tarefas, motivos, planos e anotações de uso ficam no `localStorage` deste
navegador, na chave `fintips.vida.v1`. Nenhuma dessas operações chama a API
financeira ou MCP. O arquivo de backup é gerado no client e contém dados
pessoais; não há upload ou sincronização remota. Esta entrega oferece download
de cópia, não uma ferramenta de restauração automática.

Abrir outra origem, navegador ou aparelho não compartilha esse estado. Limpar
os dados do navegador pode apagá-lo. Isso é persistência local do protótipo,
não armazenamento cifrado: a proteção em repouso e a migração para o app
nativo precisam de uma implementação própria.

Se a leitura encontrar JSON inválido ou schema desconhecido, preserva o
conteúdo e pausa a edição. Se a gravação falhar, informa que a alteração não
foi salva. Os erros exibidos não repetem o conteúdo armazenado.

As chamadas financeiras são permitidas somente em origem loopback, usando o
motor local do FinTips. Uma cópia hospedada da UI continua usando tarefas e
planos locais, mas não envia extratos e patrimônio a uma API remota. O usuário
precisa do motor no próprio aparelho para usar essa parte.

## O que ainda não está ligado

- Coleta automática de estatísticas e permissões Android/iOS.
- Compartilhamento do novo contexto com ChatGPT.
- APK, app iOS ou interface Compose nativa.
- Migração e sincronização entre navegadores, dispositivos e motor Kotlin.
- Sincronização direta com a nuvem do Librera; a importação de arquivo local
  já funciona. [Discovery do formato e limites do pacing](LEITURA-LIBRERA.md).

As capacidades de coleta aparecem como “Em estudo / Ainda não conectado”.
Minutos digitados pela pessoa são marcados como registro manual, sem fingir
uma leitura de sensor. O discovery técnico está na entrega independente
`docs/DISCOVERY-CELULAR.md`.

## Validar

```bash
cd web
npm ci
npm test
npm run build
npm run dev
```

O build continua em `fintips/web`, incluído no pacote Python. Os testes de
estado cobrem recorrência, conclusão por dia, calendário local, exclusão,
valores ausentes e preservação de dados inválidos. A QA de navegador usou
dados sintéticos, larguras de 320 a 1280 px, fluxo completo de tarefas/planos,
registro manual, backup, tema escuro e inspeção das requisições de rede.
