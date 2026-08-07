"""Configuração compartilhada: carregamento do .env e escolha de modelo.

Importar este módulo já carrega o .env da raiz do projeto. Isso importa porque o
LangChain lê a credencial do ambiente (`GOOGLE_API_KEY`) na hora de construir o
modelo — sem ela, `create_agent(...)` estoura um ValidationError do pydantic
antes de qualquer chamada de rede.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# find_dotenv() sobe a partir do ARQUIVO que chama, não do diretório de trabalho.
# Apontar explicitamente para a raiz do repo evita depender de onde o exemplo rodou.
RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(RAIZ / ".env")

if not os.getenv("GOOGLE_API_KEY"):
    raise RuntimeError(
        f"GOOGLE_API_KEY não encontrada. Defina no .env da raiz ({RAIZ / '.env'})."
    )

# Os mesmos modelos usados pelos exemplos ADK em agents/, para comparação direta.
# O prefixo "google_genai:" diz ao init_chat_model qual provider instanciar; ele
# vem do pacote langchain-google-genai.
MODELO_RAPIDO = "google_genai:gemini-3.1-flash-lite"
MODELO_PADRAO = "google_genai:gemini-3.5-flash"


def checkpointer_padrao():
    """O checkpointer certo para o contexto em que o exemplo está rodando.

    Rodando direto (`uv run python -m ex_03_tools_hitl.main`), o agente precisa do
    seu próprio checkpointer — sem ele, `interrupt()` e memória de thread não
    funcionam.

    Rodando sob o Agent Server (`langgraph dev`), o servidor injeta a persistência
    e RECUSA carregar um grafo que traga a sua: não é aviso, é
    `GraphLoadError` e o servidor não sobe.

    A detecção é por `sys.modules`: o `langgraph_api` já está importado quando o
    servidor carrega o seu módulo, e não está em nenhum outro caso.
    """
    import sys

    if "langgraph_api" in sys.modules:
        return None

    from langgraph.checkpoint.memory import InMemorySaver

    return InMemorySaver()
