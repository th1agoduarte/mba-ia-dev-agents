from google.adk import Agent

FATURAS = [
    {
        "id": "fatura_001",
        "cliente_id": "cliente_123",
        "valor": 49.99,
        "data_emissao": "2024-01-01",
        "data_vencimento": "2024-01-15",
        "status": "paga",
    },
    {
        "id": "fatura_002",
        "cliente_id": "cliente_123",
        "valor": 49.99,
        "data_emissao": "2024-02-01",
        "data_vencimento": "2024-02-15",
        "status": "pendente",
    },
]

# serialização


def listar_faturas(cliente_id: str):
    """
        Lista as faturas de um cliente específico.
        Args:
            cliente_id (str): O ID do cliente para o qual as faturas devem ser listadas.
        Returns:
            dict: Um dicionário contendo a lista de faturas do cliente.
    """

    return {
        "faturas": [fatura for fatura in FATURAS if fatura["cliente_id"] == cliente_id],
    }


root_agent = Agent(
    name="operador_conta",
    instruction="""
        Você é o atendente de conta interativo da Acme.
        Você é responsável por:
         - Informar ao cliente sobre sua assinatura: o plano, status e renovação.
         - Tirar dúvidas sobre as faturas do cliente.
         - Cancelar a assinatura do cliente, se solicitado.
        O usuário precisa fornecer o ID do cliente para que você possa buscar as informações corretas.
        Seja cordial e direto.
    """,
    model="gemini-3.1-flash-lite",
    tools=[listar_faturas]
)
