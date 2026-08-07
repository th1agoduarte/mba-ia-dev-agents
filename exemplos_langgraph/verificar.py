"""Verificação do grafo: cenários com LLM e bordas determinísticas.

    cd exemplos-langgraph && uv run python verificar.py

A maior parte dos casos NÃO chama modelo: o cálculo do valor, a severidade e a
idempotência são código puro, e é justamente aí que mora o risco financeiro.
"""

from __future__ import annotations

import sys

from langgraph.types import Command

from exemplos_langgraph.acme import dominio
from exemplos_langgraph.acme.config import LIMIAR_APROVACAO, TETO_REFUND
from exemplos_langgraph.acme.dominio import StatusTicket
from exemplos_langgraph.grafo import nos
from exemplos_langgraph.grafo.grafo import construir_grafo

RESULTADOS: list[tuple[bool, str, str]] = []


def checar(nome: str, obtido, esperado) -> None:
    ok = obtido == esperado
    RESULTADOS.append((ok, nome, "" if ok else f"esperado {esperado!r}, veio {obtido!r}"))


# --- cálculo do refund: os ramos que o original deixava incompletos ----------

checar(
    "soma: mês sem fatura vira sem_fatura (e não KeyError)",
    nos._somar_linhas("cliente_123", "2030-01", ["it-1"])["status"],
    "sem_fatura",
)
checar(
    "soma: ids que não existem viram linhas_invalidas",
    nos._somar_linhas("cliente_123", "2024-02", ["nao-existe"])["status"],
    "linhas_invalidas",
)
checar(
    "soma: cliente desconhecido vira sem_fatura",
    nos._somar_linhas("cliente_000", "2024-02", ["it-1"])["status"],
    "sem_fatura",
)
_acima = nos._somar_linhas("cliente_456", "2024-02", ["it-9", "it-10"])
checar("soma: acima do teto é bloqueado", _acima["status"], "acima_do_teto")
checar("soma: valor somado pelo CÓDIGO", _acima["valor"], 269.99)
checar(
    "soma: ids inexistentes são ignorados, os válidos somam",
    nos._somar_linhas("cliente_123", "2024-02", ["it-1", "fantasma"])["valor"],
    49.99,
)
checar(
    "soma: uma linha válida abaixo do teto é ok",
    nos._somar_linhas("cliente_123", "2024-02", ["it-1"])["status"],
    "ok",
)

# --- severidade determinística ----------------------------------------------

checar("severidade: acima do teto é high", nos._severidade("acima_do_teto", 999.0), "high")
checar("severidade: sem fatura é low", nos._severidade("sem_fatura", None), "low")
checar("severidade: linhas inválidas é low", nos._severidade("linhas_invalidas", None), "low")
checar(
    "severidade: valor acima de 2x o limiar é high",
    nos._severidade("ok", 2 * LIMIAR_APROVACAO + 1),
    "high",
)
checar("severidade: banda baixa é medium", nos._severidade("ok", LIMIAR_APROVACAO + 1), "medium")

# --- idempotência dos efeitos -----------------------------------------------

dominio.limpar()
_p = dominio.emitir_refund("cliente_123", 10.0, "teste", "TICKET-X")
_s = dominio.emitir_refund("cliente_123", 10.0, "teste", "TICKET-X")
checar("refund: primeira emissão", _p["status"], "emitido")
checar("refund: segunda emissão do MESMO ticket é reaproveitada", _s["status"], "reaproveitado")
checar("refund: só um registro no total", len(dominio.REFUNDS_EMITIDOS), 1)

_e1 = dominio.criar_escalacao("TICKET-Y", "resumo", "medium", "handoff")
_e2 = dominio.criar_escalacao("TICKET-Y", "outro", "high", "handoff")
checar("escalação: segunda criação é reaproveitada", _e2["status"], "reaproveitado")
checar("escalação: referência preservada", _e2["referencia_externa"], _e1["referencia_externa"])

# --- cenários ponta a ponta (com LLM) ---------------------------------------

dominio.limpar()
_grafo = construir_grafo()


def _resolver(ticket_id: str):
    return _grafo.invoke(
        {"ticket_id": ticket_id}, config={"configurable": {"thread_id": ticket_id}}
    )


def _ticket(ticket_id: str):
    """Busca o ticket e falha alto se sumiu — nenhuma asserção faz sentido sem ele."""
    t = dominio.buscar_ticket(ticket_id)
    if t is None:
        raise AssertionError(f"ticket {ticket_id} desapareceu do repositório")
    return t


_resolver("TICKET-0004")
checar(
    "cenário fora de escopo: recusado sem chamar modelo",
    _ticket("TICKET-0004").status,
    StatusTicket.RESOLVIDO,
)
checar(
    "cenário fora de escopo: nenhum refund",
    len(dominio.REFUNDS_EMITIDOS),
    0,
)

_resolver("TICKET-0003")
checar(
    "cenário dúvida de uso: resolvido pelo atendente",
    _ticket("TICKET-0003").status,
    StatusTicket.RESOLVIDO,
)
checar(
    "cenário dúvida de uso: resposta não vazia",
    len(_ticket("TICKET-0003").resposta) > 30,
    True,
)

_resolver("TICKET-0001")
_refunds_1 = [r for r in dominio.REFUNDS_EMITIDOS if r["ticket_id"] == "TICKET-0001"]
checar("cenário refund automático: um estorno emitido", len(_refunds_1), 1)
checar(
    "cenário refund automático: valor abaixo do limiar",
    _refunds_1[0]["valor"] <= LIMIAR_APROVACAO if _refunds_1 else False,
    True,
)

_pausado = _resolver("TICKET-0002")
checar("cenário refund alto: grafo pausou", bool(_pausado.get("__interrupt__")), True)
checar(
    "cenário refund alto: NADA foi estornado durante a pausa",
    [r for r in dominio.REFUNDS_EMITIDOS if r["ticket_id"] == "TICKET-0002"],
    [],
)
checar(
    "cenário refund alto: card de escalação criado antes da pausa",
    dominio.buscar_escalacao("TICKET-0002") is not None,
    True,
)
checar(
    "cenário refund alto: ticket fica AGUARDANDO_APROVACAO durante a pausa",
    _ticket("TICKET-0002").status,
    StatusTicket.AGUARDANDO_APROVACAO,
)

_grafo.invoke(
    Command(resume={"aprovado": False}),
    config={"configurable": {"thread_id": "TICKET-0002"}},
)
checar(
    "cenário refund alto: recusa NÃO estorna",
    [r for r in dominio.REFUNDS_EMITIDOS if r["ticket_id"] == "TICKET-0002"],
    [],
)

# aprovação, numa thread nova para não reaproveitar a decisão anterior
dominio.limpar()
_grafo2 = construir_grafo()
_grafo2.invoke({"ticket_id": "TICKET-0002"}, config={"configurable": {"thread_id": "aprovar"}})
_grafo2.invoke(
    Command(resume={"aprovado": True}), config={"configurable": {"thread_id": "aprovar"}}
)
_refunds_2 = [r for r in dominio.REFUNDS_EMITIDOS if r["ticket_id"] == "TICKET-0002"]
checar("cenário refund alto: aprovação estorna uma vez", len(_refunds_2), 1)
checar(
    "cenário refund alto: valor acima do limiar e abaixo do teto",
    LIMIAR_APROVACAO < _refunds_2[0]["valor"] <= TETO_REFUND if _refunds_2 else False,
    True,
)

# --- placar ------------------------------------------------------------------

_falhas = [r for r in RESULTADOS if not r[0]]
for ok, nome, detalhe in RESULTADOS:
    print(f"{'passou' if ok else 'FALHOU'}  {nome}")
    if detalhe:
        print(f"          {detalhe}")
print(f"\n{len(RESULTADOS) - len(_falhas)}/{len(RESULTADOS)} casos passaram")
sys.exit(1 if _falhas else 0)
