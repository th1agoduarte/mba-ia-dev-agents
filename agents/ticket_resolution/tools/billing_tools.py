from outside import mock_billing_server as _billing




async def find_invoices(customer_id: str) -> dict:
    """
        Lista as faturas do cliente do ticket para o agente avaliar o refund.
        Args:
            tool_context (ToolContext): O contexto da ferramenta, contendo o estado do ticket.
        Returns:
            dict: Um dicionário contendo a lista de faturas do cliente sob a chave "invoices".
    """
    return {"invoices": await _billing.list_invoices(customer_id)}
