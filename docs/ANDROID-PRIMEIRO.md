# Android primeiro

**Estado atual — preview 7:** ponte HTTPS/OAuth para ChatGPT e Claude e cliente
WSS Android implementados. O motor e os registros ficam no celular; cada
consulta usa o mesmo MCP local, com áreas aprovadas por conector e sem snapshot
remoto. **Hospedagem e autorização nas contas reais ainda precisam de ativação.**
Veja [implantação e vínculo](../integracoes/ponte/README.md). O APK não embute
um domínio externo. O fluxo abaixo das versões anteriores é histórico.


Em 14/10/2026, depois da entrega do APK v2, o usuário definiu: **“Foco no Android”**.
Android passa a orientar implementação, validação de UI e automação. Preservar
a linguagem Evangelion aprovada, alto contraste e movimento acessível.

## Estado real

Preview 6: teste MCP real no início e códigos de diagnóstico; o APK embarca servidor MCP Kotlin em loopback, iniciado e encerrado
pelo app/notificação, com atualização local das áreas autorizadas. Ponte até
ChatGPT/Claude continua pendente. [Contrato](SERVIDOR-MCP-LOCAL.md).
A descrição da alpha 4 a seguir é histórica.

Alpha 4: a UI WebView já chama o motor Kotlin para frentes, pacing e conferência
OFX, preservando os registros anteriores. Vínculo MCP é preparado no app e
confirmado no navegador; servidor HTTPS e uso nas contas ainda pendentes.
[Contrato e aceites](MOTOR-EMBARCADO-MCP.md). A nota sobre a v2 abaixo é histórica.

O APK v2 de avaliação abre a UI web empacotada em WebView offline. O módulo
Kotlin/Compose compila, mas oferece apenas a tela do dia no alvo release.
Cinco abas no APK não comprovam cinco telas Compose. Não substituir o APK
aprovado por telas nativas vazias nem apresentar migração como concluída.

## Ordem de implementação

| Ordem | Responsável solicitado | Entrega | Critério de pronto |
|---|---|---|---|
| 1 | Codex/UI | estrutura Compose com Hoje, Vida, Finanças, Planos e Contexto; tokens Evangelion e componentes de movimento | navegação por toque e Voltar, restauração da aba, insets e alvos de toque de pelo menos 48 dp; estados pendentes explícitos |
| 2 | Codex/UI + Claude/motor | tarefas, planos e leitura usando contratos locais | persistência após encerramento do processo, correção e desfazer; preservar registros anteriores com migração/revisão local antes de ativar a nova entrada |
| 3 | Claude/adaptadores + Codex/UI | seleção persistente do Librera, UsageStats e Health Connect | permissão explicada no momento de conectar, retomada/revogação/erro, frescor e cobertura; sem exigir registros diários manuais |
| 4 | Codex/UI | animações e refinamento no aparelho | teclado não cobre ações, saída de formulário e Voltar consistentes, movimento reduzido/escala de animação do Android respeitados; feedback tátil conforme preferência do sistema |

Codex mantém desenho, componentes Compose e experiência de interação.
Claude mantém motor, persistência e adaptadores; pedidos dependem de aceite
registrado. Antes de alterar o mesmo arquivo, registrar escopo no log.
Os IDs M-01/M-02/A-01/A-02/A-03 continuam em
[NECESSIDADES-UI.md](NECESSIDADES-UI.md); este documento muda a prioridade de
plataforma, não declara aceite nem implementação por outro agente.

## Contratos de plataforma

- PII e credenciais de fontes permanecem no aparelho. Não adicionar servidor
  para conectar a UI ao motor nem enviar títulos, rotinas ou listas de apps.
- Usar seletor de documentos e acesso persistente quando o provedor suportar;
  permissões revogadas devem permitir reconectar sem apagar histórico.
- Automação segue [AUTOMACAO-SEM-TOIL.md](AUTOMACAO-SEM-TOIL.md): executar
  conforme limites reais do Android, sem prometer coleta contínua infalível.
- Mudança de WebView para armazenamento nativo exige migração explícita e
  validada no client. Manter package e assinatura compatíveis quando possível
  não migra, por si só, o localStorage. Nunca pedir desinstalação como migração.
- Exportação e restauração continuam locais; nenhum log de depuração deve
  conter payload pessoal. ChatGPT exige a revisão de privacidade já definida.

## Validação e entregas

Cada APK informa quais telas são nativas, quais integrações funcionam e o que
foi executado em dispositivo/emulador. Build e QA do navegador não comprovam
fluidez ou lifecycle Android. Validar tela compacta, teclado aberto, botão
Voltar, rotação, recriação do processo, fonte ampliada e movimento reduzido.

Usar APKs incrementais para feedback no celular. Novas tarefas de web ou iOS
não são prioridade enquanto navegação, persistência e fontes Android não
estiverem sólidas. A web existente permanece referência visual e de regras.
