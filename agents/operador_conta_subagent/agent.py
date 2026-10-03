from google.adk import Agent
try:
    from agents.model_config import modelo
except ModuleNotFoundError:  # adk web: 'agents/' está no sys.path, não a raiz
    from model_config import modelo
from google.adk.tools.tool_context import ToolContext

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

def listar_faturas(cliente_id: str) -> dict:
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


ASSINATURAS: dict[str, dict] = {
    "cliente_123": {"plano": "Pro", "status": "ativa", "renovacao": "2026-07-01"},
}


def cancelar_assinatura(cliente_id: str, senha: str, tool_context: ToolContext) -> dict:
    """
        Cancela a assinatura de um cliente específico.
        Args:
            cliente_id (str): O ID do cliente para o qual a assinatura deve ser cancelada.
            senha (str): A senha fornecida pelo cliente para autenticação.
        Returns:
            dict: Um dicionário contendo o status da operação de cancelamento.
    """

    if tool_context.tool_confirmation is None:
        tool_context.request_confirmation(
            hint="O valor da assinatura é alto. Tem certeza que deseja cancelar?",
            payload={
                "cliente_id": cliente_id,
                "senha": ""
            }
        )
        return {"status": "aguardando_confirmacao"}

    if not tool_context.tool_confirmation.confirmed:
        return {"status": "nao_cancelada", "mensagem": "Cancelamento não confirmado pelo usuário."}

    if senha != "senha_secreta":
        return {"status": "nao_cancelada", "mensagem": "Senha incorreta. Cancelamento não autorizado."}

    assinatura = ASSINATURAS.get(cliente_id)
    if assinatura is not None:
        assinatura["status"] = "cancelada"
    return {"status": "cancelada", "cliente_id": cliente_id}


# O usuário precisa fornecer o ID do cliente para que você possa buscar as informações corretas.
consultor_faturas_subagent = Agent(
    name="consultor_faturas",
    description="Especialista em faturas, responsável por listar as faturas de um cliente específico.",
    instruction="""
        Você é um consultor de faturas da Acme.
        Você é responsável por:
         - Listar as faturas de um cliente específico.
         Seja cordial e direto.
    """,
    model=modelo(__file__),
    tools=[
        listar_faturas
    ],
    disallow_transfer_to_peers=True,
    disallow_transfer_to_parent=True 
    # impedir que o subagente seja transferido para o agente pai
    # obrigar a transferência para root_agent no próximo turno
)

consultor_assinaturas_subagent = Agent(
    name="consultor_assinaturas",
    description="Especialista em assinaturas, responsável por informar ao cliente sobre sua assinatura",
    instruction="""
        Você é um consultor de assinaturas da Acme.
        Você é responsável por:
         - Informar ao cliente sobre sua assinatura: o plano, status e renovação.
        Seja cordial e direto.
    """,
    model=modelo(__file__),
    tools=[
        cancelar_assinatura
    ],
    disallow_transfer_to_peers=True
)

# agente coordenador
root_agent = Agent(
    name="operador_conta",
    description="Coordenador responsável por ajudar o cliente a gerenciar sua conta, incluindo faturas e assinaturas.",
    instruction="""
        Você é o atendente de conta interativo da Acme.
        Seja cordial e direto.
    """,
    model=modelo(__file__),
    sub_agents=[
        consultor_faturas_subagent,
        consultor_assinaturas_subagent
    ]
)

# transfer_to_agent = agente alvo detem o controle da conversa, ele pode conversar com o usuário