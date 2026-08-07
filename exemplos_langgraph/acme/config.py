"""Configuração: .env, modelos e os limiares da política de refund."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(RAIZ / ".env")

if not os.getenv("GOOGLE_API_KEY"):
    raise RuntimeError(
        f"GOOGLE_API_KEY não encontrada. Defina no .env da raiz ({RAIZ / '.env'})."
    )

MODELO_RAPIDO = "google_genai:gemini-3.1-flash-lite"
MODELO_PADRAO = "google_genai:gemini-3.5-flash"

# Mesmos limiares do projeto ADK (env.py). Acima do limiar exige aprovação
# humana; acima do teto o refund é bloqueado e vira handoff.
LIMIAR_APROVACAO = float(os.environ.get("REFUND_APPROVAL_THRESHOLD", "50"))
TETO_REFUND = float(os.environ.get("REFUND_MAX_LIMIT", "200"))


def checkpointer_padrao():
    """O checkpointer certo para o contexto em que o grafo está rodando.

    Rodando direto (`uv run python exemplos_langgraph/main.py`), o grafo precisa
    do seu próprio checkpointer — sem ele o `interrupt()` do nó de aprovação
    estoura.

    Rodando sob o Agent Server (`langgraph dev`), o servidor injeta a
    persistência e RECUSA carregar um grafo que traga a sua: não é aviso, é
    `GraphLoadError` e o servidor não sobe.

    Detecção por `sys.modules`: o `langgraph_api` já está importado quando o
    servidor carrega este módulo, e não está em nenhum outro caso.
    """
    import sys

    if "langgraph_api" in sys.modules:
        return None

    from langgraph.checkpoint.memory import InMemorySaver

    return InMemorySaver()
