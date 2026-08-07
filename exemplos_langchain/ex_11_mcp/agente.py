"""11. Tools de um servidor MCP — espelha o `escalator` de `agents/ticket_resolution`.

MCP (Model Context Protocol) padroniza como um servidor externo publica tools. No
ADK isso é um `McpToolset`; aqui é o pacote `langchain-mcp-adapters`, com o
`MultiServerMCPClient` — que, como o nome diz, fala com vários servidores de uma
vez e devolve todas as tools já no formato do LangChain.

## O que muda na execução

Este é o primeiro exemplo **assíncrono** da trilha, e não por estilo:

- carregar as tools é I/O de rede (`await client.get_tools()`), então o agente só
  pode ser montado dentro de uma corrotina — daí a fábrica `async def`;
- as tools de MCP são assíncronas, então a conversa precisa de `await
  agente.ainvoke(...)`. Chamar `.invoke()` síncrono falha na execução da tool.

Por isso aqui não existe `agente = create_agent(...)` no topo do módulo, como nos
outros dez exemplos.

## O saneamento de schema que NÃO foi preciso

O cliente do projeto ADK (`mcp_clients/linear_mcp.py`) carrega 40+ linhas de
`_sanitize_schema` traduzindo `const` → `enum` e `oneOf` → `anyOf`, porque esses
keywords de JSON Schema estouram a validação do ADK e são descartados pelo
conversor do Gemini.

Verificado: o `save_issue` do Linear continua expondo `const` e `oneOf`, e o
binding com Gemini pelo LangChain funciona sem tradução nenhuma — o
`langchain-google-genai` apenas ignora o que não suporta e segue. Um problema a
menos, mas note que é sorte de implementação, não garantia do protocolo.
"""

from __future__ import annotations

import os

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from exemplos_langchain.acme.config import MODELO_PADRAO

URL_LINEAR = os.environ.get("LINEAR_MCP_URL", "https://mcp.linear.app/mcp")

# O servidor do Linear expõe 52 tools. Mandar todas ao modelo é desperdício de
# contexto e convite a erro de escolha — o ADK filtra pelo mesmo motivo
# (`tool_filter`). Aqui o filtro é uma list comprehension.
TOOLS_LEITURA = ["list_teams", "get_issue"]
TOOLS_ESCRITA = ["save_issue"]


def criar_cliente() -> MultiServerMCPClient:
    """Monta o cliente MCP. Não conecta ainda — a conexão é por chamada de tool."""
    chave = os.environ.get("LINEAR_API_KEY")
    if not chave:
        raise RuntimeError("LINEAR_API_KEY não definida no .env da raiz.")
    return MultiServerMCPClient(
        {
            "linear": {
                "transport": "streamable_http",
                "url": URL_LINEAR,
                "headers": {"Authorization": f"Bearer {chave}"},
            }
        }
    )


async def carregar_tools(*, permitir_escrita: bool = False) -> list:
    """Busca as tools do servidor e devolve só as que interessam.

    `permitir_escrita=False` é o padrão de propósito: sem isso, uma alucinação do
    modelo vira um issue de verdade no Linear de alguém.
    """
    permitidas = set(TOOLS_LEITURA) | (set(TOOLS_ESCRITA) if permitir_escrita else set())
    todas = await criar_cliente().get_tools()
    return [t for t in todas if t.name in permitidas]


INSTRUCAO_LEITURA = """
    Você é o Escalonador da Acme Cloud e consulta o Linear pelo MCP.
    Responda de forma objetiva, usando as ferramentas disponíveis.
    Nunca invente identificadores: se precisar de um time ou de um issue, consulte.
"""

INSTRUCAO_ESCRITA = """
    Você é o Escalonador da Acme Cloud: abre o handoff humano no Linear.

    Para criar o issue:
    1. Descubra o time com `list_teams` — não invente o id.
    2. Chame `save_issue` com um título curto e uma descrição que inclua o
       `ticket_id`, o `customer_id` e o motivo da escalação.
       Para um portão de aprovação de estorno, deixe em DESTAQUE na descrição:
       "Para APROVAR, mova este issue para Done; para RECUSAR, mova para Canceled."

    Responda com o identificador do issue criado.
"""


async def criar_agente(*, permitir_escrita: bool = False):
    """Monta o agente com as tools do Linear já carregadas."""
    return create_agent(
        model=MODELO_PADRAO,
        system_prompt=INSTRUCAO_ESCRITA if permitir_escrita else INSTRUCAO_LEITURA,
        tools=await carregar_tools(permitir_escrita=permitir_escrita),
    )
