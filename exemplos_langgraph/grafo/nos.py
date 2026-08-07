"""Os nós do grafo.

Dois tipos convivem, e essa é a razão de existir o LangGraph:

- nós DETERMINÍSTICOS (`triagem`, `triagem_refund`, `efetivar_refund`): código
  comum. Decidem rota, somam dinheiro, gravam no repositório. Sem modelo.
- nós AGÊNTICOS (`no_atendente`, `no_investigador`, `no_escalonador`): invocam um
  `create_agent` e escrevem o resultado estruturado no estado.

O roteamento usa `Command(goto=...)`, que atualiza o state e escolhe o próximo
nó na mesma volta — o análogo direto do
`Event(actions=EventActions(route=..., state_delta=...))` do ADK. A alternativa
seria `add_conditional_edges` com uma função de rota separada; preferi `Command`
por ficar 1:1 com o original.
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END
from langgraph.types import Command, interrupt

from exemplos_langgraph.acme import dominio
from exemplos_langgraph.acme.config import LIMIAR_APROVACAO, TETO_REFUND
from exemplos_langgraph.acme.dominio import CategoriaTicket, StatusTicket
from exemplos_langgraph.grafo.agentes import atendente, escalonador, investigador
from exemplos_langgraph.grafo.estado import EstadoResolucao

MENSAGEM_RECUSA = (
    "Olá! Este canal é exclusivo para suporte da Acme Cloud (faturamento, bugs, "
    "recursos e configuração da plataforma). Não identificamos um pedido de "
    "suporte na sua mensagem. Se precisar de ajuda com a plataforma, descreva o "
    "problema e abriremos um novo atendimento."
)


def _fechar(
    ticket_id: str, resposta: str, status: StatusTicket, erro: str = ""
) -> dict:
    """Grava o desfecho no repositório e devolve o update do estado.

    Escrita idempotente (atribuição, não incremento): se o nó reexecutar depois de
    um `interrupt`, o resultado é o mesmo.
    """
    ticket = dominio.buscar_ticket(ticket_id)
    if ticket is not None:
        ticket.resposta = resposta
        ticket.status = status
        if erro:
            ticket.erro = erro
        dominio.salvar_ticket(ticket)
    return {"resposta": resposta, "status_final": status.value}


# --- triagem -----------------------------------------------------------------


def triagem(
    state: EstadoResolucao,
) -> Command[Literal["recusar", "no_atendente", "no_investigador"]]:
    """Lê o ticket e escolhe a rota. Nenhum modelo envolvido."""
    ticket = dominio.buscar_ticket(state["ticket_id"])
    if ticket is None:
        return Command(
            goto="recusar",
            update={"resposta": f"Ticket {state['ticket_id']} não encontrado."},
        )

    comum = {
        "cliente_id": ticket.cliente_id,
        "mensagem": ticket.mensagem,
        "justificativa": ticket.justificativa,
    }

    if ticket.categoria == CategoriaTicket.OUT_OF_SCOPE:
        return Command(goto="recusar", update=comum)

    # O mesmo critério do ADK: só vai para a rota de refund se o classificador
    # marcou needs_refund E estava confiante.
    if ticket.precisa_refund and ticket.confianca >= 0.6:
        return Command(goto="no_investigador", update=comum)

    return Command(goto="no_atendente", update=comum)


def recusar(state: EstadoResolucao) -> dict:
    """Fecha o ticket fora de escopo com uma resposta padrão."""
    resposta = state.get("resposta") or MENSAGEM_RECUSA
    return _fechar(state["ticket_id"], resposta, StatusTicket.RESOLVIDO)


# --- atendimento geral -------------------------------------------------------


def no_atendente(state: EstadoResolucao) -> dict:
    """Delega ao agente atendente e guarda a saída estruturada."""
    resultado = atendente.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Ticket: {state.get('mensagem', '')}\n"
                        f"Contexto da triagem: {state.get('justificativa', '')}"
                    ),
                }
            ]
        }
    )
    saida = resultado["structured_response"]
    return {"resposta": saida.mensagem, "status_final": saida.status}


def finalizar(state: EstadoResolucao) -> dict:
    """Persiste o desfecho do atendimento geral."""
    status = (
        StatusTicket.RESOLVIDO
        if state.get("status_final") == "success"
        else StatusTicket.FALHOU
    )
    return _fechar(state["ticket_id"], state.get("resposta", ""), status)


# --- rota de refund ----------------------------------------------------------


def no_investigador(state: EstadoResolucao) -> dict:
    """Delega o JULGAMENTO da política ao agente. Ele aponta linhas, não valores."""
    resultado = investigador.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Cliente: {state.get('cliente_id', '')}\n"
                        f"Reclamação: {state.get('mensagem', '')}"
                    ),
                }
            ]
        }
    )
    saida = resultado["structured_response"]
    return {
        "veredito": saida.decisao.value,
        "mes_fatura": saida.mes,
        "linhas": saida.linhas,
        "raciocinio": saida.raciocinio,
    }


def _somar_linhas(cliente_id: str, mes: str, linhas: list[str]) -> dict:
    """Soma o valor REAL das linhas apontadas. Sem efeito colateral.

    Esta função é o coração da segurança financeira do fluxo: o LLM diz QUAIS
    linhas, o código diz QUANTO. Um modelo que alucina um valor não consegue
    causar prejuízo porque o valor nunca vem dele.
    """
    fatura = dominio.buscar_fatura(cliente_id, mes)
    if fatura is None:
        return {"status": "sem_fatura", "motivo": f"Não há fatura de {mes}."}

    por_id = {item["id"]: item for item in fatura["items"]}
    escolhidas = [por_id[i] for i in linhas if i in por_id]
    if not escolhidas:
        return {
            "status": "linhas_invalidas",
            "motivo": f"Nenhuma linha válida em {mes} para os ids {linhas}.",
        }

    valor = round(sum(item["amount"] for item in escolhidas), 2)
    skus = ", ".join(item["sku"] for item in escolhidas)
    if valor > TETO_REFUND:
        return {
            "status": "acima_do_teto",
            "valor": valor,
            "skus": skus,
            "motivo": f"Refund de ${valor:.2f} acima do teto de ${TETO_REFUND:.0f}.",
        }
    return {"status": "ok", "valor": valor, "skus": skus, "motivo": ""}


def _severidade(status_calculo: str, valor: float | None) -> str:
    """Severidade determinística — nasce aqui, nunca no LLM."""
    if status_calculo == "acima_do_teto":
        return "high"
    if status_calculo in ("sem_fatura", "linhas_invalidas"):
        return "low"
    if valor is not None and valor > 2 * LIMIAR_APROVACAO:
        return "high"
    return "medium"


def triagem_refund(
    state: EstadoResolucao,
) -> Command[Literal["refund_automatico", "no_escalonador"]]:
    """Soma o valor e decide: automático, aprovação humana ou handoff."""
    if state.get("veredito") != "refund":
        # O investigador desistiu: vai direto para o humano assumir.
        return Command(
            goto="no_escalonador",
            update={
                "intencao_escalacao": "handoff",
                "severidade": "medium",
                "motivo_calculo": state.get("raciocinio", ""),
            },
        )

    calculo = _somar_linhas(
        state.get("cliente_id", ""), state.get("mes_fatura", ""), state.get("linhas", [])
    )

    # Qualquer falha de cálculo (sem fatura, linhas inválidas, acima do teto)
    # vira handoff humano. Espelha o `_escalate_event` do ADK.
    if calculo["status"] != "ok":
        return Command(
            goto="no_escalonador",
            update={
                "intencao_escalacao": "handoff",
                "severidade": _severidade(calculo["status"], calculo.get("valor")),
                "motivo_calculo": calculo["motivo"],
                "valor_refund": calculo.get("valor", 0.0),
                "skus_refund": calculo.get("skus", ""),
            },
        )

    if calculo["valor"] > LIMIAR_APROVACAO:
        return Command(
            goto="no_escalonador",
            update={
                "intencao_escalacao": "aprovacao_refund",
                "severidade": _severidade("ok", calculo["valor"]),
                "valor_refund": calculo["valor"],
                "skus_refund": calculo["skus"],
            },
        )

    return Command(
        goto="refund_automatico",
        update={"valor_refund": calculo["valor"], "skus_refund": calculo["skus"]},
    )


def refund_automatico(state: EstadoResolucao) -> dict:
    """Abaixo do limiar: estorna sem humano nenhum no caminho."""
    dominio.emitir_refund(
        cliente_id=state.get("cliente_id", ""),
        valor=state.get("valor_refund", 0.0),
        motivo=f"Refund automático (ticket {state['ticket_id']})",
        ticket_id=state["ticket_id"],
    )
    resposta = (
        f"Olá! Seu pedido de reembolso foi aprovado e processado. O valor de "
        f"${state.get('valor_refund', 0.0):.2f} referente à fatura de "
        f"{state.get('mes_fatura', '')} (linhas: {state.get('skus_refund', '')}) será creditado "
        f"em sua conta em até 5 dias úteis."
    )
    return _fechar(state["ticket_id"], resposta, StatusTicket.RESOLVIDO)


# --- escalação e aprovação humana --------------------------------------------


def no_escalonador(state: EstadoResolucao) -> dict:
    """Abre o card de handoff. O agente é idempotente por ticket."""
    resumo = (
        f"Ticket {state['ticket_id']} do cliente {state.get('cliente_id', '')}. "
        f"Reclamação: {state.get('mensagem', '')}. "
    )
    if state.get("intencao_escalacao") == "aprovacao_refund":
        resumo += (
            f"Pedido de refund de ${state.get('valor_refund', 0):.2f} da fatura "
            f"de {state.get('mes_fatura')} (linhas: {state.get('skus_refund')}). "
            "Aprovar ou recusar."
        )
    else:
        resumo += f"Motivo: {state.get('motivo_calculo') or state.get('raciocinio', '')}"

    resultado = escalonador.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"ticket_id={state['ticket_id']}\n"
                        f"intencao={state.get('intencao_escalacao')}\n"
                        f"severidade={state.get('severidade')}\n"
                        f"resumo={resumo}"
                    ),
                }
            ]
        }
    )
    saida = resultado["structured_response"]
    return {"referencia_escalacao": saida.referencia, "status_escalacao": saida.status}


def triagem_escalacao(
    state: EstadoResolucao,
) -> Command[Literal["aguardar_aprovacao", "encerrar_escalado"]]:
    """Refund escalado espera decisão humana; handoff encerra aqui."""
    if state.get("intencao_escalacao") == "aprovacao_refund":
        return Command(goto="aguardar_aprovacao")
    return Command(goto="encerrar_escalado")


def encerrar_escalado(state: EstadoResolucao) -> dict:
    """Terminal do handoff: o ticket sai do automático e vai para um humano.

    Falhar ao escalar NÃO é a mesma coisa que escalar: sem card aberto, ninguém
    foi avisado. Por isso o status difere — e o motivo técnico fica registrado no
    ticket, não na resposta ao cliente.
    """
    if state.get("status_escalacao") == "falhou":
        resposta = (
            "Olá! Tivemos um problema técnico ao encaminhar seu caso e não foi "
            "possível concluí-lo automaticamente. A falha já está registrada e "
            "nossa equipe vai retomar o atendimento."
        )
        return _fechar(
            state["ticket_id"],
            resposta,
            StatusTicket.FALHOU,
            erro=state.get("motivo_calculo", "") or "falha ao abrir a escalação",
        )

    resposta = (
        "Olá! Seu caso precisa de uma análise mais detalhada e foi encaminhado a "
        f"um especialista (referência {state.get('referencia_escalacao', 'N/D')}). "
        "Retornaremos em breve."
    )
    return _fechar(state["ticket_id"], resposta, StatusTicket.ESCALADO)


def aguardar_aprovacao(state: EstadoResolucao) -> dict:
    """PAUSA o grafo até um humano decidir.

    `interrupt()` suspende a execução e persiste o state no checkpointer. O valor
    devolvido é exatamente o que vier no `Command(resume=...)`. É o equivalente do
    `RequestInput` do ADK — com a diferença de que aqui a retomada continua a
    MESMA execução, de dentro deste nó.
    """
    # Marca o ticket ANTES de pausar: enquanto o humano não decide, quem olhar o
    # repositório precisa ver que há algo esperando. A atribuição é idempotente,
    # e isso importa porque o corpo do nó re-executa quando a execução retoma.
    ticket = dominio.buscar_ticket(state["ticket_id"])
    if ticket is not None:
        ticket.status = StatusTicket.AGUARDANDO_APROVACAO
        dominio.salvar_ticket(ticket)

    decisao = interrupt(
        {
            "pergunta": "Aprovar o estorno?",
            "ticket_id": state["ticket_id"],
            "valor": state.get("valor_refund"),
            "mes": state.get("mes_fatura"),
            "skus": state.get("skus_refund"),
            "referencia": state.get("referencia_escalacao"),
        }
    )
    aprovado = bool(decisao.get("aprovado")) if isinstance(decisao, dict) else bool(decisao)
    return {"status_final": "aprovado" if aprovado else "recusado"}


def efetivar_refund(state: EstadoResolucao) -> dict:
    """Aplica a decisão humana. O efeito é idempotente por ticket."""
    if state.get("status_final") != "aprovado":
        resposta = (
            "Olá! Seu pedido de reembolso foi analisado, mas não foi aprovado. "
            "Se tiver dúvidas, entre em contato com nosso suporte."
        )
        return _fechar(state["ticket_id"], resposta, StatusTicket.RESOLVIDO)

    dominio.emitir_refund(
        cliente_id=state.get("cliente_id", ""),
        valor=state.get("valor_refund", 0.0),
        motivo=f"Refund aprovado por humano (ticket {state['ticket_id']})",
        ticket_id=state["ticket_id"],
    )
    resposta = (
        f"Olá! Seu pedido de reembolso foi aprovado e processado. O valor de "
        f"${state.get('valor_refund', 0.0):.2f} referente à fatura de "
        f"{state.get('mes_fatura', '')} (linhas: {state.get('skus_refund', '')}) será creditado "
        f"em sua conta em até 5 dias úteis."
    )
    return _fechar(state["ticket_id"], resposta, StatusTicket.RESOLVIDO)


__all__ = [
    "END",
    "aguardar_aprovacao",
    "efetivar_refund",
    "encerrar_escalado",
    "finalizar",
    "no_atendente",
    "no_escalonador",
    "no_investigador",
    "recusar",
    "refund_automatico",
    "triagem",
    "triagem_escalacao",
    "triagem_refund",
]
