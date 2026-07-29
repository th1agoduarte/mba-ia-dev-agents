from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins import BasePlugin
from google.genai.types import Content
from google.genai import types
import logging

_RETRIABLE_LLM_ERRORS = ["MALFORMED_RESPONSE"]
_MAX_RETRIES = 5

_NUDGE = types.Content(
    role="user",
    parts=[
        types.Part(text=(
            "Sua resposta anterior não teve conteúdo."
            "Por favor, tente novamente e forneça uma resposta clara."
        ))
    ],
)

logger = logging.getLogger(__name__)


def _is_empty_response(llm_response: LlmResponse) -> bool:
    """Resposta 'terminou normal' mas sem nenhum conteúdo útil."""
    if llm_response.partial:
        return False  # chunk de streaming: vazio parcial é normal
    if llm_response.error_code:
        return False  # já coberto pelo caminho de erro
    if llm_response.content and llm_response.content.parts:
        for part in llm_response.content.parts:
            if part.thought:
                continue  # pensamento sozinho não é resposta útil
            if (part.text or part.function_call or part.function_response
                    or part.inline_data or part.executable_code
                    or part.code_execution_result):
                return False  # tem conteúdo real
    return True


class ModelRetryPlugin(BasePlugin):

    _pending_requests: dict[str, LlmRequest] = {}

    def __init__(self, name=None):
        self.name = name or "model_retry_plugin"

    async def before_model_callback(self, *, callback_context: CallbackContext, llm_request: LlmRequest) -> LlmResponse | None:
        """before_model: guarda o request para um eventual retry no after_model."""
        self._pending_requests[callback_context.invocation_id] = llm_request
        return None  # None = segue o fluxo normal

    async def after_model_callback(self, *, callback_context: CallbackContext, llm_response: LlmResponse) -> LlmResponse | None:
        llm_request = self._pending_requests.pop(
            callback_context.invocation_id, None)

        code = getattr(llm_response.error_code,
                       "name", llm_response.error_code)
        if (code not in _RETRIABLE_LLM_ERRORS and not _is_empty_response(llm_response)) or llm_request is None:
            return None

            # cópia com o nudge anexado — request DIFERENTE do que falhou
        retry_request = llm_request.model_copy(deep=True)
        retry_request.contents = list(
            retry_request.contents or []) + [_NUDGE]

        llm = callback_context._invocation_context.agent.canonical_model  # type: ignore

        for attempt in range(1, _MAX_RETRIES + 1):
            logger.warning("Resposta %s; retry %d/%d",
                           code or "vazia", attempt, _MAX_RETRIES)
            final_response = None
            async for response in llm.generate_content_async(retry_request, stream=False):
                final_response = response
            if (final_response is not None
                    and not final_response.error_code
                    and not _is_empty_response(final_response)):
                return final_response

        # esgotou: degrada com elegância em vez de deixar o turno morrer vazio
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(text=(
                        "Tive um problema técnico ao concluir esta etapa. "
                        "Pode reenviar sua mensagem, por favor?"
                    ))
                ],
            )
        )

    async def after_agent_callback(self, *, agent: BaseAgent, callback_context: CallbackContext) -> Content | None:
        self._pending_requests.pop(callback_context.invocation_id, None)
