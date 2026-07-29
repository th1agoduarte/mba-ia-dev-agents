import os
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPServerParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

_HOST = os.environ.get("ACCOUNT_MCP_HOST")
_PORT = int(os.environ.get("ACCOUNT_MCP_PORT")) #type: ignore
ACCOUNT_MCP_URL = f"http://{_HOST}:{_PORT}/mcp"


def create_account_toolset() -> McpToolset:
    """Toolset MCP do sistema de conta (servidor PRÓPRIO, streamable-http).
    """
    return McpToolset(
        connection_params=StreamableHTTPServerParams(url=ACCOUNT_MCP_URL),
        # Em produção, restrinja com tool_filter=[...] às ações permitidas.
    )
