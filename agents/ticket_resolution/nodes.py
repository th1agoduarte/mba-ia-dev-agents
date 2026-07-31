from google.adk.workflow import node
from google.adk import Context, Event
from pydantic import BaseModel, Field
from agents.ticket_resolution.agents.attendant.agent import AttendantOutput
from google.adk.events import EventActions, RequestInput
from agents.ticket_resolution.agents.escalator.agent import EscalatorInput, EscalatorIntent, EscalatorOutput
from agents.ticket_resolution.agents.refund_investigator.agent import (
    RefundInvestigatorOutput,
    VerdictDecision,
)
from db import repo
from db.models import TicketCategory, TicketStatus
from outside import mock_billing_server as _billing
from env import REFUND_APPROVAL_THRESHOLD, REFUND_MAX_LIMIT


def _needs_refund_resolution(needs_refund: bool, confidence: float) -> bool:
    return needs_refund and confidence >= 0.6


@node
async def triage_ticket_node(ctx: Context):
    ticket_id = ctx.state.get("ticket_id")

    ticket = await repo.get_ticket(ticket_id)

    if not ticket:
        # type: ignore
        return Event(message=f"Ticket {ticket_id} não encontrado.")

    classification = ticket.classification

    if classification.category == TicketCategory.OUT_OF_SCOPE:
        return Event(actions=EventActions(route="refuse"))

    ctx.state["ticket_message"] = ticket.message
    ctx.state["classification_justification"] = classification.justification
    ctx.state["customer_id"] = ticket.customer_id

    if _needs_refund_resolution(classification.needs_refund, classification.confidence):
        return Event(actions=EventActions(route="refund_investigator"))

    return Event(actions=EventActions(route="attendant"))


@node
async def refuse_ticket_node(ticket_id: str):
    ticket = await repo.get_ticket(ticket_id)

    if not ticket:
        # type: ignore
        return Event(message=f"Ticket {ticket_id} não encontrado.")

    message = (
        "Olá! Este canal é exclusivo para suporte da Acme Cloud (faturamento, "
        "bugs, recursos e configuração da plataforma). Não identificamos um "
        "pedido de suporte na sua mensagem. Se precisar de ajuda com a "
        "plataforma, descreva o problema e abriremos um novo atendimento."
    )

    ticket.response = message
    ticket.status = TicketStatus.RESOLVED

    await repo.update_ticket(ticket)
    return Event(message=message)  # type: ignore


@node
async def finish_ticket_node(ticket_id: str, node_input: AttendantOutput):
    ticket = await repo.get_ticket(ticket_id)

    if not ticket:
        # type: ignore
        return Event(message=f"Ticket {ticket_id} não encontrado.")

    # if node_input.status == "error": poderia fazer algum tratamento de erro aqui

    message = node_input.message

    ticket.response = message
    ticket.status = TicketStatus.RESOLVED if node_input.status == "success" else TicketStatus.FAILED

    await repo.update_ticket(ticket)
    return Event(message=message)  # type: ignore


def _escalation_severity(
    *, calc_status: str | None = None, amount: float | None = None
) -> str:
    """Severidade DETERMINÍSTICA da escalação — nasce aqui (o gate tem o sinal),
    nunca no LLM. O mapa segue o risco de cada caminho:

    - `block_refund` (> teto absoluto)      → high   (valor anômalo, possível abuso)
    - `not_found`/`invalid`                 → low    (problema de dado, sem dinheiro em jogo)
    - aprovação com valor > 2× o limiar     → high   (dinheiro alto na banda)
    - demais (incerteza do investigator, banda baixa) → medium
    """
    if calc_status == "block_refund":
        return "high"
    if calc_status in ("not_found", "invalid"):
        return "low"
    if amount is not None and amount > 2 * REFUND_APPROVAL_THRESHOLD:
        return "high"
    return "medium"


async def _compute_refundable(customer_id: str, month: str, item_ids: list[str]) -> dict:
    """SOMA o valor real das linhas `item_ids` da fatura `{month}` — SEM efeito colateral.

    Usado pelo `refund_gate` para decidir auto/aprovação/bloqueio ANTES de qualquer
    pausa. Não toca no billing nem no banco; só lê a fatura e soma. Retorna:
    - `{"status": "not_found", ...}`   — não há fatura no mês.
    - `{"status": "invalid", ...}`     — nenhum `item_id` casa com a fatura.
    - `{"status": "block_refund", "amount", "skus", ...}` — soma acima do teto absoluto.
    - `{"status": "ok", "amount", "skus"}` — pode estornar (gate decide auto vs HITL).
    """
    inv = await _billing.get_invoice(customer_id, month)
    if "error" in inv:
        return {"status": "not_found", "reason": inv["error"]}

    by_id = {it["id"]: it for it in inv["items"]}
    selected = [by_id[i] for i in item_ids if i in by_id]
    if not selected:
        return {
            "status": "invalid",
            "reason": f"Nenhuma linha válida em {month} para os ids {item_ids}.",
        }

    amount = sum(it["amount"] for it in selected)
    skus = ", ".join(it["sku"] for it in selected)
    if amount > REFUND_MAX_LIMIT:
        return {
            "status": "block_refund",
            "amount": amount,
            "skus": skus,
            "reason": f"Refund de S${amount} acima do teto absoluto S${REFUND_MAX_LIMIT:.0f}.",
        }
    return {"status": "ok", "amount": amount, "skus": skus}


class AutoRefundRequest(BaseModel):
    refund_month: str = Field(
        description="Mês da fatura a estornar (YYYY-MM).")
    refund_amount: float = Field(description="Valor total a estornar.")
    refund_skus: str = Field(
        default="", description="SKUs das linhas a estornar.")


def _escalate_event(
    *,
    intent: EscalatorIntent,
    summary: str,
    severity: str,
    state_delta: dict | None = None,
) -> Event:
    """Roteia para o `escalator_agent` com o pedido de escalação já formatado."""
    return Event(
        actions=EventActions(route="escalate", state_delta=state_delta or {}),
        output=EscalatorInput(intent=intent, summary=summary, severity=severity),
    )


@node
async def triage_refund_node(
    ctx: Context,
    node_input: RefundInvestigatorOutput,
):
    """Portão do refund: SOMA o valor real e decide auto / aprovação / handoff.

    O investigador aponta as LINHAS; quem soma é o código. Só o caminho `auto`
    dispensa humano — qualquer incerteza (veredito de escalate, dado que não
    fecha, valor acima do teto absoluto) vira handoff.
    """
    month = node_input.month or ""
    item_ids = node_input.item_ids or []
    customer_id = ctx.state.get("customer_id")

    if node_input.decision != VerdictDecision.refund:
        return _escalate_event(
            intent=EscalatorIntent.handoff,
            summary=(
                "O investigador não encontrou base para estorno automático: "
                f"{node_input.reasoning}"
            ),
            severity=_escalation_severity(),
        )

    calc = await _compute_refundable(customer_id, month, item_ids)

    # `not_found`/`invalid` não têm valor somado, e `block_refund` está acima do
    # teto absoluto: nenhum deles pode virar portão de aprovação (aprovar seria
    # furar a política) — os três vão para um humano assumir.
    if calc["status"] in ("not_found", "invalid", "block_refund"):
        return _escalate_event(
            intent=EscalatorIntent.handoff,
            summary=(
                f"Refund não pôde ser processado automaticamente: {calc['reason']}"
            ),
            severity=_escalation_severity(
                calc_status=calc["status"], amount=calc.get("amount")
            ),
        )

    if calc["amount"] > REFUND_APPROVAL_THRESHOLD:
        return _escalate_event(
            intent=EscalatorIntent.refund_confirmation,
            summary=(
                f"Pedido de refund de S${calc['amount']:.2f} referente à fatura de {month} (linhas: {calc['skus']})."
            ),
            severity=_escalation_severity(amount=calc["amount"]),
            state_delta={
                "refund_amount": calc["amount"],
                "refund_month": month,
                "refund_skus": calc["skus"],
            },
        )

    auto_refund_request = AutoRefundRequest(
        refund_month=month,
        refund_amount=calc["amount"],
        refund_skus=calc["skus"],
    )

    return Event(actions=EventActions(route="auto_refund"), output=auto_refund_request)


@node
async def auto_refund_node(ctx: Context, node_input: AutoRefundRequest):
    ticket_id = ctx.state.get("ticket_id")
    ticket = await repo.get_ticket(ticket_id)

    if not ticket:
        # type: ignore
        return Event(message=f"Ticket {ticket_id} não encontrado.")

    await _billing.issue_refund(
        customer_id=ticket.customer_id,
        amount=node_input.refund_amount,
        reason=f"Refund aprovado pelo agente de suporte (ticket {ticket_id})",
    )

    ticket.response = (
        f"Olá! Seu pedido de reembolso foi aprovado e processado. "
        f"O valor de ${node_input.refund_amount:.2f} referente à fatura "
        f"de {node_input.refund_month} (linhas: {node_input.refund_skus}) "
        f"será creditado em sua conta em até 5 dias úteis."
    )

    ticket.status = TicketStatus.RESOLVED
    await repo.update_ticket(ticket)

    return Event(message=ticket.response)  # type: ignore


@node
async def triage_escalation_node(node_input: EscalatorOutput):
    """Depois da escalação: abre o portão de aprovação ou encerra em handoff.

    Só um `refund_confirmation` BEM-SUCEDIDO pode pausar — sem escalação criada
    não existe onde o humano decidir. Todo o resto (handoff, ou falha ao
    escalar) cai no nó terminal, que fecha o ticket com o status certo.
    """
    if (
        node_input.status != "failed"
        and node_input.intent == EscalatorIntent.refund_confirmation
    ):
        return Event(actions=EventActions(route="refund_await_input"))

    return Event(actions=EventActions(route="handoff"), output=node_input)


@node
async def finish_escalation_node(ticket_id: str, node_input: EscalatorOutput):
    """Terminal do handoff: o ticket sai do automático e vai para um humano."""
    ticket = await repo.get_ticket(ticket_id)

    if not ticket:
        # type: ignore
        return Event(message=f"Ticket {ticket_id} não encontrado.")

    if node_input.status == "failed":
        ticket.status = TicketStatus.FAILED
        ticket.error = node_input.detail
        message = (
            "Olá! Tivemos um problema técnico ao encaminhar seu caso e não foi "
            "possível concluí-lo automaticamente. A falha já está registrada e "
            "nossa equipe vai retomar o atendimento."
        )
    else:
        ticket.status = TicketStatus.ESCALATED
        message = (
            "Olá! Seu caso precisa de uma análise mais detalhada e foi encaminhado "
            "a um especialista da nossa equipe, que dará continuidade ao "
            "atendimento e retornará com uma posição."
        )

    ticket.response = message
    await repo.update_ticket(ticket)
    return Event(message=message)  # type: ignore


@node
async def await_refund_input_node(ticket_id: str):
    """PAUSA o grafo até um humano aprovar ou recusar o estorno.

    O `AWAITING_APPROVAL` é gravado aqui, junto da pausa: quem conhece o
    desfecho é o nó, não quem dispara o grafo. É um set idempotente — se o
    corpo do nó reexecutar num resume, o valor é o mesmo.
    """
    ticket = await repo.get_ticket(ticket_id)

    if not ticket:
        # type: ignore
        return Event(message=f"Ticket {ticket_id} não encontrado.")

    ticket.status = TicketStatus.AWAITING_APPROVAL
    await repo.update_ticket(ticket)

    return RequestInput(
        message=(
            "Aprovação humana necessária para o estorno. "
            "Responda com confirmed=true para aprovar ou confirmed=false para recusar."
        ),
        response_schema={
            "type": "object",
            "properties": {
                "confirmed": {"type": "boolean"}
            },
        }
    )


@node
async def refund_with_confirmation(node_input: dict, ctx: Context):
    ticket_id = ctx.state.get("ticket_id")
    ticket = await repo.get_ticket(ticket_id)

    if not ticket:
        # type: ignore
        return Event(message=f"Ticket {ticket_id} não encontrado.")

    confirmed = node_input.get("confirmed", False)

    if not confirmed:
        ticket.response = (
            "Olá! Seu pedido de reembolso foi analisado, mas infelizmente não foi aprovado. "
            "Se tiver dúvidas ou precisar de mais informações, entre em contato com nosso suporte."
        )
        ticket.status = TicketStatus.RESOLVED
        await repo.update_ticket(ticket)
        return Event(message=ticket.response)  # type: ignore

    refund_amount = ctx.state.get("refund_amount")
    refund_month = ctx.state.get("refund_month")
    refund_skus = ctx.state.get("refund_skus")

    # Se confirmado, processar o reembolso
    await _billing.issue_refund(
        customer_id=ticket.customer_id,
        amount=refund_amount,
        reason=f"Refund aprovado pelo agente de suporte (ticket {ticket_id})",
    )

    ticket.response = (
        f"Olá! Seu pedido de reembolso foi aprovado e processado. "
        f"O valor de ${refund_amount:.2f} referente à fatura "
        f"de {refund_month} (linhas: {refund_skus}) "
        f"será creditado em sua conta em até 5 dias úteis."
    )

    ticket.status = TicketStatus.RESOLVED
    await repo.update_ticket(ticket)

    return Event(message=ticket.response)  # type: ignore
