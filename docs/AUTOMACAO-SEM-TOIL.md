# Automação que cabe na vida

Diretriz do usuário em 14/10/2026: automatizar tudo que for possível para
reduzir o trabalho de manter registros. **Configurar uma vez; acompanhar sem
preencher todos os dias.** Registro manual é alternativa/correção. PII,
histórico bruto e credenciais ficam exclusivamente no client, inclusive em
trabalho de fundo. O APK atual ainda usa registro/importação manual.

## Ordem e delegação

| ID | Entrega | Responsável | Pronto quando |
|---|---|---|---|
| A-01 / M-01 | Librera com fonte persistente | Claude: adaptador solicitado; Codex: conexão e apresentação | seleção/autorização sobrevive a reiniciar; nova posição aparece sem reimportar nem digitar; pacing recalcula localmente |
| A-02 | Tempo por aplicativo, Android UsageStats | Claude: coletor solicitado; Codex: permissão e estados | após autorização, atualização ao retomar e em fundo quando permitido; medida com fonte, período e cobertura |
| A-03 | Passos, atividade e sono, Health Connect | Claude: coletor solicitado; Codex: escolha de dados e estados | tipos autorizados uma vez; novas medidas chegam sem digitação; sono depende de fonte que o registrou |
| A-04 | Novos extratos em pasta autorizada | Claude: ingestão local solicitada; Codex: conexão | detectar arquivos novos, deduplicar, preservar estado em arquivo inválido; depende do motor financeiro no aparelho |
| A-05 | Janelas da agenda | Claude: agregação local solicitada; Codex: conexão | disponibilidade vem da agenda autorizada; eventos/títulos brutos não saem do client |
| UI-03 | Conectar fontes uma vez | Codex: próxima implementação assumida | fonte, estado, frescor, pausa, reconexão e correção; fonte ativa dispensa transcrição diária |

Os pedidos ao Claude aguardam aceite nos docs. São critérios de implementação,
não declarações de coleta já funcionando. O adaptador deve viver em arquivos
novos, com escopo registrado no canal antes de tocar na faixa do outro agente.

## Librera: primeiro fluxo a fechar

1. Escolher perfil e arquivo/diretório sincronizado acessível pelo seletor
   nativo. Informar que a conexão acompanhará futuras posições.
2. Conservar acesso persistente quando o provedor oferecer essa permissão e
   comprová-lo após reiniciar. O seletor atual do APK faz importação pontual;
   acesso temporário não vira conexão persistente por suposição.
3. Atualizar ao abrir/retomar e, quando possível, via agendamento Android.
   Trabalho em fundo não garante execução pontual: suspensão, economia de
   bateria e force-stop podem atrasar. Mostrar atraso, sem inventar dados.
4. Projetar somente nome base local, `p` e `t`; descartar `pt`, caminhos e extras.
   Deduplicar pelo timestamp da fonte, não pela hora do job.
5. Persistir a data real da posição. Ler o mesmo snapshot em cinco dias
   diferentes não cria cinco dias de leitura nem nova base para o pacing.

O arquivo guarda a última posição; observação diária pode perder mudanças
intermediárias. Não chamar isso de sessão medida. [Formato e cálculo](LEITURA-LIBRERA.md)
continuam sendo o contrato. Drive direto, se necessário, exige autorização
por arquivo e tokens no aparelho; não assumir acesso a todos os arquivos de
outro app com `drive.file` nem criar backend FinTips com cópia de PII.

## Contrato para a UI

A fonte entrega snapshot versionado do repositório local. A tela não mantém
um segundo histórico concorrente. O schema de tarefas web atual só aceita
origem `usuario`; a ponte de sensores exige migração explícita, não inserir
`sensor` em um formato que hoje o recusaria. Leitura já separa `usuario`/`librera`.

| Conceito | Contrato |
|---|---|
| Identidade | ID opaco local; URI/tokens no adaptador, fora de logs e contexto remoto |
| Estado | não conectada, ativa, pausada, precisa permissão, erro, não suportada |
| Execução | última tentativa/sucesso; consultar com sucesso não prova dado recente |
| Medida | timestamp original, período, unidade, origem e ID para deduplicação |
| Cobertura | completa/parcial/desconhecida, conforme a evidência disponível |
| Recuperação | erro categorizado sem conteúdo pessoal; histórico conservado; reautorizar quando necessário |
| Controle | pausar/desconectar, corrigir medida, rever efeito e retomar a fonte |

Vazio, falha e intervalo não observado não significam zero. Correção da pessoa
prevalece com escopo explícito; não apagá-la na próxima coleta. Primeiro plano
e worker usam o mesmo parser/repositório e respeitam pausa, revogação,
concorrência e economia de bateria; não fazer polling permanente.

## Eliminar confirmações desnecessárias

O motor de vida já aceita `sensor` como evidência de cumprimento. Uma missão
objetiva pode usar condição, fonte e período escolhidos uma vez pela pessoa.
O motor registra o atendimento automaticamente com proveniência/critério;
a UI mostra e permite corrigir, sem checklist de confirmação diária.

A medida precisa provar a condição: passos não provam treino de força,
abrir o leitor não prova compreensão e janela livre não prova tarefa feita.
Posição em 100% continua sendo posição no fim, não declaração automática de
leitura/compreensão. Motivos e avaliação de escolhas não vêm de sensores.

Pacing, disponibilidade e contexto local se recalculam automaticamente.
Alterar prazo ou intenção exige ação da pessoa ou regra de ajuste previamente
escolhida, com limites e histórico; não mover metas para esconder atraso.

## Experiência e aceite

- Hoje apresenta o que já foi observado e o próximo passo útil; fonte/frescor
  consultáveis. Manual fica como alternativa e correção.
- Permissão no momento de conectar, reconexão quando necessária. Indisponibilidade
  não cria dívida de preenchimento nem pedido repetido a cada abertura.
- Perguntar apenas sobre lacuna que muda uma decisão, agrupar e permitir adiar.
  Notificações opcionais e limitadas, sem lembrete diário para compensar integração ausente.
- Medir localmente ações de transcrição por semana, proporção automática,
  lacunas e reconexões. Não enviar analytics com contexto pessoal nem contar
  consultas repetidas como novas observações.

Aceite por adaptador: configurar, usar a fonte normalmente, fechar/reabrir
FinTips e reiniciar o aparelho; atualizar sem redigitação. Exercitar revogação,
fonte fora do ar, arquivo inválido, snapshot repetido, dado atrasado e coletores
concorrentes. Avaliação prolongada deve confirmar ausência de manutenção
diária; esse teste de uso ainda não foi realizado.
