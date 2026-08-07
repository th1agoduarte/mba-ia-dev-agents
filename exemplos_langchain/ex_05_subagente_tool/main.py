"""O coordenador delega ao subagente de status depois de um erro de sistema.

    uv run python -m exemplos_langchain.ex_05_subagente_tool.main
"""

from langchain.messages import AIMessage

from exemplos_langchain.ex_05_subagente_tool.agente import agente


def main() -> None:
    resultado = agente.invoke(
        {
            "messages": [
                {"role": "user", "content": "Liste minhas faturas. Sou o cliente_123."}
            ]
        }
    )

    chamadas = [
        c["name"]
        for m in resultado["messages"]
        if isinstance(m, AIMessage)
        for c in (m.tool_calls or [])
    ]
    print("ferramentas chamadas:", chamadas)
    print("\n[agente]", resultado["messages"][-1].text)


if __name__ == "__main__":
    main()
