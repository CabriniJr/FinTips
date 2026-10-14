# Linguagem visual do FinTips

Direção escolhida pelo usuário em 14/10/2026: interfaces de Evangelion, nas
referências [painéis e instrumentos](https://imgur.com/a/evangelion-user-interfaces-images-mvW7g)
e [mapa animado](https://imgur.com/a/uDeBs). Foram examinados exemplos de réguas,
mapas de contorno, marcações de posição, diagramas e vídeo. Os arquivos dessas
referências não fazem parte do produto.

## Tradução para o app

Após a primeira versão, o usuário pediu referência mais direta ao anime.
A direção final usa preto, vermelho de título e âmbar intenso, com painéis
retangulares, áreas chanfradas, réguas e tipografia condensada pesada,
valores monoespaçados e barras segmentadas. A hierarquia vem de tamanho,
espaçamento e borda, antes de cor. Títulos podem usar caixa alta; conteúdo
pessoal e texto corrido mantêm a escrita normal.

| Papel | Token | Valor |
|---|---|---|
| Fundo | `--paper` | `#080808` |
| Painel | `--card` | `#0d0c0b` |
| Texto principal | `--ink` | `#f1efe6` |
| Texto secundário | `--ink-3` | `#bdad99` |
| Ação e seção ativa | `--accent` | `#ffa342` |
| Identidade e títulos | `--signal` | `#ff4b35` |
| Progresso registrado | `--s3` | `#a4ec8c` |
| Atenção | `--warn` | `#e9c56e` |
| Erro real | `--crit` | `#ff9c8c` |

As seis áreas têm cores e ícones próprios, mas sempre exibem seus nomes. Vermelho estrutural identifica a tela; erros têm texto e estado explícitos. Cor
sozinha não comunica conclusão, erro ou origem de um registro. As linhas do
gráfico de leitura conectam posições observadas; não representam sessões.
As barras do dia mostram tarefas registradas, não o score do motor de vida.

`web/src/instrument.css` é a camada visual final. `mobile.css` organiza o
layout e `styles.css` mantém os componentes financeiros. Barlow Condensed
SemiBold e Black são distribuídas localmente sob SIL OFL; corpo usa fonte do sistema.
Não há requisição a serviços de fontes nem imagens remotas na interface.

## Requisitos ao portar para Compose

- Cinco destinos persistentes: Hoje, Vida, Finanças, Planos, Contexto.
- Seis áreas com nomes legíveis; leitura dentro de Estudos.
- Alvos de toque de pelo menos 44 px no protótipo; 48 dp no Android.
- Conteúdo funciona a 320 px, com fonte de formulário de 16 px, área segura
  inferior e rolagem horizontal apenas nas abas e tabelas.
- Foco visível, diálogos com título e fechamento, estados vazios que explicam
  o próximo passo. Contraste dos textos principais e secundários verificado
  sobre os fundos utilizados; SVG deve fornecer alternativa textual.
- Sem luz piscando, estática sobre texto, som, radar aleatório, alerta falso
  ou contador inventado. Movimento reduzido respeitado. Não copiar logos.
- O tema escuro é a direção atual, inclusive se o sistema estiver claro.
  Um tema claro futuro precisa de paleta e validação próprias.

O protótipo web pode ser revisado hoje; a aplicação visual no Android depende
da tela Compose. Não tratar a compilação Vite como entrega de APK.
