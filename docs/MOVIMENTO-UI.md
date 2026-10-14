# Movimento da UI

Pedido do usuário após avaliar o primeiro APK: manter a linguagem aprovada,
adicionar transições, hover e resposta de clique/toque, com alto contraste.

| Interação | Resposta |
|---|---|
| Trocar destino | saída de 130 ms, entrada de 280 ms; indicador responde imediatamente |
| Toques rápidos em destinos | último destino prevalece; sem fila de páginas antigas |
| Botão | pressão curta, onda local no ponto de toque; teclado também recebe resposta |
| Hover com mouse | elevação curta, borda e seta; não é requisito para usar no celular |
| Áreas e lista | entrada dos módulos em sequência curta, sem mudar texto ou valor |
| Cumprir tarefa | encaixe do check, leitura numérica imediata e transição da barra real |
| Leitura | desenho da linha observada; comprimento/posição vêm do histórico |
| Formulário | entrada de 240 ms; saída de 160 ms ao salvar, fechar ou cancelar |
| Mensagem | entrada/saída; ações repetidas reiniciam a mensagem e sua animação |

`web/src/motion.js` controla navegação e ondas de toque sem dependência nova,
analytics ou cópia do DOM pessoal. `motion.css` é a camada final de movimento.
`Sheet` conserva o foco/modal até o fim da saída e evita ações durante fechamento.
Navegação cancela o destino pendente ao receber novo toque.

## Acessibilidade e contraste

Respeitar `prefers-reduced-motion`: navegação/fechamento imediatos, sem ondas,
stagger, deslocamento de hover ou transição de indicador. Alterar a preferência
durante uma transição encerra a espera e cancela ondas em execução. Foco,
estado selecionado, cor e rótulo continuam informativos sem movimento.

Texto e números entram com cor/opacidade estáveis; o movimento de entrada é
geométrico. A paleta mantém contraste elevado. Não animar contagem inventada,
piscar alerta, simular coleta ou manter animações ociosas consumindo bateria.
A barra pode transicionar entre valores reais; o número já mostra o valor atual.

## Verificação

QA no navegador: pressão/onda, tarefa e indicador, abrir/salvar/fechar/Escape,
navegação rápida, aba ativa visível, teclado, persistência, hover desktop e
movimento reduzido, inclusive alterado durante transição. Nenhuma escrita de
rede nessas operações. Fluxos de leitura e 25 combinações de rota/largura
permanecem na verificação do protótipo.

O APK de avaliação usa os mesmos assets. A fluidez real, teclado e feedback
no WebView do celular precisam da avaliação do usuário; o build não comprova
taxa de quadros em dispositivo.
