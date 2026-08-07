"""Domínio da Acme Cloud em memória: tickets, faturamento e escalações.

Substitui `db/repo.py`, `outside/mock_billing_server.py` e o MCP do Linear do
projeto ADK. Nada de LangChain aqui — trocar por Postgres e por um MCP real seria
mexer só neste arquivo.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CategoriaTicket(str, Enum):
    BILLING = "billing"
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    ONBOARDING = "onboarding"
    COMPOSITE = "composite"
    UNDEFINED = "undefined"
    OUT_OF_SCOPE = "out_of_scope"


class StatusTicket(str, Enum):
    PENDENTE = "pendente"
    AGUARDANDO_APROVACAO = "aguardando_aprovacao"
    RESOLVIDO = "resolvido"
    ESCALADO = "escalado"
    FALHOU = "falhou"


@dataclass
class Ticket:
    id: str
    cliente_id: str
    mensagem: str
    categoria: CategoriaTicket
    confianca: float
    justificativa: str
    precisa_refund: bool = False
    status: StatusTicket = StatusTicket.PENDENTE
    resposta: str = ""
    erro: str = ""


TICKETS: dict[str, Ticket] = {}


def semear_tickets() -> None:
    """Popula tickets de exemplo, um por cenário do `main.py`."""
    TICKETS.clear()
    for ticket in [
        Ticket(
            id="TICKET-0001",
            cliente_id="cliente_123",
            mensagem="A fatura de 2024-02 veio com o plano Pro cobrado duas vezes. Quero o estorno da cobrança repetida.",
            categoria=CategoriaTicket.BILLING,
            confianca=0.95,
            justificativa="Cliente relata cobrança duplicada do plano.",
            precisa_refund=True,
        ),
        Ticket(
            id="TICKET-0002",
            cliente_id="cliente_456",
            mensagem="A fatura de 2024-02 tem um ajuste ADJ-991 de 120 dólares que ninguém explicou. Quero estorno.",
            categoria=CategoriaTicket.BILLING,
            confianca=0.9,
            justificativa="Ajuste manual sem justificativa na fatura.",
            precisa_refund=True,
        ),
        Ticket(
            id="TICKET-0003",
            cliente_id="cliente_123",
            mensagem="Como faço para adicionar um membro na minha equipe?",
            categoria=CategoriaTicket.ONBOARDING,
            confianca=0.9,
            justificativa="Dúvida de uso da plataforma.",
            precisa_refund=False,
        ),
        Ticket(
            id="TICKET-0004",
            cliente_id="cliente_789",
            mensagem="Bom dia, qual a cotação do bitcoin hoje?",
            categoria=CategoriaTicket.OUT_OF_SCOPE,
            confianca=0.98,
            justificativa="Não é um pedido de suporte da Acme.",
            precisa_refund=False,
        ),
    ]:
        TICKETS[ticket.id] = ticket


def buscar_ticket(ticket_id: str) -> Ticket | None:
    return TICKETS.get(ticket_id)


def salvar_ticket(ticket: Ticket) -> Ticket:
    TICKETS[ticket.id] = ticket
    return ticket


# --- faturamento -------------------------------------------------------------
# Cada fatura tem LINHAS. Repare que nenhuma linha diz "isto é indevido": quem
# julga é o agente investigador, pela política. Um billing real também não sabe.

FATURAS: dict[str, list[dict]] = {
    "cliente_123": [
        {
            "month": "2024-02",
            "items": [
                {"id": "it-1", "sku": "PLAN-PRO", "amount": 49.99, "description": "Assinatura mensal Pro"},
                {"id": "it-2", "sku": "PLAN-PRO", "amount": 49.99, "description": "Assinatura mensal Pro"},
                {"id": "it-3", "sku": "OVERAGE-API", "amount": 12.50, "description": "Excedente de chamadas de API"},
            ],
        }
    ],
    "cliente_456": [
        {
            "month": "2024-02",
            "items": [
                {"id": "it-9", "sku": "PLAN-ENTERPRISE", "amount": 149.99, "description": "Assinatura mensal Enterprise"},
                {"id": "it-10", "sku": "ADJ-991", "amount": 120.00, "description": "Ajuste manual"},
            ],
        }
    ],
}

REFUNDS_EMITIDOS: list[dict] = []


def listar_faturas(cliente_id: str) -> list[dict]:
    return FATURAS.get(cliente_id, [])


def buscar_fatura(cliente_id: str, mes: str) -> dict | None:
    for fatura in listar_faturas(cliente_id):
        if fatura["month"] == mes:
            return fatura
    return None


def emitir_refund(cliente_id: str, valor: float, motivo: str, ticket_id: str) -> dict:
    """Efetiva o estorno. IDEMPOTENTE por ticket_id.

    A idempotência não é decoração: um grafo com `interrupt()` pode reexecutar o
    corpo de um nó ao retomar. Se o efeito não for idempotente, o cliente recebe
    o dinheiro duas vezes.
    """
    for existente in REFUNDS_EMITIDOS:
        if existente["ticket_id"] == ticket_id:
            return {**existente, "status": "reaproveitado"}
    registro = {
        "ticket_id": ticket_id,
        "cliente_id": cliente_id,
        "valor": valor,
        "motivo": motivo,
        "status": "emitido",
    }
    REFUNDS_EMITIDOS.append(registro)
    return registro


# --- escalações (substitui o Linear) -----------------------------------------

ESCALACOES: dict[str, dict] = {}


def buscar_escalacao(ticket_id: str) -> dict | None:
    return ESCALACOES.get(ticket_id)


def criar_escalacao(ticket_id: str, resumo: str, severidade: str, intencao: str) -> dict:
    """Cria o card de handoff humano. Também idempotente por ticket_id."""
    if ticket_id in ESCALACOES:
        return {**ESCALACOES[ticket_id], "status": "reaproveitado"}
    escalacao = {
        "ticket_id": ticket_id,
        "resumo": resumo,
        "severidade": severidade,
        "intencao": intencao,
        "referencia_externa": f"ACME-{len(ESCALACOES) + 1:03d}",
        "status": "criado",
    }
    ESCALACOES[ticket_id] = escalacao
    return escalacao


def limpar() -> None:
    """Zera o estado mutável. Usado pelos verificadores e pelo main."""
    REFUNDS_EMITIDOS.clear()
    ESCALACOES.clear()
    semear_tickets()


semear_tickets()
