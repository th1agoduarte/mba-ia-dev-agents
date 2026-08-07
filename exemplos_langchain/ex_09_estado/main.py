"""Dois clientes, o mesmo agente: o contexto decide quem está sendo atendido.

    uv run python -m exemplos_langchain.ex_09_estado.main
"""

from exemplos_langchain.ex_09_estado.agente import Contexto, agente


def conversar(thread: str, cliente_id: str, texto: str) -> dict:
    resultado = agente.invoke(
        {"messages": [{"role": "user", "content": texto}]},
        config={"configurable": {"thread_id": thread}},
        context=Contexto(cliente_id=cliente_id),
    )
    print(f"\n[{cliente_id} / thread {thread}] {texto}")
    print(f"[agente] {resultado['messages'][-1].text}")
    return resultado


def main() -> None:
    # cliente_123 JÁ respondeu a pesquisa (ver acme/dados.RESPONDERAM_PESQUISA):
    # o agente vai direto ao assunto.
    conversar("t-123", "cliente_123", "Quais são as minhas faturas?")

    # cliente_456 NÃO respondeu: o agente conduz a pesquisa antes.
    conversar("t-456", "cliente_456", "Quais são as minhas faturas?")

    # A resposta abaixo é registrada no estado pela tool `registrar_pesquisa`.
    resultado = conversar(
        "t-456",
        "cliente_456",
        "A experiência tem sido ruim, o sistema vive fora do ar.",
    )

    print("\n--- estado da thread t-456 ---")
    print("pesquisa_satisfacao:", resultado.get("pesquisa_satisfacao"))

    # Com sentimento negativo no estado, o prompt dinâmico manda oferecer desconto.
    conversar("t-456", "cliente_456", "Quero cancelar minha assinatura.")

    # Note que as faturas listadas em cada thread são de clientes diferentes,
    # embora o texto da pergunta seja idêntico: quem decide é o context.


if __name__ == "__main__":
    main()
