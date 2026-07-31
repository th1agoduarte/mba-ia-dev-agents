from db import repo
from db.models import TicketEscalationModel

# As chaves são os valores do `EscalatorIntent` — a tool e o agente falam o MESMO
# vocabulário, senão o LLM precisa adivinhar a tradução (e às vezes erra).
_TITLE_PREFIX = {
    "refund_confirmation": "[Aprovação humana]",
    "handoff": "[Handoff humano]",
}

_BODY_PROTOCOL = {
    "refund_confirmation": (
        "Para APROVAR a ação solicitada, mova este issue para Done; "
        "para RECUSAR, mova para Canceled."
    ),
    "handoff": (
        "Caso sem resolução automática — um humano precisa assumir e "
        "conduzir manualmente."
    ),
}

_TITLE_MAX = 80


def _format_escalation(
    intent: str, summary: str, ticket_id: str, customer_id: str
) -> tuple[str, str]:
    title = f"{_TITLE_PREFIX[intent]} {ticket_id}: {summary}"
    if len(title) > _TITLE_MAX:
        title = title[: _TITLE_MAX - 1] + "…"
    body = (
        f"Ticket: {ticket_id}\n"
        f"Cliente: {customer_id}\n\n"
        f"{summary}\n\n"
        f"{_BODY_PROTOCOL[intent]}"
    )
    return title, body


async def create_ticket_escalation(
    ticket_id: str,
    customer_id: str,
    intent: str,
    summary: str,
    severity: str = "medium",
    external_ref: str | None = None,
):
    """
     Cria uma escalação de ticket (registro no banco e issue no Linear) se não existir.
    Args:
        ticket_id: ID do ticket a ser escalado.
        customer_id: ID do cliente do ticket.
        intent: Tipo de handoff: `refund_confirmation` ou `handoff` — repasse o
            mesmo valor que veio no pedido, sem traduzir.
        summary: Resumo do motivo da escalação.
        severity: Severidade da escalação: low | medium | high | urgent.
        external_ref: ID da issue no Linear (se já existir).    
    Returns:
        Dict com id, ticket_id, severity, status (`created`|`reused`|`failed`) e
        external_ref.
    """
    if intent not in _TITLE_PREFIX:
        return {
            "status": "failed",
            "error": (
                f"intent inválido: {intent!r}; use 'refund_confirmation' ou 'handoff'."
            ),
        }

    existing = await repo.get_ticket_escalation(ticket_id)
    if existing is not None:
        return {
            "id": existing.id,
            "ticket_id": existing.ticket_id,
            "severity": existing.severity,
            "status": "reused",
            "external_ref": existing.external_ref,
        }

    title, body = _format_escalation(intent, summary, ticket_id, customer_id)
    ticket_escalation = await repo.create_ticket_escalation(
        ticket_escalation=TicketEscalationModel(
            ticket_id=ticket_id,
            title=title,
            body=body,
            severity=severity,
            external_ref=external_ref,
        )
    )
    return {
        "id": ticket_escalation.id,
        "ticket_id": ticket_escalation.ticket_id,
        "severity": ticket_escalation.severity,
        "status": "created",
        "external_ref": ticket_escalation.external_ref,
    }

async def get_ticket_escalation(ticket_id: str) -> dict:
    """
    Checa se este ticket JÁ tem uma escalação aberta (e issue no Linear).
    Args:
        ticket_id: ID do ticket a ser checado.
    Returns:
        `{"exists": bool, "external_ref": str|None, "id": int|None}`.
    """
    existing = await repo.get_ticket_escalation(ticket_id)
    if existing is None:
        return {"exists": False, "external_ref": None, "id": None}
    return {
        "exists": True,
        "external_ref": existing.external_ref,
        "id": existing.id,
    }
