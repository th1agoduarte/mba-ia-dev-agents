"""Os agentes que ocupam nós do grafo.

Um agente é um grafo. Colocar um `create_agent` dentro de um `StateGraph` maior é
o mesmo que aninhar subgrafos — e é o que o ADK faz ao aceitar um `Agent` como nó
de um `Workflow`.

Todos usam `response_format`: o grafo em volta precisa de dado com forma para
rotear, não de prosa. É o `output_schema` do ADK.
"""

from __future__ import annotations

from enum import Enum

from langchain.agents import create_agent
from langchain.tools import tool
from pydantic import BaseModel, Field

from exemplos_langgraph.acme import dominio
from exemplos_langgraph.acme.config import MODELO_PADRAO


# --- atendente ---------------------------------------------------------------


class SaidaAtendente(BaseModel):
    status: str = Field(description="'success' ou 'error'.")
    mensagem: str = Field(description="Mensagem final para o cliente, cordial e clara.")


@tool
def status_plataforma() -> dict:
    """Status atual dos serviços da Acme e incidentes em aberto.

    Use para verificar se o problema do cliente tem um incidente correlacionado.
    """
    return {
        "servicos": {"board": "operacional", "api": "operacional"},
        "incidentes_abertos": [],
    }


@tool
def adicionar_membro(email: str) -> dict:
    """Adiciona um membro à equipe do cliente.

    Args:
        email: e-mail do membro a adicionar.
    """
    return {"status": "adicionado", "email": email}


atendente = create_agent(
    model=MODELO_PADRAO,
    system_prompt="""
        Você é o Atendente da central da Acme Cloud, a linha de frente do
        atendimento geral: bug, dúvida, onboarding e configuração.

        Se o cliente PEDE explicitamente para adicionar um membro à equipe, use
        `adicionar_membro`. Uma pergunta de "como faço para..." é dúvida: explique,
        não execute.
        Se o cliente relata algo quebrado, verifique `status_plataforma` antes de
        responder.

        Responda de forma cordial, dizendo o que foi feito e qual o próximo passo.
    """,
    tools=[status_plataforma, adicionar_membro],
    response_format=SaidaAtendente,
)


# --- investigador de refund --------------------------------------------------


class Veredito(str, Enum):
    refund = "refund"
    escalate = "escalate"


class SaidaInvestigador(BaseModel):
    decisao: Veredito = Field(description="'refund' para estornar, 'escalate' para humano.")
    mes: str = Field(default="", description="Mês da fatura no formato YYYY-MM.")
    linhas: list[str] = Field(
        default_factory=list, description="Ids das linhas indevidas a estornar."
    )
    raciocinio: str = Field(description="Justificativa curta da decisão.")


@tool
def buscar_faturas(cliente_id: str) -> dict:
    """Lista as faturas do cliente, com as linhas de cada uma.

    Args:
        cliente_id: identificador do cliente do ticket.
    """
    return {"faturas": dominio.listar_faturas(cliente_id)}


investigador = create_agent(
    model=MODELO_PADRAO,
    system_prompt="""
        Você é o Investigador de Refund da Acme Cloud. Seu único trabalho é
        JULGAR pela política — você NUNCA calcula nem informa valores.

        Passo 1: chame `buscar_faturas` uma vez com o id do cliente.
        Lista vazia significa que não há fatura: decida `escalate`.

        Passo 2: na fatura do mês que casa com a reclamação, identifique as
        linhas INDEVIDAS.
        - LEGÍTIMO, não estornar: a assinatura do plano (`PLAN-*`) uma vez no mês;
          excedente de uso (`OVERAGE-API`).
        - INDEVIDO, estornar: plano em DUPLICIDADE (a mesma `PLAN-*` repetida no
          mesmo mês, a cópia extra); ajuste manual (`ADJ-*`) sem justificativa
          real na descrição.

        Passo 3: emita o veredito.
        - Havendo linha claramente indevida: `decisao="refund"`, `mes` com o mês e
          `linhas` com os ids dessas linhas. Só os ids, jamais o valor.
        - Não havendo, ou se a mensagem não permite escolher mês e linha com
          segurança: `decisao="escalate"` e `linhas` vazio.
    """,
    tools=[buscar_faturas],
    response_format=SaidaInvestigador,
)


# --- escalonador -------------------------------------------------------------


class SaidaEscalonador(BaseModel):
    status: str = Field(description="'criado', 'reaproveitado' ou 'falhou'.")
    detalhe: str = Field(default="", description="Resumo curto do que foi feito.")
    referencia: str = Field(default="", description="Identificador externo do card.")


@tool
def consultar_escalacao(ticket_id: str) -> dict:
    """Verifica se já existe uma escalação aberta para o ticket.

    Args:
        ticket_id: identificador do ticket.
    """
    return dominio.buscar_escalacao(ticket_id) or {"encontrado": False}


@tool
def abrir_escalacao(ticket_id: str, resumo: str, severidade: str, intencao: str) -> dict:
    """Abre o card de handoff humano para o ticket.

    Args:
        ticket_id: identificador do ticket.
        resumo: o que o humano precisa saber para decidir.
        severidade: low, medium, high ou urgent.
        intencao: 'aprovacao_refund' ou 'handoff'.
    """
    return dominio.criar_escalacao(ticket_id, resumo, severidade, intencao)


escalonador = create_agent(
    model=MODELO_PADRAO,
    system_prompt="""
        Você é o Escalonador da Acme Cloud: cria o handoff para um humano.

        Passo 1: chame `consultar_escalacao`. Se já existir registro, NÃO crie
        outro e responda `status="reaproveitado"`.
        Passo 2: se não existir, chame `abrir_escalacao` com um resumo claro,
        a severidade e a intenção que você recebeu.
        Passo 3: responda com o status, um detalhe curto e a referência externa
        devolvida pela ferramenta.
    """,
    tools=[consultar_escalacao, abrir_escalacao],
    response_format=SaidaEscalonador,
)
