"""O subagente pausa para perguntar, e a execução retoma de onde parou.

    uv run python -m exemplos_langchain.ex_07_subagente_clarificacao.main
"""

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from exemplos_langchain.acme import dados
from exemplos_langchain.ex_07_subagente_clarificacao.agente import agente


def main() -> None:
    config: RunnableConfig = {"configurable": {"thread_id": "plano-1"}}

    print("plano inicial:", dados.ASSINATURAS["cliente_123"]["plano"])

    # Pedido deliberadamente incompleto: não diz para qual plano mudar.
    resultado = agente.invoke(
        {
            "messages": [
                {"role": "user", "content": "Sou o cliente_123 e quero mudar de plano."}
            ]
        },
        config=config,
        version="v2",
    )

    if not resultado.interrupts:
        print("não pausou:", resultado.value["messages"][-1].text)
        return

    pergunta = resultado.interrupts[0].value["pergunta"]
    print(f"\n[subagente pergunta] {pergunta}")

    resposta_humana = "Quero o plano Enterprise."
    print(f"[usuário responde] {resposta_humana}\n")

    # O valor do resume vira o retorno de interrupt() lá dentro do subagente.
    resultado = agente.invoke(
        Command(resume=resposta_humana), config=config, version="v2"
    )

    print("[agente]", resultado.value["messages"][-1].text)
    print("plano final:", dados.ASSINATURAS["cliente_123"]["plano"])


if __name__ == "__main__":
    main()
