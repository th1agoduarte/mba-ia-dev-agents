"""3. Tools + aprovação humana — equivale a `agents/operador_conta`.

Este é o exemplo onde ADK e LangChain mais divergem.

No ADK, a confirmação mora DENTRO da tool:

    def cancelar_assinatura(cliente_id, senha, tool_context):
        if tool_context.tool_confirmation is None:
            tool_context.request_confirmation(hint="...")   # a tool se pausa
            return {"status": "aguardando_confirmacao"}
        ...

No LangChain a tool não sabe que existe aprovação. Quem pausa é o
`HumanInTheLoopMiddleware`, que roda DEPOIS do modelo e ANTES da execução da
tool: ele inspeciona as tool calls propostas, e se alguma casar com a política de
`interrupt_on`, emite um `interrupt()` que suspende o grafo.

Três consequências práticas:

1. A pausa exige um `checkpointer` — é ele que persiste o estado do grafo para a
   execução poder ser retomada depois. Sem checkpointer, o interrupt estoura.
2. Toda invocação precisa de um `thread_id` no config, que identifica a conversa
   a pausar e retomar.
3. O modelo precisa de fato CHAMAR a tool. Se ele "pedir confirmação" em texto,
   não há tool call para interceptar e o middleware nunca dispara — por isso a
   instrução manda executar direto.
"""

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware

from exemplos_langchain.acme.config import MODELO_RAPIDO, checkpointer_padrao
from exemplos_langchain.acme.tools import cancelar_assinatura, consultar_assinatura, listar_faturas

INSTRUCAO = """
    Você é o atendente de conta interativo da Acme.
    Você é responsável por:
     - Informar ao cliente sobre sua assinatura: o plano, status e renovação.
     - Tirar dúvidas sobre as faturas do cliente.
     - Cancelar a assinatura do cliente, se solicitado.
    O usuário precisa fornecer o ID do cliente para que você possa buscar as
    informações corretas. Para cancelar, ele também precisa informar a senha.

    Execute o que o cliente pedir chamando as ferramentas diretamente.
    NÃO peça confirmação em texto: o cancelamento passa por uma aprovação
    tratada fora da conversa.
    Seja cordial e direto.
"""

agente = create_agent(
    model=MODELO_RAPIDO,
    system_prompt=INSTRUCAO,
    tools=[listar_faturas, consultar_assinatura, cancelar_assinatura],
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                # True = pausa e aceita qualquer decisão (approve/edit/reject/respond).
                # Um dict permite restringir: {"allowed_decisions": ["approve", "reject"]}.
                "cancelar_assinatura": True,
                # False = ação segura, executa sem perguntar. Poderia ser omitida:
                # o que não está no mapa não pausa. Deixamos explícito por didática.
                "listar_faturas": False,
                "consultar_assinatura": False,
            },
            description_prefix="Ação sensível aguardando aprovação",
        )
    ],
    # Em produção troque por um checkpointer persistente (ver ex_08_sessao).
    checkpointer=checkpointer_padrao(),
)
