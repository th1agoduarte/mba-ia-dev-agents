"""O estado do grafo.

No ADK, o `Workflow` carrega `ctx.state` (um dicionário plano) e passa o
`node_input` de um nó para o seguinte. No LangGraph existe UM schema de estado
declarado, e todo nó devolve um dicionário PARCIAL que é mesclado nele.

Duas consequências que mudam como se pensa o fluxo:

- Não existe "saída do nó anterior" implícita. Se um nó precisa de um dado, esse
  dado tem que estar no estado — o que torna a dependência explícita e legível.
- O estado é o contrato do grafo. Ler esta classe deveria bastar para entender o
  que circula entre os nós.
"""

from __future__ import annotations

from typing import Literal

from typing_extensions import NotRequired, TypedDict


class EstadoResolucao(TypedDict):
    """Tudo que circula entre os nós da resolução de um ticket."""

    # entrada
    ticket_id: str

    # preenchido pela triagem, a partir do ticket
    cliente_id: NotRequired[str]
    mensagem: NotRequired[str]
    justificativa: NotRequired[str]

    # veredito do investigador de refund
    veredito: NotRequired[Literal["refund", "escalate"]]
    mes_fatura: NotRequired[str]
    linhas: NotRequired[list[str]]
    raciocinio: NotRequired[str]

    # cálculo determinístico do valor (nunca vem do LLM)
    valor_refund: NotRequired[float]
    skus_refund: NotRequired[str]
    motivo_calculo: NotRequired[str]

    # escalação
    intencao_escalacao: NotRequired[Literal["aprovacao_refund", "handoff"]]
    severidade: NotRequired[str]
    referencia_escalacao: NotRequired[str]
    status_escalacao: NotRequired[str]

    # desfecho
    resposta: NotRequired[str]
    status_final: NotRequired[str]
