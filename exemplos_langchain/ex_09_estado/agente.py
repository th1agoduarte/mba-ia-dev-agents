"""9. Contexto, estado e prompt dinâmico — equivale a
`agents/operador_conta_session_state`.

O exemplo ADK fazia quatro coisas que aqui se separam em dois conceitos
DIFERENTES, e essa separação é a lição principal.

No ADK tudo vive em `session.state`: o `cliente_id` semeado na criação da sessão,
o resultado da pesquisa gravado por uma tool, o `output_key` do agente. Tudo lido
com `tool_context.state.get(...)` e injetado no prompt com `{chave?}`.

O LangChain divide isso em dois:

- **`context`** (`context_schema`) — dado ESTÁTICO da invocação: quem é o usuário,
  conexão de banco, feature flags. Não é persistido no checkpoint, você o passa a
  cada `invoke(..., context=...)`. É injeção de dependência.
- **`state`** (`state_schema`) — dado que a execução PRODUZ e que precisa
  sobreviver entre turnos: o resultado da pesquisa. Vive no checkpoint.

Regra prática: `cliente_id` é contexto (veio de fora, o agente não descobriu);
o resultado da pesquisa é estado (o agente produziu).

E o template `{pesquisa_satisfacao_resultado?}` da instrução não existe: o
`system_prompt` é string fixa. Prompt que varia com o estado se faz com o
middleware `@dynamic_prompt`, que roda antes de cada chamada ao modelo.
"""

from dataclasses import dataclass
from typing import Any

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt
from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command
from typing_extensions import NotRequired

from exemplos_langchain.acme import dados
from exemplos_langchain.acme.config import MODELO_RAPIDO, checkpointer_padrao


@dataclass
class Contexto:
    """Dado estático da invocação. Equivale ao state semeado no create_session."""

    cliente_id: str


class EstadoAtendimento(AgentState):
    """Estado que a conversa produz e que sobrevive entre turnos."""

    pesquisa_satisfacao: NotRequired[dict[str, Any]]


# --- tools que leem o cliente do CONTEXTO, não de um argumento ----------------
# Compare com acme/tools.py: lá o LLM precisava passar `cliente_id`, e podia
# errar ou inventar. Aqui o dado vem do runtime e o modelo nem o enxerga.


@tool
def listar_minhas_faturas(runtime: ToolRuntime[Contexto]) -> dict:
    """Lista as faturas do cliente que está sendo atendido."""
    return {"faturas": dados.buscar_faturas(runtime.context.cliente_id)}


@tool
def consultar_minha_assinatura(runtime: ToolRuntime[Contexto]) -> dict:
    """Consulta plano, status e renovação da assinatura do cliente atendido."""
    return dados.buscar_assinatura(runtime.context.cliente_id) or {
        "erro": "cliente não encontrado"
    }


@tool
def cancelar_minha_assinatura(senha: str, runtime: ToolRuntime[Contexto]) -> dict:
    """Cancela a assinatura do cliente atendido.

    Args:
        senha: senha fornecida pelo cliente para autenticação.
    """
    if senha != dados.SENHA_VALIDA:
        return {"status": "nao_cancelada", "motivo": "senha incorreta"}
    if not dados.cancelar(runtime.context.cliente_id):
        return {"status": "nao_cancelada", "motivo": "cliente não encontrado"}
    return {"status": "cancelada"}


@tool
def ja_respondeu_pesquisa(runtime: ToolRuntime[Contexto]) -> dict:
    """Verifica se o cliente já respondeu à pesquisa de satisfação nos últimos 3 meses."""
    respondeu = runtime.context.cliente_id in dados.RESPONDERAM_PESQUISA
    return {"ja_respondeu": respondeu}


@tool
def registrar_pesquisa(
    feedback: str, sentimento: str, runtime: ToolRuntime[Contexto]
) -> Command:
    """Registra a resposta do cliente à pesquisa de satisfação.

    Args:
        feedback: o que o cliente achou dos serviços da Acme.
        sentimento: positivo, neutro ou negativo.
    """
    # Uma tool escreve no estado devolvendo um Command. É o equivalente do
    # `tool_context.state["x"] = ...` do ADK — só que explícito e auditável.
    return Command(
        update={
            "pesquisa_satisfacao": {"feedback": feedback, "sentimento": sentimento},
            "messages": [
                ToolMessage(
                    content="Pesquisa registrada.",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )


# --- prompt que muda conforme o estado ---------------------------------------

INSTRUCAO_BASE = """
    Você é o atendente de conta interativo da Acme.
    Informe o cliente sobre sua assinatura, tire dúvidas sobre faturas e cancele
    a assinatura quando solicitado (peça a senha).

    Antes de tratar qualquer outro assunto, verifique com `ja_respondeu_pesquisa`
    se o cliente já respondeu à pesquisa de satisfação. Se não respondeu,
    pergunte como tem sido a experiência dele com a Acme e registre a resposta
    com `registrar_pesquisa` antes de seguir.

    Execute as ações chamando as ferramentas diretamente.
    Seja cordial e direto.
"""


@dynamic_prompt
def prompt_com_pesquisa(request: ModelRequest[Contexto]) -> str:
    """Injeta o resultado da pesquisa no prompt, quando existir.

    É o equivalente ao `{pesquisa_satisfacao_resultado?}` da instrução ADK — com
    a diferença de que aqui você controla o texto e o caso "ainda não existe".
    """
    pesquisa = request.state.get("pesquisa_satisfacao")
    if not pesquisa:
        return INSTRUCAO_BASE
    extra = f"""
    O cliente já respondeu à pesquisa de satisfação:
      - feedback: {pesquisa["feedback"]}
      - sentimento: {pesquisa["sentimento"]}
    Se o sentimento for negativo e ele pedir cancelamento, ofereça antes um
    desconto de 20% na próxima renovação.
    """
    return INSTRUCAO_BASE + extra


agente = create_agent(
    model=MODELO_RAPIDO,
    tools=[
        listar_minhas_faturas,
        consultar_minha_assinatura,
        cancelar_minha_assinatura,
        ja_respondeu_pesquisa,
        registrar_pesquisa,
    ],
    # Sem `system_prompt=`: quem entrega o prompt é o middleware.
    middleware=[prompt_com_pesquisa],
    context_schema=Contexto,
    state_schema=EstadoAtendimento,
    checkpointer=checkpointer_padrao(),
)
