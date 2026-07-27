from multiprocessing import Value
from typing import Any

from google.adk.agents import Agent
from google.adk.apps import App
from db.models import TicketModel, ClassificationModel
from google.adk.tools import ToolContext
from agents.ticket_receptionist.subagents.ticket_classifier.agent import (
    TicketClassifierOutput, ticket_classifier_subagent, CLASSIFIER_OUTPUT_KEY
)
from google.genai.types import Content
from db import repo
from google.adk.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

TICKET_CREATED_KEY = "temp:ticket_created"

def _mensagem_usuario(content: Content | None) -> str:
    if not content or not content.parts:
        return ""
    return "\n".join([part.text for part in content.parts if part.text])

# framework -> middleware -> service handleError
# controller|service

async def registrar_ticket(tool_context: ToolContext):
    """
    Registra um ticket de suporte na central de atendimento da Acme Cloud.
    Args:
        tool_context (ToolContext): Contexto da ferramenta, contendo informações do ticket.
    Returns:
        dict: Um dicionário contendo o status do registro do ticket.
    """

    if TICKET_CREATED_KEY in tool_context.state:
        return {"status": "error", "message": "O ticket já foi registrado. Não é possível registrar novamente."}

    if not CLASSIFIER_OUTPUT_KEY in tool_context.state:
        return {"status": "error", "message": "O ticket não foi classificado. Por favor, classifique o ticket antes de registrá-lo."}
    
    classification = TicketClassifierOutput.model_validate(
        tool_context.state[CLASSIFIER_OUTPUT_KEY])

    user_message = _mensagem_usuario(tool_context.user_content)

    #raise Exception("erro de banco de dados")
    if not user_message:
        raise ValueError(
            "A mensagem do usuário está vazia. Não é possível registrar o ticket.")

    ticket_created = await repo.create_ticket(
        TicketModel(
            customer_id=tool_context.user_id,
            message=user_message,
            classification=ClassificationModel(
                **classification.model_dump()
            )
        )
    )
    tool_context.state[TICKET_CREATED_KEY] = True

    return {"status": "success", "ticket_id": ticket_created.id}


# """
# - SOBRE A MENSAGEM DO USUÁRIO PARA CLASSIFICAÇÃO DO TICKET:
# Se você identificar que a mensagem do usuário é algo muito genérico, sem qualquer detalhe ou contexto,
# você deve solicitar mais informações ao usuário antes de prosseguir com a classificação do ticket.
# O usuário deve fornecer passos ou detalhes específicos de como, quando e onde o problema ocorreu,
# ou qualquer outra informação relevante que possa ajudar na classificação do ticket.
# """

_INSTRUCTION_RECEPTIONIST = """
Você é o Recepcionista de tickets da central de atendimento da Acme Cloud.
Se o usuário perguntar sobre algum ticket já registrado, pesquise o status do ticket e dê uma resposta adequada.
Se o usuário pedir para listar tickets, 
forneça uma lista dos tickets registrados de acordo com os critérios fornecidos (por exemplo, status, categoria, etc.).

Se o usuário pedir para criar um ticket, pergunte qual é a mensagem do ticket e, em seguida,
ative o processo de classificação do ticket e proceda com o registro do ticket.

"""


def _handle_tool_error(
        tool: BaseTool,
        args: dict[str, Any], tool_context: ToolContext, error: Exception) -> dict | None:
    logger.error("Erro ao executar a ferramenta %s: %s", tool.name, error)
    if isinstance(error, ValueError):
        return {"status": "error", "message": str(error)}
    return {
        "status": "error", 
        "message": "Ocorreu um erro inesperado ao processar sua solicitação."
    }


root_agent = Agent(
    name="ticket_receptionist",
    description="Responsável por receber tickets de suporte da Acme Cloud e classificá-los.",
    model="gemini-3.5-flash",
    instruction=_INSTRUCTION_RECEPTIONIST,
    sub_agents=[
        ticket_classifier_subagent
    ],
    mode="chat",
    tools=[registrar_ticket],
    on_tool_error_callback=_handle_tool_error,
)

app = App(
    root_agent=root_agent,
    name="ticket_receptionist",
)