"""Mostra a conversa mudando de especialista entre turnos.

    uv run python -m exemplos_langchain.ex_04_handoffs.main
"""

from langchain_core.runnables import RunnableConfig

from exemplos_langchain.ex_04_handoffs.agente import agente

TURNOS = [
    "Quero ver minhas faturas. Sou o cliente_123.",
    "E qual é o meu plano hoje?",
]


def main() -> None:
    config: RunnableConfig = {"configurable": {"thread_id": "handoff-1"}}

    for turno in TURNOS:
        resultado = agente.invoke(
            {"messages": [{"role": "user", "content": turno}]}, config=config
        )
        ativo = resultado.get("especialista_ativo", "coordenador")
        print(f"\n[usuário] {turno}")
        print(f"[especialista ativo: {ativo}]")
        print(f"[agente] {resultado['messages'][-1].text}")


if __name__ == "__main__":
    main()
