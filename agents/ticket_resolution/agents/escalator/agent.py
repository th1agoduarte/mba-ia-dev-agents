from enum import Enum
from google.adk import Agent
from pydantic import BaseModel, Field
from agents.ticket_resolution.tools.ticket_escalation_tools import (
    create_ticket_escalation,
    get_ticket_escalation,
)
from mcp_clients.linear_mcp import create_linear_toolset


class EscalatorIntent(str, Enum):
    # refund aguardando aprovação humana
    refund_confirmation = "refund_confirmation"
    # resolver desistiu, humano assume
    handoff = "handoff"               


class EscalatorInput(BaseModel):
    intent: EscalatorIntent = Field(
        description="Qual o tipo de handoff: refund_confirmation ou handoff.")
    summary: str = Field(
        description="Por que escalar / o que o humano precisa saber.")
    severity: str = Field(
        default="medium", description="low | medium | high | urgent.")


class EscalatorOutput(BaseModel):
    status: str = Field(
        description="created | reused | failed para descrever o status da escalação.")
    detail: str = Field(default="", description="Resumo do que foi feito.")
    intent: EscalatorIntent = Field(
        description="Qual o tipo de handoff: refund_confirmation ou handoff.")

_INSTRUCTION = """Você é o Agente Escalonador da Acme Cloud.

Pedido recebido: intent, summary, severity (no input). 

Ticket ID: {ticket_id}.
Customer ID: {customer_id}.

# Passo 1 — não duplicar

Chame `get_ticket_escalation`. Se existir um registro, não crie outro, se o `external_ref` estiver presente, significa
que o registro existe também no Linear.
NÃO crie outro registro. Responda `status="reused"`.

# Passo 2 — criar (quando não existe)

a) Crie a issue no Linear.
    Componha um título e descrição CLAROS a partir do `intent` e `summary`, incluindo o
    `ticket_id` e o `customer_id`. Adapte ao intent:
    - `refund_confirmation`: deixe em DESTAQUE — "Para APROVAR, mova este issue para Done;
        para RECUSAR, mova para Canceled."
    - `handoff`: deixe claro que o caso precisa de um humano assumir manualmente.
        Defina a priority do issue conforme o `severity` do pedido: low, medium, high, urgent.

b) Chame `create_ticket_escalation` e use o `external_ref` como ID da issue no Linear.
        
# Passo 3 — responder

Responda um JSON válido com:
- `status` = `created` (ou `reused` se já existia) ou `failed` se houve erro.
- `detail` = curto descrevendo o que foi feito).
- `intent` = o mesmo do input.
"""


_tools = [get_ticket_escalation, create_ticket_escalation]
_linear = create_linear_toolset()
_tools.append(_linear)


escalator_agent = Agent(
    name="escalator",
    description=(
        "Cria o handoff humano de um ticket: checa duplicidade, formata e abre o "
        "issue no Linear "
        "(refund_confirmation = portão de aprovação do refund; "
        "handoff = caso para um humano assumir) "
        "e persiste a escalação"
    ),
    model="gemini-3.5-flash",
    instruction=_INSTRUCTION,
    tools=_tools,
    input_schema=EscalatorInput,
    output_schema=EscalatorOutput,
)
