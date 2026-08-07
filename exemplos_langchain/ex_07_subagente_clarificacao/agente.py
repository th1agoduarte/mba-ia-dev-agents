"""7. Subagente que pergunta ao usuário no meio da tarefa — equivale a
`agents/operador_conta_task`.

O `mode="task"` do ADK dá ao subagente algo que o `single_turn` não tem: se
faltar informação, ele faz uma pergunta ao usuário, o turno encerra, e a próxima
mensagem volta para o mesmo subagente, que então fecha com `finish_task`.

No LangChain o subagente continua sendo uma tool (ex_05), e a pergunta ao usuário
é feita com o primitivo `interrupt()`. Ele suspende o grafo INTEIRO — inclusive o
coordenador que estava esperando a tool — e o valor passado no `Command(resume=…)`
vira o retorno da chamada de `interrupt()`, ali mesmo, dentro do subagente.

Diferença importante em relação ao ADK: aqui não há "o próximo turno volta para o
mesmo agente". A execução é literalmente RETOMADA de onde parou, na mesma
invocação. Não é um turno novo.

Como no ex_03, isso exige `checkpointer` e `thread_id`. A diferença é quem pausa:
lá era o `HumanInTheLoopMiddleware` (política sobre tool calls), aqui é o próprio
código da tool pedindo um dado.
"""

from langchain.agents import create_agent
from langchain.tools import tool
from langgraph.types import interrupt

from exemplos_langchain.acme import dados
from exemplos_langchain.acme.config import MODELO_PADRAO, MODELO_RAPIDO, checkpointer_padrao

PLANOS = {"Basic": 29.99, "Pro": 49.99, "Enterprise": 149.99}


@tool
def perguntar_ao_cliente(pergunta: str) -> str:
    """Pergunta algo ao cliente quando faltar informação para concluir a tarefa.

    Args:
        pergunta: a pergunta a fazer, em português e direta.
    """
    # interrupt() devolve exatamente o valor enviado no Command(resume=...).
    resposta = interrupt({"pergunta": pergunta})
    return str(resposta)


@tool
def aplicar_troca_de_plano(cliente_id: str, novo_plano: str) -> dict:
    """Efetiva a troca de plano de um cliente.

    Args:
        cliente_id: identificador do cliente.
        novo_plano: um de Basic, Pro ou Enterprise.
    """
    if novo_plano not in PLANOS:
        return {"status": "recusada", "motivo": f"plano inválido: {novo_plano}"}
    assinatura = dados.buscar_assinatura(cliente_id)
    if assinatura is None:
        return {"status": "recusada", "motivo": "cliente não encontrado"}
    anterior = assinatura["plano"]
    assinatura["plano"] = novo_plano
    return {
        "status": "trocado",
        "de": anterior,
        "para": novo_plano,
        "mensalidade": PLANOS[novo_plano],
    }


especialista_planos = create_agent(
    model=MODELO_PADRAO,
    system_prompt=f"""
        Você é o consultor de planos da Acme.
        Planos disponíveis: {", ".join(PLANOS)}.

        Sua tarefa é trocar o plano do cliente.
        Se o cliente não disse PARA QUAL plano quer mudar, use
        `perguntar_ao_cliente` para descobrir antes de agir.
        Com a informação em mãos, chame `aplicar_troca_de_plano` e informe o
        resultado em uma frase.
    """,
    tools=[perguntar_ao_cliente, aplicar_troca_de_plano],
)


@tool("trocar_plano")
def trocar_plano(pedido: str) -> str:
    """Troca o plano da assinatura de um cliente. Use quando o cliente quiser mudar de plano.

    Args:
        pedido: o pedido do cliente, incluindo o id do cliente se conhecido.
    """
    resultado = especialista_planos.invoke(
        {"messages": [{"role": "user", "content": pedido}]}
    )
    return resultado["messages"][-1].text


agente = create_agent(
    model=MODELO_RAPIDO,
    system_prompt="""
        Você é o atendente de conta interativo da Acme.
        Se o cliente quiser mudar de plano, delegue para `trocar_plano`.
        Seja cordial e direto.
    """,
    tools=[trocar_plano],
    checkpointer=checkpointer_padrao(),
)
