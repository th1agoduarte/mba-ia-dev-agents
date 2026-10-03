"""Seleção de modelo por agente + provider (Gemini x Anthropic).

Tudo fica no `.env` da RAIZ. Cada agente tem a sua própria variável de modelo,
derivada do nome da pasta: `agents/meu_agente1/` -> `MEU_AGENTE1_MODEL`. Se a
variável do agente estiver vazia/ausente, usa a variável `DEFAULT_MODEL` (valor
padrão sem custo). Em seguida, `MODEL_PROVIDER` decide Gemini ou Anthropic.

    # .env da raiz
    MODEL_PROVIDER=gemini | anthropic      # provider de todos
    DEFAULT_MODEL=gemini-3.5-flash-lite    # usado por quem não tem variável própria
    MEU_AGENTE1_MODEL=                      # vazio -> cai no DEFAULT_MODEL
    OPERADOR_CONTA_MODEL=gemini-3.5-flash   # override só deste agente

No código, cada agente chama `modelo(__file__)`.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# O .env da raiz tem provider, chaves e as variáveis de modelo por agente.
RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

# gemini | anthropic
PROVIDER = os.getenv("MODEL_PROVIDER", "gemini").strip().lower()

# Variável com o valor padrão (sem custo). Se nem ela existir, cai neste literal.
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-3.5-flash-lite").strip()

# Mapeia cada modelo Gemini para um equivalente Anthropic (usado só quando
# MODEL_PROVIDER=anthropic). Nomes não mapeados caem no default abaixo.
_ANTHROPIC_SONNET = "anthropic/claude-sonnet-5"
_ANTHROPIC_HAIKU = "anthropic/claude-haiku-4-5"
_ANTHROPIC_EQUIVALENTES = {
    "gemini-3.5-flash": _ANTHROPIC_SONNET,
    "gemini-3.5-flash-lite": _ANTHROPIC_HAIKU,
    "gemini-3.1-flash-lite": _ANTHROPIC_HAIKU,
}
_ANTHROPIC_DEFAULT = _ANTHROPIC_HAIKU


def _chave_do_agente(agent_file: str) -> str:
    """Nome da pasta do agente -> variável de ambiente. Ex.: MEU_AGENTE1_MODEL."""
    return Path(agent_file).resolve().parent.name.upper() + "_MODEL"


def _modelo_gemini(agent_file: str | None) -> str:
    """Modelo do agente: a variável própria do agente ou o DEFAULT_MODEL."""
    if agent_file:
        valor = os.getenv(_chave_do_agente(agent_file))
        if valor and valor.strip():
            return valor.strip()
    return DEFAULT_MODEL


def modelo(agent_file: str | None = None):
    """Modelo do agente para o provider ativo.

    Passe `__file__`: a variável do agente (ex.: `MEU_AGENTE1_MODEL`) é lida do
    `.env` da raiz; vazia/ausente -> `DEFAULT_MODEL`.

    - gemini: devolve a string do modelo.
    - anthropic: devolve um `LiteLlm` com o Claude equivalente.
    """
    gemini_model = _modelo_gemini(agent_file)

    if PROVIDER == "gemini":
        return gemini_model

    if PROVIDER == "anthropic":
        from google.adk.models.lite_llm import LiteLlm

        return LiteLlm(
            model=_ANTHROPIC_EQUIVALENTES.get(gemini_model, _ANTHROPIC_DEFAULT)
        )

    raise ValueError(
        f"MODEL_PROVIDER inválido: {PROVIDER!r}. Use 'gemini' ou 'anthropic'."
    )
