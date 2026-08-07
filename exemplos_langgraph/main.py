"""Roda os quatro cenários de resolução de ticket.

    cd exemplos-langgraph && uv run python main.py
    cd exemplos-langgraph && uv run python main.py recusar   # recusa o refund do cenário 4
"""

from __future__ import annotations

import sys

from langgraph.types import Command

from exemplos_langgraph.acme import dominio
from exemplos_langgraph.grafo.grafo import construir_grafo


def resolver(grafo, ticket_id: str) -> dict:
    """Roda o grafo para um ticket. A thread é o próprio id do ticket."""
    return grafo.invoke(
        {"ticket_id": ticket_id},
        config={"configurable": {"thread_id": ticket_id}},
    )


def mostrar(titulo: str, ticket_id: str) -> None:
    ticket = dominio.buscar_ticket(ticket_id)
    print(f"\n=== {titulo} ({ticket_id}) ===")
    if ticket is None:
        print(f"  ticket {ticket_id} não encontrado")
        return
    print(f"  categoria: {ticket.categoria.value} | precisa_refund: {ticket.precisa_refund}")
    print(f"  status final: {ticket.status.value}")
    print(f"  resposta: {ticket.resposta[:160]}")


def main() -> None:
    aprovar = "recusar" not in sys.argv
    dominio.limpar()
    grafo = construir_grafo()

    # 1. Fora de escopo: a triagem recusa sem chamar modelo nenhum.
    resolver(grafo, "TICKET-0004")
    mostrar("fora de escopo -> recusa determinística", "TICKET-0004")

    # 2. Dúvida de uso: rota do atendente.
    resolver(grafo, "TICKET-0003")
    mostrar("dúvida de uso -> atendente", "TICKET-0003")

    # 3. Refund pequeno (plano duplicado, $49,99 < limiar de $50): automático.
    resolver(grafo, "TICKET-0001")
    mostrar("refund abaixo do limiar -> automático", "TICKET-0001")
    print(f"  refunds emitidos: {dominio.REFUNDS_EMITIDOS}")

    # 4. Refund grande (ajuste de $120 > limiar): escala e PAUSA para o humano.
    resultado = resolver(grafo, "TICKET-0002")
    if not resultado.get("__interrupt__"):
        print("\n=== refund acima do limiar ===")
        print("  não pausou (o investigador pode ter decidido escalar direto)")
        mostrar("refund acima do limiar", "TICKET-0002")
        return

    pausa = resultado["__interrupt__"][0].value
    print("\n=== refund acima do limiar -> aprovação humana (TICKET-0002) ===")
    print(f"  grafo PAUSADO: {pausa['pergunta']} valor=${pausa['valor']:.2f}")
    escalacao = dominio.buscar_escalacao("TICKET-0002") or {}
    print(
        f"  card de escalação: {escalacao.get('referencia_externa', 'N/D')} "
        f"({escalacao.get('severidade', 'N/D')})"
    )
    deste = [r for r in dominio.REFUNDS_EMITIDOS if r["ticket_id"] == "TICKET-0002"]
    print(f"  refunds DESTE ticket antes da decisão: {len(deste)} (tem de ser 0)")

    grafo.invoke(
        Command(resume={"aprovado": aprovar}),
        config={"configurable": {"thread_id": "TICKET-0002"}},
    )
    print(f"  decisão humana: {'aprovado' if aprovar else 'recusado'}")
    mostrar("depois da decisão", "TICKET-0002")
    deste = [r for r in dominio.REFUNDS_EMITIDOS if r["ticket_id"] == "TICKET-0002"]
    print(f"  refunds DESTE ticket depois: {len(deste)} (1 se aprovado, 0 se recusado)")


if __name__ == "__main__":
    main()
