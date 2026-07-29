from google.adk import Agent
from pydantic import BaseModel, Field
from mcp_clients.account_mcp import create_account_toolset


class AccountOperatorOutput(BaseModel):
    status: str = Field(
        description="Status da ação: 'added', 'already_member', 'invalid_email', 'error'.")
    message: str = Field(
        description="Mensagem de confirmação ou erro para o cliente.")

# state
_INSTRUCTION = """Você é o Operador de Conta da Acme Cloud. Você EXECUTA ações de
conta (adicionar membro à equipe, etc).

Mensagem do Ticket: {ticket_message}
Cliente ID: {customer_id}

# Retorno
{
    "status": <status>,
    "message": <message>
}

# Restrições:

Você SÓ pode declarar added/already_member/invalid_email 
após receber a resposta correspondente da tool MCP. 
Se a tool não estiver disponível na sua lista de ferramentas, 
ou se a chamada falhar, 
retorne status: 'error' informando que a ação não pôde ser executada e 
que o ticket será encaminhado. 
"""


account_operator_agent = Agent(
    name="account_operator",
    description=(
        "Especialista em ações de conta (adicionar membro à equipe, etc)."
    ),
    #mode="single_turn",
    model="gemini-3.5-flash",
    instruction=_INSTRUCTION,
    tools=[create_account_toolset()], #mcp
    output_schema=AccountOperatorOutput,
)
