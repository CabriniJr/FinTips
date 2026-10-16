# Extratos registrados no Android — preview 10

A preview 9 apenas conferia o saldo em memória. Não salvava o arquivo nem
criava histórico financeiro; sair da tela perdia o resultado. Esses arquivos
antigos precisam ser importados novamente, pois não há registro para migrar.

Em **Finanças**, escolher um OFX/QFX de uma conta em BRL e tocar em
**Importar e registrar contexto**. Saldo anterior é opcional, em detalhes.
A importação salva a fonte, mostra recibo, lista o histórico e atualiza o
resumo por mês. Contexto e Conversa mostram quantas movimentações estão
registradas. Reabrir/atualizar o APK preserva as fontes; desinstalar ou limpar
os dados do app apaga a guarda privada.

## Guarda e contexto

Autoridade única desta fonte: `noBackupFilesDir/extratos-v1.json`, schema 1,
com `AtomicFile`, sal local e até 20 fontes (1 MB cada; arquivo de guarda até
16 MB). O descritor de guarda vem de `ExtratosLocais`, junto do estado nativo;
a tela não mantém lista/cópia paralela no localStorage. Não é arquivo do
Workspace Python e não muda a autoridade YAML do desktop. A migração P2 futura
deve incluir esta fonte, seu schema e o descritor no registro unificado.

Cada fonte conserva OFX em texto, instante da importação, referência opaca e
saldo inicial quando informado. O caminho não tem nome de banco ou conta.
Nenhum desses arquivos, salts ou dados reais pertence ao Git. O app exclui
backups Android e usa também `noBackupFilesDir` para esta fonte.

- Arquivo igual é idempotente; informar o saldo inicial depois atualiza a
  conferência sem duplicar a fonte.
- Períodos sobrepostos são deduplicados por conta/banco, FITID **original**,
  instante e valor. O leitor mantém seu ID desambiguado, mas fornece o original
  só localmente ao importador. Estorno com FITID reutilizado não desaparece.
- Entradas/saídas mensais são observações por sinal, sem inferir salário,
  despesa, causa, categoria ou intenção. Transferência própria também movimenta
  a conta. Classificação fica `pendente` e saldo disponível fica `null`.
- Falta de saldo inicial ou saldo bancário declarado → não conferido. Diferença
  não impede guardar a evidência: aparece como divergência, nunca como saldo
  disponível validado. Sem dado não vira zero.
- Fonte inválida/truncada, sem identificação de conta/transação, moeda não BRL,
  limite excedido ou histórico ilegível recusa a gravação e preserva o anterior.
- Remover uma fonte exige ação explícita e recalcula o contexto das restantes.

`statement_context.py` e `ContextoExtrato.kt` geram o mesmo contrato observado,
com ouro Python/Kotlin. A camada de transporte valida a lista fechada de
campos: contagens, datas/períodos, valores inteiros, meses e estados de
conciliação/classificação. Não envia banco, conta, nome, memo, FITID, sal,
referência do arquivo ou contraparte real.

Ao usar a **API do assistente**, o Android lê esse depósito novamente e inclui
o bloco `financas_importadas` no contexto da chamada autorizada. O WebView não
fornece esse bloco nem controla sua sensibilidade. Importar não faz uma chamada
paga e não exige reconfigurar a chave. O cálculo não vem de uma resposta da IA.

Esta correção ainda não integra o motor financeiro completo, categorias,
perfil, cenários, scores ou ferramentas de consulta transação a transação.
O MCP legado mantém seu protocolo/escopos anteriores e ainda não recebe esse
resumo. A política/catálogo P1/P3 e a visão global do agente devem consumir a
mesma fonte, sem copiá-la para outro banco ou ampliar grants implicitamente.

## Cópia local

**Finanças → Salvar cópia dos extratos** salva em Downloads/FinTips, sem
provedor remoto de destino. A cópia inclui fontes originais em texto e sal;
é sensível. A cópia de Vida/Leitura/Conversa é separada e não inclui esse
arquivo nativo. Se a guarda estiver ilegível, a cópia de recuperação conserva
os bytes originais em base64, sem sobrescrevê-los. Restauração automatizada dessa cópia ainda não foi implementada;
os OFX originais podem ser reimportados normalmente.

## Verificação

- Ouro: vazio, saldo opcional, diferença, saldo ausente, repetição,
  sobreposição/estorno/FITID literal com `#`, e contas de bancos distintos.
- Instrumentação Android: instância nova lê o histórico; repetição não duplica;
  saldo informado depois confere; fonte inválida e arquivo corrompido não
  sobrescrevem; fonte bruta está na cópia local, ausente do contexto.
- HTTPS Android com API simulada: valores do contexto presente no corpo e
  canários de banco/conta/origem/destino/FITID ausentes.
- UI em 320/390/768: importação, recibo, repetição, reload, erro com histórico
  preservado e contexto em outras abas. Bridge simulado nesse teste; não é
  prova de I/O Android nem avaliação de inteligência do modelo.
