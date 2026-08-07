"""Executa o agente mínimo.

    uv run python -m exemplos_langchain.ex_01_agente_minimo.main
"""

from exemplos_langchain.ex_01_agente_minimo.agente import agente


def main() -> None:
    # A entrada é sempre uma lista de mensagens; a saída traz a conversa inteira,
    # com a resposta do modelo na última posição.
    resultado = agente.invoke(
        {"messages": [{"role": "user", "content": "Olá! Quem é você?"}]}
    )
    print(resultado["messages"][-1].text)


if __name__ == "__main__":
    main()
