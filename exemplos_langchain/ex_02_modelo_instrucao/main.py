"""Executa o agente com instrução.

    uv run python -m exemplos_langchain.ex_02_modelo_instrucao.main
"""

from exemplos_langchain.ex_02_modelo_instrucao.agente import agente


def main() -> None:
    resultado = agente.invoke({"messages": [{"role": "user", "content": "Pode começar."}]})
    print(resultado["messages"][-1].text)


if __name__ == "__main__":
    main()
