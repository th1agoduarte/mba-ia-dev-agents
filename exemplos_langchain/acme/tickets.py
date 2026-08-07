"""Central de tickets da Acme Cloud: enums e um repositório em memória.

Espelha `db/models.py` + `db/repo.py` do projeto ADK, sem banco. A troca por
Postgres seria substituir só as funções deste módulo — nenhum agente conhece a
forma de armazenamento.
"""

from dataclasses import dataclass, field, replace
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
class Classificacao:
    categoria: CategoriaTicket
    confianca: float
    justificativa: str
    precisa_refund: bool = False


@dataclass
class Ticket:
    id: str
    cliente_id: str
    mensagem: str
    classificacao: Classificacao
    status: StatusTicket = StatusTicket.PENDENTE
    resposta: str = ""


_TICKETS: dict[str, Ticket] = {}
_PROXIMO_ID: list[int] = [1]


def criar_ticket(cliente_id: str, mensagem: str, classificacao: Classificacao) -> Ticket:
    ticket_id = f"TICKET-{_PROXIMO_ID[0]:04d}"
    _PROXIMO_ID[0] += 1
    ticket = Ticket(
        id=ticket_id,
        cliente_id=cliente_id,
        mensagem=mensagem,
        classificacao=classificacao,
    )
    _TICKETS[ticket_id] = ticket
    return ticket


def buscar_ticket(ticket_id: str) -> Ticket | None:
    return _TICKETS.get(ticket_id)


def listar_tickets(
    cliente_id: str | None = None, status: StatusTicket | None = None
) -> list[Ticket]:
    tickets = list(_TICKETS.values())
    if cliente_id:
        tickets = [t for t in tickets if t.cliente_id == cliente_id]
    if status:
        tickets = [t for t in tickets if t.status == status]
    return tickets


def atualizar_ticket(ticket: Ticket) -> Ticket:
    _TICKETS[ticket.id] = ticket
    return ticket


def limpar() -> None:
    """Zera o repositório. Usado pelos verificadores."""
    _TICKETS.clear()
    _PROXIMO_ID[0] = 1


def como_dict(ticket: Ticket) -> dict:
    return {
        "id": ticket.id,
        "cliente_id": ticket.cliente_id,
        "mensagem": ticket.mensagem,
        "status": ticket.status.value,
        "categoria": ticket.classificacao.categoria.value,
        "resposta": ticket.resposta,
    }


__all__ = [
    "CategoriaTicket",
    "Classificacao",
    "StatusTicket",
    "Ticket",
    "atualizar_ticket",
    "buscar_ticket",
    "como_dict",
    "criar_ticket",
    "field",
    "limpar",
    "listar_tickets",
    "replace",
]
