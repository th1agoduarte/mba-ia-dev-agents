"""10. Middleware de infraestrutura — equivale a `agents/ticket_receptionist`.

O exemplo ADK junta quatro coisas. Três já vimos; a quarta é o assunto aqui.

| ADK (`ticket_receptionist`) | Aqui |
|---|---|
| `sub_agents=[ticket_classifier]` (`single_turn` + `output_schema` + `output_key`) | subagente-como-tool com `response_format` (ex_06) |
| `tool_context.state["temp:ticket_created"]` como trava | chave do `state_schema` + `Command` (ex_09) |
| `on_tool_error_callback=_handle_tool_error` | `ToolErrorMiddleware` |
| `plugins=[ModelRetryPlugin()]` (96 linhas escritas à mão) | `ModelRetryMiddleware` |

A lição das duas últimas linhas: no ADK, plugin e callback são pontos de extensão
VAZIOS — o framework te dá o gancho, você escreve a política. O `ModelRetryPlugin`
do exemplo original guarda o request no `before_model`, inspeciona a resposta no
`after_model`, detecta resposta vazia ou malformada, remonta o request com um
"nudge", tenta 5 vezes e degrada com elegância. São 96 linhas.

No LangChain isso é uma linha, porque `ModelRetryMiddleware` já vem pronto — com
backoff exponencial e jitter, que a versão artesanal não tinha.

Isso não quer dizer que o LangChain seja "melhor": quer dizer que a fronteira
entre o que é do framework e o que é seu está em lugares diferentes. Middleware
customizado continua existindo (`@wrap_model_call`, ver ex_04) para o que é
política do seu domínio.
"""

from __future__ import annotations

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    ModelRetryMiddleware,
    ToolCallRequest,
    ToolErrorMiddleware,
)
from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing_extensions import NotRequired

from exemplos_langchain.acme import tickets
from exemplos_langchain.acme.config import MODELO_PADRAO, MODELO_RAPIDO, checkpointer_padrao
from exemplos_langchain.acme.tickets import CategoriaTicket


class JaRegistradoError(Exception):
    """Erro de negócio: tentativa de registrar o mesmo ticket duas vezes."""


class SemClassificacaoError(Exception):
    """Erro de negócio: registro pedido antes da classificação."""


class Classificacao(BaseModel):
    """Formato exigido da saída do classificador."""

    categoria: CategoriaTicket = Field(description="Categoria do ticket.")
    confianca: float = Field(ge=0.0, le=1.0, description="Certeza de 0.0 a 1.0.")
    justificativa: str = Field(description="Uma frase curta, em português.")
    precisa_refund: bool = Field(
        default=False,
        description="True se a mensagem cita estorno, refund ou ajuste de valor.",
    )


class EstadoRecepcao(AgentState):
    """A classificação e a trava de registro vivem no estado da conversa."""

    classificacao: NotRequired[dict]
    ticket_registrado: NotRequired[str]


_INSTRUCAO_CLASSIFICADOR = """
Você é o Classificador de tickets da central de atendimento da Acme Cloud.
Analise a mensagem e classifique-a, com uma justificativa curta.

A Acme Cloud é uma plataforma SaaS B2B de gestão de equipes e boards, com API
cobrada por excedente, planos Free/Pro/Enterprise e faturas mensais.

Categorias REAIS (prefira sempre uma delas):
- `billing` — fatura, cobrança, refund
- `bug` — algo quebrado na plataforma
- `feature_request` — pedido de recurso ou integração
- `onboarding` — dúvida de uso ou configuração

Categorias de FALLBACK (último recurso):
- `composite` — misturam-se 2 ou mais categorias REAIS
- `undefined` — é suporte plausível, mas nenhuma categoria real se aplica
- `out_of_scope` — não é pedido de suporte (saudação, spam, off-topic)

Decida NESTA ordem:
1. `out_of_scope` apenas se a mensagem INTEIRA não for suporte.
2. `composite` se 2 ou mais categorias reais se aplicarem.
3. a categoria REAL única, mesmo cercada de ruído ao lado do pedido.
4. `undefined` se nenhuma real se aplica com clareza.

Se a mensagem cita estorno, refund ou ajuste de valor, marque
`precisa_refund=True`. NÃO estime valores.
Se a mensagem for ambígua, use `confianca` abaixo de 0.6.
"""

classificador = create_agent(
    model=MODELO_PADRAO,
    system_prompt=_INSTRUCAO_CLASSIFICADOR,
    response_format=Classificacao,
)


@tool
def classificar_ticket(mensagem: str, runtime: ToolRuntime) -> Command:
    """Classifica a mensagem de um ticket. Chame antes de registrar.

    Args:
        mensagem: o texto do ticket, exatamente como o cliente escreveu.
    """
    resultado = classificador.invoke(
        {"messages": [{"role": "user", "content": mensagem}]}
    )
    classificacao: Classificacao = resultado["structured_response"]
    # O resultado vai para o estado (não só para a conversa) porque a tool de
    # registro vai lê-lo de lá — é o papel do `output_key` do ADK.
    return Command(
        update={
            "classificacao": {**classificacao.model_dump(mode="json"), "mensagem": mensagem},
            "messages": [
                ToolMessage(
                    content=(
                        f"Classificado como {classificacao.categoria.value} "
                        f"(confiança {classificacao.confianca:.2f}): "
                        f"{classificacao.justificativa}"
                    ),
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )


@tool
def registrar_ticket(cliente_id: str, runtime: ToolRuntime) -> Command:
    """Registra o ticket já classificado na central de atendimento.

    Args:
        cliente_id: identificador do cliente que abriu o ticket.
    """
    if runtime.state.get("ticket_registrado"):
        # Trava de idempotência: equivale ao guard `temp:ticket_created` do ADK.
        # Sem ela, o modelo pode chamar a tool duas vezes e abrir dois tickets.
        raise JaRegistradoError(
            f"O ticket {runtime.state['ticket_registrado']} já foi registrado "
            "nesta conversa. Não registre de novo."
        )

    classificacao = runtime.state.get("classificacao")
    if not classificacao:
        raise SemClassificacaoError(
            "O ticket ainda não foi classificado. Chame `classificar_ticket` antes."
        )

    ticket = tickets.criar_ticket(
        cliente_id=cliente_id,
        mensagem=classificacao["mensagem"],
        classificacao=tickets.Classificacao(
            categoria=CategoriaTicket(classificacao["categoria"]),
            confianca=classificacao["confianca"],
            justificativa=classificacao["justificativa"],
            precisa_refund=classificacao["precisa_refund"],
        ),
    )
    return Command(
        update={
            "ticket_registrado": ticket.id,
            "messages": [
                ToolMessage(
                    content=f"Ticket {ticket.id} registrado com sucesso.",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )


@tool
def consultar_ticket(ticket_id: str) -> dict:
    """Consulta o status e os dados de um ticket já registrado.

    Args:
        ticket_id: o identificador do ticket, por exemplo "TICKET-0001".
    """
    ticket = tickets.buscar_ticket(ticket_id)
    if ticket is None:
        return {"erro": f"ticket {ticket_id} não encontrado"}
    return tickets.como_dict(ticket)


@tool
def listar_tickets(cliente_id: str) -> dict:
    """Lista os tickets registrados por um cliente.

    Args:
        cliente_id: identificador do cliente.
    """
    return {
        "tickets": [tickets.como_dict(t) for t in tickets.listar_tickets(cliente_id)]
    }


def _tratar_erro_de_tool(erro: Exception, chamada: ToolCallRequest) -> str | None:
    """Converte exceção em `ToolMessage` de erro, para o modelo se recuperar.

    Equivale ao `on_tool_error_callback` do ADK, com uma diferença importante de
    projeto: aqui o tratamento é OPT-IN. Devolver `None` deixa a exceção subir e
    derrubar a execução. Ou seja, só o que você reconhece vira mensagem para o
    modelo — um `KeyError` acidental não vaza para o cliente disfarçado de texto.

    O handler recebe DOIS argumentos: a exceção e a chamada que falhou
    (`chamada.tool_call` traz nome, args e id) — dá para tratar por tool.
    """
    if isinstance(erro, (JaRegistradoError, SemClassificacaoError)):
        return str(erro)
    return None


agente = create_agent(
    model=MODELO_RAPIDO,
    system_prompt="""
        Você é o Recepcionista de tickets da central de atendimento da Acme Cloud.

        Se o cliente pedir para abrir um ticket: chame `classificar_ticket` com a
        mensagem dele e, em seguida, `registrar_ticket`. Informe o número do
        ticket ao final.
        Se perguntar sobre um ticket existente, use `consultar_ticket`.
        Se pedir a lista dos tickets dele, use `listar_tickets`.

        Registre cada ticket UMA única vez.
        Seja cordial e direto.
    """,
    tools=[classificar_ticket, registrar_ticket, consultar_ticket, listar_tickets],
    state_schema=EstadoRecepcao,
    middleware=[
        # Erros de negócio viram mensagem para o modelo; o resto sobe.
        ToolErrorMiddleware(on_error=_tratar_erro_de_tool),
        # As 96 linhas do ModelRetryPlugin do ADK, com backoff e jitter de brinde.
        ModelRetryMiddleware(max_retries=3, initial_delay=0.5),
    ],
    checkpointer=checkpointer_padrao(),
)
