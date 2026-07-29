from google.adk import Agent
from google.adk.tools import AgentTool
from pydantic import BaseModel, Field
from agents.ticket_resolution.agents.account_operator.agent import account_operator_agent
from agents.ticket_resolution.tools.platform_status_tool import platform_status


class AttendantOutput(BaseModel):
    status: str = Field(description="Status da ação: 'success' | 'error'.")
    message: str = Field(description="Mensagem final para o cliente.")

_INSTRUCTION = """Você é o Atendente da central da Acme Cloud — a linha de frente do
atendimento geral (bug, dúvida, onboarding, configuração).

Mensagem do Ticket: {ticket_message}
Contexto da triagem: {classification_justification}

Ações a serem desempenhas:

1 - AÇÃO DE CONTA

Se o cliente PEDE EXPLICITAMENTE uma ação de conta que o sistema executa:
ADICIONAR UM MEMBRO à equipe — chame o subagent `account_operator`.

Exemplos de pedido de ação de conta:
- "adicionem fulano@x.com à equipe" → é PEDIDO de ação → transfira.
- "COMO adiciono um membro?" → é dúvida how-to → NÃO transfira, responda você (opção 3).

2 - ATENDIMENTO GERAL

Se o cliente NÃO pede ação de conta, use o restante do seu conhecimento para resolver o problema

FORMATO DE SAÍDA: JSON com os campos `status` e `message`.
A mensagem deve ser cordial e educado, 
deve dar detalhes do que foi feito, e deve ser clara sobre o próximo passo (se houver).
"""


attendant_agent = Agent(
    name="attendant",
    description=(
        "Atendente de atendimento geral: resolve dúvidas/problemas,"
        "verifica de status da plataforma e realiza operações de conta"
    ),
    model="gemini-3.5-flash",
    instruction=_INSTRUCTION,
    tools=[platform_status, AgentTool(account_operator_agent)], #http
    #sub_agents=[account_operator_agent],
    output_key="attendant_output",
    output_schema=AttendantOutput,
)
