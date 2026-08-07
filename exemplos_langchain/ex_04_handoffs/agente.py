"""4. Handoffs — equivale a `agents/operador_conta_subagent`.

No ADK, `sub_agents=[...]` dá ao coordenador a tool implícita `transfer_to_agent`:
o especialista assume a conversa e fala direto com o usuário até transferir de
volta. `disallow_transfer_to_peers` / `disallow_transfer_to_parent` restringem
para onde ele pode ir.

O LangChain não tem `sub_agents`. O padrão equivalente chama-se **handoffs** e é
construído explicitamente:

- uma chave de estado (`especialista_ativo`) diz quem está com a conversa;
- tools de transferência devolvem um `Command` que atualiza essa chave;
- um middleware `wrap_model_call` lê a chave antes de cada chamada ao modelo e
  troca `system_prompt` e `tools`.

Ou seja: em vez de vários objetos Agent, é UM agente que muda de figurino. A doc
recomenda essa forma para a maioria dos casos; a alternativa (cada especialista
como um nó de grafo separado, transferindo com `Command(graph=Command.PARENT)`)
só compensa quando o especialista é um grafo complexo por dentro.

O estado sobrevive entre turnos por causa do `checkpointer` — sem ele, o
`especialista_ativo` voltaria ao default a cada mensagem.

CUIDADO — o roteamento é probabilístico. Quem decide transferir é o modelo, não
o código. Na primeira versão do prompt do coordenador, 1 execução em 4 parava
nele em vez de seguir para o especialista seguinte: ele respondia ao cliente em
vez de transferir. O conserto foi no PROMPT ("sua única ação é encaminhar";
"se acabou de receber a conversa de volta, transfira imediatamente"), não no
grafo. Se o seu handoff estiver instável, o prompt do roteador é a alavanca.
"""

from typing import Callable

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

from exemplos_langchain.acme.config import MODELO_PADRAO, MODELO_RAPIDO, checkpointer_padrao
from exemplos_langchain.acme.tools import cancelar_assinatura, consultar_assinatura, listar_faturas

# `create_agent(model=...)` aceita string e resolve com init_chat_model por baixo,
# mas `request.override(model=...)` exige o OBJETO já construído — ele chama
# .bind_tools() direto. Por isso instanciamos aqui.
_RAPIDO = init_chat_model(MODELO_RAPIDO, temperature=0)
_PADRAO = init_chat_model(MODELO_PADRAO, temperature=0)


class EstadoAtendimento(AgentState):
    """Estado do grafo, estendido com quem está conduzindo a conversa."""

    especialista_ativo: str


def _transferir(destino: str, runtime: ToolRuntime) -> Command:
    """Monta o Command de transferência.

    O `ToolMessage` NÃO é decoração: o modelo emitiu uma tool call e espera a
    resposta correspondente. Sem ela, o histórico fica malformado e o provedor
    recusa a próxima chamada.
    """
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"Conversa transferida para: {destino}",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "especialista_ativo": destino,
        }
    )


@tool
def transferir_para_faturas(runtime: ToolRuntime) -> Command:
    """Transfere a conversa ao consultor de faturas, especialista em listar faturas."""
    return _transferir("faturas", runtime)


@tool
def transferir_para_assinaturas(runtime: ToolRuntime) -> Command:
    """Transfere a conversa ao consultor de assinaturas, que informa plano, status e renovação, e cancela assinaturas."""
    return _transferir("assinaturas", runtime)


@tool
def devolver_ao_coordenador(runtime: ToolRuntime) -> Command:
    """Devolve a conversa ao atendente principal quando o assunto sai da sua especialidade."""
    return _transferir("coordenador", runtime)


# Cada "especialista" é uma configuração: prompt + conjunto de tools + modelo.
# É o análogo direto de um sub_agent do ADK.
ESPECIALISTAS: dict[str, dict] = {
    "coordenador": {
        "modelo": _RAPIDO,
        "prompt": """
            Você é o atendente de conta da Acme e faz a triagem.
            Sua ÚNICA ação é encaminhar o cliente ao especialista adequado:
            faturas ou assinaturas.
            Não responda sobre faturas ou assinaturas você mesmo, e não peça
            dados ao cliente — o especialista faz isso.
            Se você acabou de receber a conversa de volta de um especialista e
            ainda há um pedido pendente, transfira imediatamente para o
            especialista certo em vez de responder.
        """,
        "tools": [transferir_para_faturas, transferir_para_assinaturas],
    },
    "faturas": {
        "modelo": _PADRAO,
        "prompt": """
            Você é um consultor de faturas da Acme.
            Você é responsável por listar as faturas de um cliente específico.
            Peça o ID do cliente se ainda não souber.
            Se o assunto mudar para assinaturas, chame `devolver_ao_coordenador`.
        """,
        "tools": [listar_faturas, devolver_ao_coordenador],
    },
    "assinaturas": {
        "modelo": _PADRAO,
        "prompt": """
            Você é um consultor de assinaturas da Acme.
            Você informa plano, status e renovação, e cancela assinaturas quando
            o cliente pedir (peça o ID do cliente e a senha).
            Se o assunto mudar para faturas, chame `devolver_ao_coordenador`.
        """,
        "tools": [consultar_assinatura, cancelar_assinatura, devolver_ao_coordenador],
    },
}


@wrap_model_call
def aplicar_especialista(
    request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    """Veste o figurino do especialista ativo antes de cada chamada ao modelo."""
    ativo = request.state.get("especialista_ativo") or "coordenador"
    config = ESPECIALISTAS[ativo]
    return handler(
        request.override(
            model=config["modelo"],
            # `override(system_prompt=...)` ainda funciona, mas está depreciado:
            # o campo do request é `system_message`, um SystemMessage.
            system_message=SystemMessage(content=config["prompt"]),
            tools=config["tools"],
        )
    )


agente = create_agent(
    model=MODELO_RAPIDO,  # default; o middleware sobrescreve a cada turno
    tools=[
        # A união de todas as tools precisa ser declarada aqui: o middleware só
        # escolhe um SUBCONJUNTO por turno, não registra tools novas.
        listar_faturas,
        consultar_assinatura,
        cancelar_assinatura,
        transferir_para_faturas,
        transferir_para_assinaturas,
        devolver_ao_coordenador,
    ],
    state_schema=EstadoAtendimento,
    middleware=[aplicar_especialista],
    checkpointer=checkpointer_padrao(),
)
