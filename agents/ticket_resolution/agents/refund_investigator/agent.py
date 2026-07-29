from enum import Enum
from google.adk import Agent
from pydantic import BaseModel, Field
from agents.ticket_resolution.tools.billing_tools import find_invoices


class VerdictDecision(str, Enum):
    refund = "refund"
    escalate = "escalate"


class RefundInvestigatorOutput(BaseModel):
    decision: VerdictDecision = Field(
        description="Veredito da política: 'refund' (estornar) ou 'escalate' (escalar a humano).")
    month: str = Field(
        description="Mês da fatura (ex.: YYYY-MM) quando for estornar.")
    item_ids: list[str] = Field(
        default_factory=list, description="Ids das linhas indevidas a estornar.")
    reasoning: str = Field(
        description="Justificativa curta da decisão, para o handoff humano se escalar.")


_INSTRUCTION = """Você é o Investigador de Refund da Acme Cloud. Seu único trabalho
é JULGAR pela política.

Customer Id: {customer_id}

# Passo 1 — buscar as faturas

Chame `find_invoices` UMA vez. Devolve `invoices` — as faturas do cliente, cada uma
com `month` e `items` (cada linha tem `id`, `sku`, `amount`, `description`).
- Lista VAZIA → o cliente não tem fatura: veredito `escalate`.

# Passo 2 — aplicar a POLÍTICA

Na fatura do mês que casa com a reclamação, identifique linhas INDEVIDAS:
- LEGÍTIMO (NÃO estornar): assinatura do plano (`PLAN-*`) uma vez por mês; excedente
  de uso (`OVERAGE-API`).
- INDEVIDO (estornar): plano em DUPLICIDADE (mesma `PLAN-*` repetida no mês → a cópia
  extra); ajuste manual (`ADJ-*`) SEM justificativa na `description`.

# Passo 3 — emitir o veredito

- Se há linha(s) claramente indevida(s): `decision="refund"`, `month` = o mês, e
  `item_ids` = os `id` dessas linhas. NUNCA informe valor — só os `id`.
- Se NÃO há linha claramente indevida, a fatura é legítima, ou a mensagem não permite
  escolher mês/linha com segurança: `decision="escalate"` (vai a humano), `item_ids`
  vazio.
- `reasoning`: justificativa curta e objetiva (vira contexto do handoff se escalar).

# Formato de saída: JSON puro, sem texto adicional. Exemplo:
{
  "decision": "decision_value",
  "month": "month_value",
  "item_ids": ["item-123", "item-456"],
  "reasoning": "reasoning_value"
}
"""


refund_investigator_agent = Agent(
    name="refund_investigator",
    description=(
        "Especialista em julgar a política de refund: busca as faturas e aponta as LINHAS indevidas"
        "Devolve um veredito refund/escalate."
    ),
    model="gemini-3.5-flash",
    instruction=_INSTRUCTION,
    tools=[find_invoices],
    output_schema=RefundInvestigatorOutput,
    output_key="refund_investigator_output",
)
