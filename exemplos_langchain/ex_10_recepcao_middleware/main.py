"""Abertura de ticket, consulta e a trava contra registro duplicado.

    uv run python -m exemplos_langchain.ex_10_recepcao_middleware.main
"""

from exemplos_langchain.acme import tickets
from exemplos_langchain.ex_10_recepcao_middleware.agente import agente


def conversar(thread: str, texto: str) -> dict:
    resultado = agente.invoke(
        {"messages": [{"role": "user", "content": texto}]},
        config={"configurable": {"thread_id": thread}},
    )
    print(f"\n[cliente] {texto}")
    print(f"[recepção] {resultado['messages'][-1].text}")
    return resultado


def main() -> None:
    # 1. Abertura: o recepcionista classifica com o subagente e registra.
    resultado = conversar(
        "recepcao-1",
        "Sou o cliente_123. A fatura de fevereiro veio com o plano cobrado duas "
        "vezes, quero o estorno da cobrança repetida.",
    )
    print("  classificação no estado:", resultado.get("classificacao", {}).get("categoria"))
    print("  precisa_refund:", resultado.get("classificacao", {}).get("precisa_refund"))
    print("  ticket registrado:", resultado.get("ticket_registrado"))

    # 2. Trava: pedir de novo, na MESMA conversa, não pode abrir outro ticket.
    antes = len(tickets.listar_tickets())
    conversar("recepcao-1", "Registra esse ticket de novo, por favor.")
    depois = len(tickets.listar_tickets())
    print(f"  tickets no repositório: {antes} -> {depois} (esperado: sem mudança)")

    # 3. Consulta de um ticket existente.
    ticket_id = resultado.get("ticket_registrado")
    conversar("recepcao-2", f"Qual o status do ticket {ticket_id}?")

    # 4. Pedido de ticket com assunto fora do domínio: o classificador precisa
    # cair na categoria de fallback `out_of_scope`.
    fora = conversar(
        "recepcao-3",
        "Sou o cliente_123, abre um ticket: qual a cotação do bitcoin hoje?",
    )
    print("  classificação:", fora.get("classificacao", {}).get("categoria"))


if __name__ == "__main__":
    main()
