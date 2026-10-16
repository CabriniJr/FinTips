# Leitura: Librera e pacing local

> **Execução da fonte persistente:** [plano do agente, P2/P4](PLANO-AGENTE-DE-VIDA.md).
> Worker e UI precisam compartilhar o repositório nativo; conectar um job a
> outra cópia de dados não atualiza o tracker. Ainda não implementado.

O tracker está em **Vida → Estudos**. Aceita livro/posição manual ou importação
de uma cópia local de `app-Progress.json`. A seleção é lida em memória no
client, sem upload. A sincronização automática com a nuvem ainda não existe.

A prioridade agora é conexão única com fonte persistente e atualização local,
para dispensar reimportações diárias. [Plano e contrato de automação](AUTOMACAO-SEM-TOIL.md).

## Discovery realizado

Verificação no código público [LibreraReader](https://github.com/foobnix/LibreraReader),
commit `fe5614f`, em 14/10/2026:

- `AppProfile.java` define `APP_PROGRESS_JSON = "app-Progress.json"`;
  a organização inclui perfil e dispositivo.
- `SharedBooks.java` salva um mapa pelo nome base do arquivo. `AppBook.java`
  usa `p` como fração de 0 a 1 e `t` como timestamp Unix em milissegundos.
  `pt` pode conter texto da página; outros campos descrevem apresentação.
- O mapa guarda a última posição, não um diário completo de leitura. O
  FinTips acumula snapshots ao importar em dias diferentes. Mesmo nome base
  dentro de um perfil pode colidir; perfil separado não resolve colisão
  entre dois livros de mesmo nome no próprio Librera.
- `GFile.java` utiliza pasta `Librera` no Drive com escopo `drive.file`,
  não `appDataFolder`. O escopo do FinTips não concede automaticamente acesso
  a arquivos criados por outro app. Conectar exige seleção/autorização real.

O Librera documenta [sincronização](https://librera.mobi/faq/setting-up-synchronization/)
via Drive e diretório local sincronizado por ferramentas como Syncthing. O
[escopo Drive por arquivo](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
é apropriado para arquivos escolhidos pelo usuário. Não foi acessada conta,
arquivo ou aparelho real do usuário. Versões antigas podem usar outro formato;
o adaptador atual recusa o que não sabe interpretar.

Exemplo **sintético** do formato, não arquivo pessoal:

```json
{"Livro de demonstração.epub": {"p": 0.25, "t": 1791979200000}}
```

## Projeção e persistência

Extrair somente nome base local, posição e timestamp. Descartar `pt`, caminhos
e campos extras. Rejeitar fração fora de 0–1, timestamp inválido, caminhos no
nome e entradas malformadas; não transformar 25 em 25% por adivinhação.
O importador tem limite de 2 MB e ignora posições com dia futuro.

100% = `10000` pontos-base (`progresso_bp`), ou seja, um ponto-base = 0,01 ponto
percentual. Livros, títulos, perfil, histórico e preferência de dias/prazo
ficam em `fintips.leitura.v1` no armazenamento do navegador. Esse armazenamento
**não é criptografado**, depende da origem e pode ser apagado com os dados do
navegador. O botão de cópia baixa JSON local com conteúdo pessoal; ainda não
há restauração na UI. O arquivo original do Librera não é persistido.

Um registro por dia e livro. Reimportar o mesmo arquivo não duplica dados;
timestamp mais recente ganha no mesmo dia. Correção manual prevalece sobre a
fonte naquele dia. Livro é identificado pelo perfil explícito e nome base;
importar com outro perfil cria outro namespace. Datas usam o dia local do
aparelho, enquanto diferenças entre dias usam calendário, sem efeito de DST.

## O que a previsão significa

A janela observada contém os últimos 28 dias. O ritmo usa o avanço entre a
primeira e a última posição, dividido pelos dias de calendário entre elas.
Dias sem atualização fazem parte do intervalo. A previsão é o teto de
`posição restante × dias observados / avanço observado`.

- Um único ponto: calibrando, sem previsão. Dois pontos: estimativa preliminar.
- Posição com mais de sete dias: atualizar antes de projetar.
- Sem avanço: sem previsão. Recuo: usar somente o trecho após o último recuo.
- Fim do livro: posição no fim, sem conclusão automática de tarefa.
- Prazo opcional: mostrar ritmo necessário e comparar com o observado.
  Prazo vencido pede revisão, sem meta retroativa.
- Dias por semana são escolha da pessoa. A meta por dia de leitura distribui
  o restante por uma aproximação do número de dias disponíveis; não é agenda
  de dias específicos. Sem prazo, distribui o ritmo observado pela frequência.

Não se estima tempo de leitura, compreensão, dias efetivamente lidos nem
motivação. A taxa pode variar conforme capítulo e edição; a UI permite ajustar
o prazo/frequência e exibe a base da estimativa.

## Contrato portável

`fintips/reading.py` define a referência; `vida/Leitura.kt` replica o pacing e
`web/src/reading-model.js` atende o protótipo local. `ouro/leitura.json` tem
casos de ritmo e importação, consumidos pelos testes Kotlin/JS. O parser
Librera Kotlin fica para o adaptador nativo; o ouro de importação já descreve
sua entrada/saída mínima. O painel não chama API para persistir leitura.
