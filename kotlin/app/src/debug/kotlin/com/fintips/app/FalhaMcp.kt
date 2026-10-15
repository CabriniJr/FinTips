package com.fintips.app

/** Mensagens fixas: nunca serializar exception.message, contexto ou token. */
internal enum class CodigoMcp(val mensagem: String) {
    ANDROID("MCP-01: O Android não permitiu iniciar o serviço. Mantenha o FinTips aberto e tente novamente."),
    CONTEXTO("MCP-02: O contexto não pôde ser preparado. Revise as áreas selecionadas."),
    SOCKET("MCP-03: Não foi possível abrir o servidor local neste aparelho."),
    TESTE("MCP-04: O servidor abriu, mas não respondeu corretamente ao teste MCP local. Encerre e tente novamente."),
    TEMPO("MCP-05: O Android não confirmou o início a tempo. Confira o estado antes de tentar novamente."),
    INDISPONIVEL("MCP-06: Não há sessão disponível para testar. Inicie ou revise o servidor primeiro."),
    DESCONHECIDO("MCP-00: Não foi possível concluir esta ação no servidor local.");

    companion object {
        fun de(valor: String?): CodigoMcp = entries.firstOrNull { it.name == valor } ?: DESCONHECIDO
    }
}
internal class FalhaMcp(val codigo: CodigoMcp) : IllegalStateException(codigo.mensagem)
