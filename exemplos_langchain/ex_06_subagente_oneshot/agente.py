"""6. Subagente de passagem única com saída estruturada — equivale a
`agents/operador_conta_single_turn`.

No ADK, `mode="single_turn"` faz o subagente rodar de forma autônoma numa
passagem só e fechar via `set_model_response`, validando contra `output_schema`.
Ele não conversa com o usuário e não consegue pausar para HITL.

No LangChain não existe `mode`. O que caracteriza esse comportamento é:

- o subagente é chamado como tool (ex_05) — logo é stateless e não fala com o
  usuário;
- `response_format=<modelo pydantic>` obriga a saída a ter forma. É o análogo do
  `output_schema`.

Com `response_format`, o resultado do invoke traz a chave `structured_response`
com a instância pydantic já validada — diferente de `messages[-1].text`, que é
texto livre. Devolver dado estruturado ao coordenador é mais robusto do que
devolver prosa para ele reinterpretar.
"""

from pydantic import BaseModel, Field

from langchain.agents import create_agent
from langchain.tools import tool

from exemplos_langchain.acme.config import MODELO_RAPIDO
from exemplos_langchain.acme.tools import listar_faturas_com_erro, obter_status_acme


class StatusPlataforma(BaseModel):
    """Formato exigido da resposta do especialista de status."""

    status: str = Field(description="operacional, manutencao ou intermitente")
    disponivel: bool = Field(description="True se a plataforma está operacional")
    resumo: str = Field(description="Uma frase explicando o status ao atendente.")


especialista_status = create_agent(
    model=MODELO_RAPIDO,
    system_prompt="""
        Você é o agente de status da Acme.
        Consulte a ferramenta e reporte o status da plataforma.
    """,
    tools=[obter_status_acme],
    response_format=StatusPlataforma,
)


@tool("consultar_status_plataforma")
def consultar_status_plataforma() -> dict:
    """Verifica se os serviços da Acme estão operacionais, em manutenção ou intermitentes.

    Use quando alguma consulta falhar com erro de sistema.
    """
    resultado = especialista_status.invoke(
        {"messages": [{"role": "user", "content": "Qual o status da plataforma agora?"}]}
    )
    # `structured_response` é a instância de StatusPlataforma já validada.
    status: StatusPlataforma = resultado["structured_response"]
    return status.model_dump()


agente = create_agent(
    model=MODELO_RAPIDO,
    system_prompt="""
        Você é o atendente de conta interativo da Acme.
        Quando uma consulta retornar erro de sistema, use
        `consultar_status_plataforma`. Se a plataforma não estiver disponível,
        avise que os serviços estão temporariamente fora e peça para tentar mais
        tarde. Se estiver disponível, informe que houve um erro de sistema.
        Nunca exponha detalhes técnicos. Seja cordial e direto.
    """,
    tools=[listar_faturas_com_erro, consultar_status_plataforma],
)
