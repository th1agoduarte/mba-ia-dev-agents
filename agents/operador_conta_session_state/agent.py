from google.adk import Agent
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.agent_tool import AgentTool
from pydantic import BaseModel, Field

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
    {
        "id": "fatura_003",
        "cliente_id": "cliente_456",
        "valor": 29.99,
        "data_emissao": "2024-01-10",
        "data_vencimento": "2024-01-25",
        "status": "paga",
    },
    {
        "id": "fatura_004",
        "cliente_id": "cliente_456",
        "valor": 29.99,
        "data_emissao": "2024-02-10",
        "data_vencimento": "2024-02-25",
        "status": "pendente",
    },
]


def listar_faturas(tool_context: ToolContext) -> dict:
    """
        Lista as faturas de um cliente específico.
        Returns:
            dict: Um dicionário contendo a lista de faturas do cliente.
    """

    cliente_id = tool_context.state.get("cliente_id")

    # simulate a system error
    # return {"error": "DB Connection Error: Unable to fetch faturas from the database."}

    return {
        "faturas": [fatura for fatura in FATURAS if fatura["cliente_id"] == cliente_id],
    }


ASSINATURAS: dict[str, dict] = {
    "cliente_123": {"plano": "Pro", "status": "ativa", "renovacao": "2026-07-01"},
    "cliente_456": {"plano": "Basic", "status": "ativa", "renovacao": "2025-12-15"},
}


def cancelar_assinatura(senha: str, tool_context: ToolContext) -> dict:
    """
        Cancela a assinatura de um cliente específico.
        Args:
            senha (str): A senha fornecida pelo cliente para autenticação.
        Returns:
            dict: Um dicionário contendo o status da operação de cancelamento.
    """

    cliente_id = tool_context.state.get("cliente_id")

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

class ConsultarFaturasOutput(BaseModel):
    faturas: list[dict] = Field(description="Lista de faturas do cliente.")

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
    output_schema=ConsultarFaturasOutput
)

consultor_assinaturas_subagent = Agent(
    name="consultor_assinaturas",
    description="Especialista em assinaturas, responsável por informar ao cliente sobre sua assinatura",
    instruction="""
        Você é um consultor de assinaturas da Acme.
        Você é responsável por:
         - Informar ao cliente sobre sua assinatura: o plano, status e renovação.
        Antes de proceder com um cancelamento de assinatura, se o usuário respondeu a pesquisa de satisfação e tem
        um sentimento negativo, você deve oferecer um desconto de 20% na próxima renovação da assinatura.
        Reposta da pesquisa: {pesquisa_satisfacao_resultado?}
    """,
    mode="task",
    model="gemini-3.5-flash",
    tools=[
        cancelar_assinatura
    ],
    disallow_transfer_to_peers=True,
    disallow_transfer_to_parent=True
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


def ja_respondeu_pesquisa(tool_context: ToolContext) -> bool:
    """
        Verifica se o cliente já respondeu à pesquisa de satisfação nos últimos 3 meses.
        Args:
            tool_context (ToolContext): O contexto da ferramenta contendo o estado da sessão.
        Returns:
            bool: True se o cliente já respondeu à pesquisa, False caso contrário.
    """
    # Simulação: apenas o cliente_123 respondeu à pesquisa nos últimos 3 meses
    return tool_context.state.get("cliente_id") == "cliente_123"


def registrar_pesquisa(tool_context: ToolContext, feedback: str, sentimento: str) -> dict:
    """
        Registra a resposta do cliente à pesquisa de satisfação.
        Args:
            tool_context (ToolContext): O contexto da ferramenta contendo o estado da sessão.
            feedback (str): O feedback fornecido pelo cliente.
            sentimento (str): O sentimento do cliente em relação aos serviços da Acme (positivo, neutro ou negativo).
        Returns:
            dict: Um dicionário confirmando o registro da pesquisa.
    """

    tool_context.state["pesquisa_satisfacao_resultado"] = {
        "feedback": feedback,
        "sentimento": sentimento
    }

    # db

    # Simulação: registra a pesquisa e retorna uma confirmação
    return {
        "status": "registrada",
    }

class PesquisaSatisfacaoOutput(BaseModel):
    feedback: str = Field(description="O que o cliente está achando dos serviços da Acme.")
    sentimento: str = Field(description="O sentimento do cliente em relação aos serviços da Acme (positivo, neutro ou negativo).")

pesquisa_satisfacao_subagent = Agent(
    name="pesquisa_satisfacao",
    description="Agente responsável por conduzir uma pesquisa de satisfação com o cliente.",
    instruction="""
        Você é um agente de pesquisa de satisfação da Acme.
        Você é responsável por conduzir uma pesquisa de satisfação com o cliente.
        Pergunte ao cliente sobre sua experiência com os serviços da Acme.
        Sua resposta deve ser neste formato:
            - feedback: O que o cliente está achando dos serviços da Acme.
            - sentimento: O sentimento do cliente em relação aos serviços da Acme (positivo, neutro ou negativo).
        Depois de terminar a pesquisa, registre a resposta do cliente usando a ferramenta `registrar_pesquisa`.
        Após proceda com `finish_task` para transferir a conversa de volta para o agente pai.
    """,
    model="gemini-3.5-flash",
    mode="task",
    disallow_transfer_to_peers=True,
    tools=[
        registrar_pesquisa
    ],
    output_schema=PesquisaSatisfacaoOutput,
    #output_key="pesquisa_satisfacao_resultado",
)
# Quanto terminar, transfira a conversa de volta para o agente pai. vs finish_task
# chat 
# agente coordenador
root_agent = Agent(
    name="operador_conta",
    description="Coordenador responsável por ajudar o cliente a gerenciar sua conta, incluindo faturas e assinaturas.",
    instruction="""
        Você é o atendente de conta interativo da Acme.

        Antes de responder a qualquer pergunta do cliente, você deve verificar se o cliente já respondeu a pesquisa de satisfação.
        Se não, você deve conduzir a pesquisa de satisfação com o cliente usando o subagente `pesquisa_satisfacao` antes de prosseguir com qualquer outra interação.
        
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
        pesquisa_satisfacao_subagent,
    ],
    tools=[
        AgentTool(acme_status_subagent),
        ja_respondeu_pesquisa
    ],
    output_key="operador_conta_resultado"
)
