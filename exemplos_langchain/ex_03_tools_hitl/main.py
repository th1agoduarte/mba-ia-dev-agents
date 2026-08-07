"""Demonstra o ciclo pausar -> decidir -> retomar.

    uv run python -m exemplos_langchain.ex_03_tools_hitl.main
    uv run python -m exemplos_langchain.ex_03_tools_hitl.main recusar
"""

import sys

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from exemplos_langchain.acme import dados
from exemplos_langchain.ex_03_tools_hitl.agente import agente


def responder(resultado) -> str:
    """`version="v2"` faz o invoke devolver um GraphOutput (.value / .interrupts)."""
    return resultado.value["messages"][-1].text


def main() -> None:
    aprovar = "recusar" not in sys.argv
    # `RunnableConfig` é um TypedDict: sem a anotação o dict vira um
    # `dict[str, dict[str, str]]` qualquer e o type checker recusa o `invoke`.
    config: RunnableConfig = {"configurable": {"thread_id": "conversa-1"}}

    # Lê o dado cru do "sistema externo" — é ele que não pode mudar antes da
    # aprovação humana.
    print("status inicial:", dados.ASSINATURAS["cliente_123"]["status"])

    resultado = agente.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Sou o cliente_123, minha senha é senha_secreta. "
                        "Cancele minha assinatura."
                    ),
                }
            ]
        },
        config=config,
        version="v2",
    )

    if not resultado.interrupts:
        # O modelo não chamou a tool sensível — nada a aprovar.
        print("não pausou:", responder(resultado))
        return

    # Atenção: a chave é "args". A página human-in-the-loop da doc mostra
    # "arguments" no exemplo de saída, mas o TypedDict ActionRequest no fonte
    # (langchain/agents/middleware/human_in_the_loop.py) define `args`.
    pedido = resultado.interrupts[0].value["action_requests"][0]
    print(f"\npausou para aprovação -> {pedido['name']}({pedido['args']})")
    print("status durante a pausa:", dados.ASSINATURAS["cliente_123"]["status"])

    decisao = (
        {"type": "approve"}
        if aprovar
        else {"type": "reject", "message": "O cliente desistiu do cancelamento."}
    )
    print(f"decisão humana: {decisao['type']}\n")

    # Retoma a MESMA thread. É o thread_id que amarra a retomada, não o objeto.
    resultado = agente.invoke(
        Command(resume={"decisions": [decisao]}),
        config=config,
        version="v2",
    )

    print("resposta:", responder(resultado))
    print("status final:", dados.ASSINATURAS["cliente_123"]["status"])


if __name__ == "__main__":
    main()
