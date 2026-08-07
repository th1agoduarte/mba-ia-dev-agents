"""A montagem do grafo — equivale ao `Workflow(edges=[...])` do ADK.

ADK:
    Workflow(edges=[
        (START, triage_ticket_node, {"refuse": ..., "attendant": ..., ...}),
        (attendant_agent, finish_ticket_node),
        ...
    ])

LangGraph: os nós são registrados por nome e as arestas ligadas depois. Como os
nós de triagem devolvem `Command(goto=...)`, o roteamento condicional já está
declarado neles — por isso aqui só aparecem as arestas FIXAS.

Topologia:

    START → triagem ─┬─ recusar ───────────────────────────────────→ END
                     ├─ no_atendente → finalizar ──────────────────→ END
                     └─ no_investigador → triagem_refund ─┬─ refund_automatico → END
                                                          └─ no_escalonador
                                                               → triagem_escalacao ─┬─ encerrar_escalado → END
                                                                                    └─ aguardar_aprovacao
                                                                                         ⏸ interrupt
                                                                                         → efetivar_refund → END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from exemplos_langgraph.acme.config import checkpointer_padrao
from exemplos_langgraph.grafo import nos
from exemplos_langgraph.grafo.estado import EstadoResolucao


def construir_grafo(checkpointer=None):
    """Monta e compila o grafo.

    O `checkpointer` é OBRIGATÓRIO para o `interrupt()` do nó de aprovação
    funcionar: é ele que guarda o estado enquanto o humano não decide. Sem ele,
    o grafo levanta erro ao tentar pausar.
    """
    construtor = StateGraph(EstadoResolucao)

    construtor.add_node("triagem", nos.triagem)
    construtor.add_node("recusar", nos.recusar)
    construtor.add_node("no_atendente", nos.no_atendente)
    construtor.add_node("finalizar", nos.finalizar)
    construtor.add_node("no_investigador", nos.no_investigador)
    construtor.add_node("triagem_refund", nos.triagem_refund)
    construtor.add_node("refund_automatico", nos.refund_automatico)
    construtor.add_node("no_escalonador", nos.no_escalonador)
    construtor.add_node("triagem_escalacao", nos.triagem_escalacao)
    construtor.add_node("encerrar_escalado", nos.encerrar_escalado)
    construtor.add_node("aguardar_aprovacao", nos.aguardar_aprovacao)
    construtor.add_node("efetivar_refund", nos.efetivar_refund)

    construtor.add_edge(START, "triagem")
    # As saídas de `triagem` e `triagem_refund` não aparecem aqui: quem as
    # declara é o `Command(goto=...)` dentro de cada nó.
    construtor.add_edge("recusar", END)
    construtor.add_edge("no_atendente", "finalizar")
    construtor.add_edge("finalizar", END)
    construtor.add_edge("no_investigador", "triagem_refund")
    construtor.add_edge("refund_automatico", END)
    construtor.add_edge("no_escalonador", "triagem_escalacao")
    construtor.add_edge("encerrar_escalado", END)
    construtor.add_edge("aguardar_aprovacao", "efetivar_refund")
    construtor.add_edge("efetivar_refund", END)

    if checkpointer is None:
        checkpointer = checkpointer_padrao()
    return construtor.compile(checkpointer=checkpointer)


grafo = construir_grafo()
