"""1. Agente mínimo — equivale a `agents/meu_agente1`.

Diferença central em relação ao ADK: lá, `Agent(name="meu_agente1")` já era um
agente válido; o modelo tinha default e o nome era obrigatório.

No LangChain é o contrário: **`model` é o único parâmetro obrigatório** e o nome
é opcional. Não existe modelo default — a escolha do modelo é sempre explícita.
"""

from langchain.agents import create_agent

from exemplos_langchain.acme.config import MODELO_RAPIDO

agente = create_agent(model=MODELO_RAPIDO)
