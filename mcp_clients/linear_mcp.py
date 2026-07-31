import os
from typing import Any, List, Optional

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPServerParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

LINEAR_MCP_URL = os.environ.get("LINEAR_MCP_URL", "https://mcp.linear.app/mcp")

LINEAR_TOOLS = ["list_teams", "get_issue", "save_issue"]


def _sanitize_schema(node: Any) -> Any:
    """Traduz keywords de JSON Schema que o ADK/Gemini não digere.

    O caso concreto é o parâmetro `patch` do `save_issue`, que o Linear passou
    a expor em 30/07/2026: um array cujos itens são um `oneOf` de 6 operações,
    cada uma discriminada por `const`. Duas traduções são necessárias:

    - `const: X` -> `enum: [X]`: `const` não existe em `_ExtendedJSONSchema`
      (pydantic com `extra="forbid"`), então estoura a validação.
    - `oneOf` -> `anyOf`: o ADK aceita o campo `one_of` mas não o percorre
      (_gemini_schema_util.py, `# 'one_of', 'all_of', 'not' to come`) e o
      `Schema.from_json_schema` o descarta — o `items` do array sumiria e a
      API do Gemini responderia 400 `properties[patch].items: missing field`.
      Para uniões discriminadas (cada branch fixa um valor de `op` distinto)
      `anyOf` é equivalente na prática.

    Serve também de defesa contra novas mudanças: o servidor do Linear é
    remoto e pode alterar o contrato das tools sem release nosso.
    """
    if isinstance(node, list):
        return [_sanitize_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    sanitized: dict[str, Any] = {}
    for key, value in node.items():
        if key == "const":
            sanitized["enum"] = [value]
            sanitized.setdefault("type", "string" if isinstance(value, str) else "object")
        elif key == "oneOf":
            sanitized["anyOf"] = _sanitize_schema(value)
        else:
            sanitized[key] = _sanitize_schema(value)
    return sanitized


class SanitizedMcpToolset(McpToolset):
    """McpToolset que ajusta os schemas vindos do servidor antes de declará-los."""

    async def get_tools(
        self,
        readonly_context: Optional[ReadonlyContext] = None,
    ) -> List[BaseTool]:
        tools = await super().get_tools(readonly_context)
        for tool in tools:
            schema = getattr(getattr(tool, "_mcp_tool", None), "inputSchema", None)
            if not isinstance(schema, dict):
                continue
            properties = schema.get("properties") or {}
            schema["properties"] = {
                name: _sanitize_schema(value) for name, value in properties.items()
            }
        return tools


def create_linear_toolset() -> McpToolset:
    api_key = os.environ.get("LINEAR_API_KEY")
    if not api_key:
        raise ValueError("LINEAR_API_KEY não definido no ambiente.")
    return SanitizedMcpToolset(
        connection_params=StreamableHTTPServerParams(
            url=LINEAR_MCP_URL,
            headers={"Authorization": f"Bearer {api_key}"},
        ),
        tool_filter=LINEAR_TOOLS,
    )
