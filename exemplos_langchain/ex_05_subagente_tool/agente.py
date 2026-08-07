"""5. Subagente como tool — equivale a `agents/operador_conta_agenttool`.

No ADK existem duas formas de compor agentes, e a escolha entre elas é a lição:

- `sub_agents=[x]`  -> transfer: x ASSUME a conversa (ver ex_04_handoffs).
- `AgentTool(x)`    -> x é chamado como ferramenta, DEVOLVE UM VALOR e o
                       coordenador segue no controle.

O LangChain só tem a segunda de forma nativa, e ela nem precisa de API especial:
um agente é invocável, então **embrulhar `agente.invoke(...)` numa `@tool` já é o
padrão de subagentes**. Não existe classe `AgentTool`.

Consequências de "subagente é uma tool":

- O subagente é STATELESS: cada chamada começa com contexto limpo. Quem guarda a
  conversa é o coordenador. Isso é isolamento de contexto de graça.
- O que o coordenador recebe é o que a função retornar — normalmente a última
  mensagem. Se o subagente "trabalhou mas não contou", o coordenador não vê nada.
- Nome e docstring da tool são o único sinal de roteamento. Equivalem à
  `description` do sub_agent no ADK.
"""

from langchain.agents import create_agent
from langchain.tools import tool

from exemplos_langchain.acme.config import MODELO_RAPIDO
from exemplos_langchain.acme.tools import listar_faturas_com_erro, obter_status_acme

# O especialista: um agente comum, sem nada de especial.
especialista_status = create_agent(
    model=MODELO_RAPIDO,
    system_prompt="""
        Você é o agente de status da Acme.
        Consulte a ferramenta e responda em uma frase se a plataforma está
        operacional, em manutenção ou intermitente.
    """,
    tools=[obter_status_acme],
)


@tool("consultar_status_plataforma")
def consultar_status_plataforma(pergunta: str) -> str:
    """Verifica se os serviços da Acme estão operacionais, em manutenção ou intermitentes.

    Use quando alguma consulta falhar com erro de sistema, para descobrir se a
    causa é indisponibilidade da plataforma.

    Args:
        pergunta: o que você quer saber sobre o status da plataforma.
    """
    resultado = especialista_status.invoke(
        {"messages": [{"role": "user", "content": pergunta}]}
    )
    # Só a última mensagem volta ao coordenador. O raciocínio e as tool calls do
    # subagente ficam no contexto dele e não poluem a conversa principal.
    return resultado["messages"][-1].text


agente = create_agent(
    model=MODELO_RAPIDO,
    system_prompt="""
        Você é o atendente de conta interativo da Acme.

        Quando uma consulta retornar um erro de sistema, use
        `consultar_status_plataforma` para descobrir se os serviços estão no ar.
        Se estiverem em manutenção ou intermitentes, diga ao cliente que os
        serviços estão temporariamente indisponíveis e que ele tente mais tarde.
        Se estiverem operacionais, diga que houve um erro de sistema e que ele
        tente novamente mais tarde.

        Erros de sistema são falhas de comunicação com sistemas externos (banco
        de dados, APIs de terceiros) e podem ser temporários. Nunca exponha
        detalhes técnicos do erro ao cliente.
        Seja cordial e direto.
    """,
    tools=[listar_faturas_com_erro, consultar_status_plataforma],
)
