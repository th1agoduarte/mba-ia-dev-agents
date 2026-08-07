"""Mostra a saída estruturada do subagente.

    uv run python -m exemplos_langchain.ex_06_subagente_oneshot.main
"""

from exemplos_langchain.ex_06_subagente_oneshot.agente import StatusPlataforma, especialista_status, agente


def main() -> None:
    # 1. O subagente sozinho: a resposta vem tipada, não como texto.
    direto = especialista_status.invoke(
        {"messages": [{"role": "user", "content": "Qual o status da plataforma?"}]}
    )
    estruturado: StatusPlataforma = direto["structured_response"]
    print("subagente isolado ->", repr(estruturado))
    print("  tipo:", type(estruturado).__name__, "| disponivel:", estruturado.disponivel)

    # 2. O coordenador usando o subagente como ferramenta.
    resultado = agente.invoke(
        {
            "messages": [
                {"role": "user", "content": "Liste minhas faturas. Sou o cliente_123."}
            ]
        }
    )
    print("\n[agente]", resultado["messages"][-1].text)


if __name__ == "__main__":
    main()
