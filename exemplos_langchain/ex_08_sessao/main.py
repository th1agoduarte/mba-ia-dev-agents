"""Memória de conversa em RAM: o segundo turno enxerga o primeiro.

    uv run python -m exemplos_langchain.ex_08_sessao.main
"""

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from exemplos_langchain.ex_08_sessao.agente import criar_agente

TURNOS = [
    "Oi! Sou o cliente_123.",
    "Quais são as minhas faturas?",
    "E qual o meu plano?",
]


def main() -> None:
    agente = criar_agente(InMemorySaver())

    # O thread_id é escolhido por você — aqui, o próprio id do cliente.
    config: RunnableConfig = {"configurable": {"thread_id": "cliente_123"}}

    for turno in TURNOS:
        resultado = agente.invoke(
            {"messages": [{"role": "user", "content": turno}]}, config=config
        )
        print(f"\n[usuário] {turno}")
        print(f"[agente] {resultado['messages'][-1].text}")

    # Uma thread diferente não sabe nada da conversa acima.
    outro = agente.invoke(
        {"messages": [{"role": "user", "content": "Qual o meu plano?"}]},
        config={"configurable": {"thread_id": "outra-conversa"}},
    )
    print("\n--- thread nova (sem histórico) ---")
    print(f"[agente] {outro['messages'][-1].text}")


if __name__ == "__main__":
    main()
