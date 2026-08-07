"""Ferramentas da Acme.

Repare no que NÃO tem aqui: nenhuma tool pede confirmação. No ADK o
`cancelar_assinatura` chamava `tool_context.request_confirmation(...)` por dentro;
no LangChain a aprovação humana é responsabilidade do `HumanInTheLoopMiddleware`,
que intercepta a tool call antes de executar. A tool volta a ser só a ação.

O que o LLM enxerga de cada tool é o NOME, a assinatura e a DOCSTRING — é a
docstring que faz o papel da `description`. Escreva-a pensando no modelo.
"""

from __future__ import annotations

from langchain.tools import tool

from exemplos_langchain.acme import dados


@tool
def listar_faturas(cliente_id: str) -> dict:
    """Lista as faturas de um cliente.

    Args:
        cliente_id: identificador do cliente, por exemplo "cliente_123".
    """
    return {"faturas": dados.buscar_faturas(cliente_id)}


@tool
def consultar_assinatura(cliente_id: str) -> dict:
    """Consulta o plano, o status e a data de renovação da assinatura de um cliente.

    Args:
        cliente_id: identificador do cliente, por exemplo "cliente_123".
    """
    assinatura = dados.buscar_assinatura(cliente_id)
    if assinatura is None:
        return {"erro": "cliente não encontrado"}
    return assinatura


@tool
def cancelar_assinatura(cliente_id: str, senha: str) -> dict:
    """Cancela a assinatura de um cliente.

    Args:
        cliente_id: identificador do cliente, por exemplo "cliente_123".
        senha: senha fornecida pelo cliente para autenticação.
    """
    if senha != dados.SENHA_VALIDA:
        return {"status": "nao_cancelada", "motivo": "senha incorreta"}
    if not dados.cancelar(cliente_id):
        return {"status": "nao_cancelada", "motivo": "cliente não encontrado"}
    return {"status": "cancelada", "cliente_id": cliente_id}


@tool
def listar_faturas_com_erro(cliente_id: str) -> dict:
    """Lista as faturas de um cliente.

    Args:
        cliente_id: identificador do cliente, por exemplo "cliente_123".
    """
    # Falha proposital: os exemplos de composição usam isto para exercitar o
    # caminho "consulte o status da plataforma antes de culpar o sistema".
    return {"error": "DB Connection Error: Unable to fetch faturas from the database."}


@tool
def obter_status_acme() -> dict:
    """Informa se os serviços da Acme estão operacionais, em manutenção ou intermitentes."""
    status = dados.status_plataforma()
    return {"status": status, "mensagem": f"A plataforma Acme está {status}."}
