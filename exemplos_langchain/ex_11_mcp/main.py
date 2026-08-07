"""Conversa com o Linear via MCP.

    uv run python -m exemplos_langchain.ex_11_mcp.main
    uv run python -m exemplos_langchain.ex_11_mcp.main criar    # ABRE UM ISSUE DE VERDADE

Sem argumento, o exemplo é somente-leitura: lista as tools carregadas e pergunta
algo que só consulta. O modo `criar` escreve no Linear da sua conta — é efeito
externo real, por isso está atrás de um argumento explícito.
"""

from __future__ import annotations

import asyncio
import sys

from exemplos_langchain.ex_11_mcp.agente import carregar_tools, criar_agente


async def somente_leitura() -> None:
    tools = await carregar_tools()
    print("tools carregadas do MCP:", [t.name for t in tools])

    agente = await criar_agente()
    # `ainvoke`, não `invoke`: as tools de MCP são assíncronas.
    resultado = await agente.ainvoke(
        {"messages": [{"role": "user", "content": "Quais times existem no meu Linear?"}]}
    )
    print("\n[agente]", resultado["messages"][-1].text)


async def criar_issue() -> None:
    tools = await carregar_tools(permitir_escrita=True)
    print("tools carregadas do MCP:", [t.name for t in tools])

    agente = await criar_agente(permitir_escrita=True)
    pedido = (
        "Escale o ticket TICKET-0002 do cliente cliente_456. "
        "Motivo: pedido de estorno de $120,00 da fatura de 2024-02 (linha ADJ-991), "
        "acima do limiar de aprovação automática. Precisa de decisão humana."
    )
    resultado = await agente.ainvoke(
        {"messages": [{"role": "user", "content": pedido}]}
    )
    print("\n[agente]", resultado["messages"][-1].text)


def main() -> None:
    if "criar" in sys.argv:
        print("MODO ESCRITA: isto vai criar um issue real no seu Linear.\n")
        asyncio.run(criar_issue())
    else:
        asyncio.run(somente_leitura())


if __name__ == "__main__":
    main()
