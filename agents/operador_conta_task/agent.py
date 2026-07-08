from google.adk import Agent
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.agent_tool import AgentTool

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



    # simulate a system error
    # return {"error": "DB Connection Error: Unable to fetch faturas from the database."}

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

def obter_status_acme() -> dict:
    """
        Obtém o status atual da empresa Acme.
        Returns:
            dict: Um dicionário contendo informações sobre o status da empresa Acme.
    """
    # randomly simulate a status check
    import random
    status = random.choice(["operacional", "manutencao", "intermitente"])
    return {"status": status, "mensagem": f"A empresa Acme está atualmente {status}."}

# O usuário precisa fornecer o ID do cliente para que você possa buscar as informações corretas.
consultor_faturas_subagent = Agent(
    name="consultor_faturas",
    description="Especialista em faturas, responsável por listar as faturas de um cliente específico.",
    instruction="""
        Você é um consultor de faturas da Acme.
        Você é responsável por:
         - Listar as faturas de um cliente específico.
    """,
    mode="task",
    model="gemini-3.5-flash",
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
    """,
    mode="task",
    model="gemini-3.5-flash",
    tools=[
        cancelar_assinatura
    ],
    disallow_transfer_to_peers=True,
    disallow_transfer_to_parent=True 
    # manter esta opçao neste subagent ajuda a evitar que o subagente use o `transfer_to_agent` 
    # para transferir a conversa para outro subagente, o que poderia causar confusão.
    # o subagente precisa usar `finish_task` para retornar o resultado para o coordenador.
)

acme_status_subagent = Agent(
    name="acme_status",
    description="Especialista identificar se os serviços da Acme estão operacionais, em manutenção ou intermitentes.",
    instruction="""
        Você é um agente de status da Acme.
        Você é responsável por fornecer informações sobre o status da empresa Acme.
    """,
    model="gemini-3.1-flash-lite",
    tools=[
        obter_status_acme
    ]
)

# agente coordenador
root_agent = Agent(
    name="operador_conta",
    description="Coordenador responsável por ajudar o cliente a gerenciar sua conta, incluindo faturas e assinaturas.",
    instruction="""
        Você é o atendente de conta interativo da Acme.
        Quando algum subagente retornar um erro de sistema, 
        use a tool `acme_status` para verificar se os serviços da Acme estão operacionais, em manutenção ou intermitentes.
        Caso os serviços estejam intermitentes ou em manutenção, informe ao usuário que 
        os serviços da Acme estão temporariamente indisponíveis e que ele deve tentar novamente mais tarde.
        Caso os serviços estejam operacionais, informe ao usuário que houve um erro de sistema e que ele deve tentar novamente mais tarde.
        O que são erros de sistema? 
        São erros que não são causados por bugs, erros de comunicação com sistemas externos, 
        como banco de dados, APIs de terceiros, etc. Esses erros podem ser temporários.
        Não informe ao usuário detalhes técnicos sobre o erro de sistema, apenas informe que houve um erro de sistema e que ele deve tentar novamente mais tarde.
        Seja cordial e direto.
    """,
    model="gemini-3.1-flash-lite",
    sub_agents=[
        consultor_faturas_subagent,
        consultor_assinaturas_subagent,
        # single_turn (tool)
    ],
    tools=[
        AgentTool(acme_status_subagent)
    ]
)

# transfer_to_agent = agente alvo detem o controle da conversa, ele pode conversar com o usuário


# chat           task                            single_turn
#                 pedir mais informações