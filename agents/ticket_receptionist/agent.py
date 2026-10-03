from multiprocessing import Value
from typing import Any, Optional

from google.adk.agents import Agent
try:
    from agents.model_config import modelo
except ModuleNotFoundError:  # adk web: 'agents/' está no sys.path, não a raiz
    from model_config import modelo
from google.adk.apps import App
from agents.ticket_receptionist.plugins import ModelRetryPlugin
from db.models import TicketModel, ClassificationModel
from google.adk.tools import ToolContext
from agents.ticket_receptionist.subagents.ticket_classifier.agent import (
    TicketClassifierOutput, ticket_classifier_subagent, CLASSIFIER_OUTPUT_KEY
)
from google.genai.types import Content
from db import repo
from google.adk.tools import BaseTool
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
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

    # raise Exception("erro de banco de dados")
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


# _RETRIABLE_LLM_ERRORS = ["MALFORMED_RESPONSE"]
# _MAX_RETRIES = 5

# # requests em voo, por invocação (as chamadas LLM de uma invocação são sequenciais)
# _pending_requests: dict[str, LlmRequest] = {}


# def capture_request_callback(
#     callback_context: CallbackContext, llm_request: LlmRequest
# ) -> Optional[LlmResponse]:
#     """before_model: guarda o request para um eventual retry no after_model."""
#     _pending_requests[callback_context.invocation_id] = llm_request
#     return None  # None = segue o fluxo normal

# def _is_empty_response(llm_response: LlmResponse) -> bool:
#     """Resposta 'terminou normal' mas sem nenhum conteúdo útil."""
#     if llm_response.partial:
#         return False  # chunk de streaming: vazio parcial é normal
#     if llm_response.error_code:
#         return False  # já coberto pelo caminho de erro
#     if llm_response.content and llm_response.content.parts:
#         for part in llm_response.content.parts:
#             if part.thought:
#                 continue  # pensamento sozinho não é resposta útil
#             if (part.text or part.function_call or part.function_response
#                     or part.inline_data or part.executable_code
#                     or part.code_execution_result):
#                 return False  # tem conteúdo real
#     return True


# _NUDGE = types.Content(
#     role="user",
#     parts=[
#         types.Part(text=(
#             "Sua resposta anterior não teve conteúdo."
#             "Por favor, tente novamente e forneça uma resposta clara."
#         ))
#     ],
# )


# async def retry_malformed_callback(
#     callback_context: CallbackContext, llm_response: LlmResponse
# ) -> Optional[LlmResponse]:
#     llm_request = _pending_requests.pop(callback_context.invocation_id, None)

#     code = getattr(llm_response.error_code, "name", llm_response.error_code)
#     if (code not in _RETRIABLE_LLM_ERRORS and not _is_empty_response(llm_response)) or llm_request is None:
#         return None

#     # cópia com o nudge anexado — request DIFERENTE do que falhou
#     retry_request = llm_request.model_copy(deep=True)
#     retry_request.contents = list(retry_request.contents or []) + [_NUDGE]

#     llm = callback_context._invocation_context.agent.canonical_model  # type: ignore

#     for attempt in range(1, _MAX_RETRIES + 1):
#         logger.warning("Resposta %s; retry %d/%d",
#                        code or "vazia", attempt, _MAX_RETRIES)
#         final_response = None
#         async for response in llm.generate_content_async(retry_request, stream=False):
#             final_response = response
#         if (final_response is not None
#                 and not final_response.error_code
#                 and not _is_empty_response(final_response)):
#             return final_response

#     # esgotou: degrada com elegância em vez de deixar o turno morrer vazio
#     return LlmResponse(
#         content=types.Content(
#             role="model",
#             parts=[
#                 types.Part(text=(
#                     "Tive um problema técnico ao concluir esta etapa. "
#                     "Pode reenviar sua mensagem, por favor?"
#                 ))
#             ],
#         )
#     )

# def cleanup_pending_requests_callback(callback_context: CallbackContext) -> None:
#     _pending_requests.pop(callback_context.invocation_id, None)

root_agent = Agent(
    name="ticket_receptionist",
    description="Responsável por receber tickets de suporte da Acme Cloud e classificá-los.",
    model=modelo(__file__),
    instruction=_INSTRUCTION_RECEPTIONIST,
    sub_agents=[
        ticket_classifier_subagent
    ],
    mode="chat",
    tools=[registrar_ticket],
    on_tool_error_callback=_handle_tool_error,
    # before_model_callback=capture_request_callback,
    # after_model_callback=retry_malformed_callback,
    # after_agent_callback=cleanup_pending_requests_callback,
)

app = App(
    root_agent=root_agent,
    name="ticket_receptionist",
    plugins=[ModelRetryPlugin()]
)
