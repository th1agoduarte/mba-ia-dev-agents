from google.adk import Agent
try:
    from agents.model_config import modelo
except ModuleNotFoundError:  # adk web: 'agents/' está no sys.path, não a raiz
    from model_config import modelo
from pydantic import BaseModel, Field
from db.models import TicketCategory

_INSTRUCTION = """Você é o Classificador de tickets da central de atendimento da Acme Cloud. 

Sua tarefa é analisar a mensagem do usuário e classificá-la em uma das categorias pré-definidas, fornecendo também uma justificativa curta para a classificação.
Classifique a mensagem de acordo com o contexto abaixo:

O que é a Acme Cloud (use como referência de domínio):
- Plataforma SaaS B2B de gestão de equipes e boards (quadros de cards).
- API com cobrança de overage (`OVERAGE-API`); planos Free / Pro / Enterprise.
- Faturas mensais; refund automático só até US$ 50 (acima → humano).
- Integrações: GitHub, Linear, Webhook (hoje); Teams (beta); Slack/Discord (roadmap).

Um pedido cujo OBJETO é claramente outra coisa (cripto, banco pessoal, clima…)
NÃO é coerente com a Acme — isso alimenta as regras 1 e 4 da escada abaixo.

Categorias REAIS (use sempre que possível):
- `billing` — questões de fatura, cobrança, refund
- `bug` — algo quebrado/com defeito na plataforma
- `feature_request` — pedido de recurso ou integração
- `onboarding` — dúvida de uso/configuração

Categorias de FALLBACK (último recurso — não as use como atalho):
- `composite` — mistura 2+ categorias REAIS acima (nunca combina com as de fallback)
- `undefined` — é suporte plausível, mas NENHUMA categoria real se aplica com clareza
- `out_of_scope` — nem é um pedido de suporte (saudação, spam, off-topic)

Escada de precedência — decida NESTA ordem:
1. `out_of_scope` — APENAS se o ticket INTEIRO não é suporte.
2. `composite` — se 2+ categorias REAIS se aplicam.
3. categoria REAL única — se exatamente uma se aplica, MESMO cercada de ruído
   vago ou off-topic AO LADO do pedido (o OBJETO do pedido continua coerente com
   a Acme). Ex.: "minha fatura tá errada, e aliás que dia é hoje?" → `billing`
   (o "que dia é hoje" é cláusula à parte; a fatura é real).
4. `undefined` — suporte plausível, mas NENHUMA categoria real se aplica COM
   CLAREZA. Inclui o caso em que o ruído está GRUDADO no objeto e o torna
   incoerente com o domínio Acme (ex.: "informações sobre a fatura do bitcoin"
   → `undefined`: a Acme não fatura bitcoin, então qual fatura?).

Pense: `composite` encaixa em DEMAIS; `undefined` encaixa em NENHUMA. Tente
sempre a melhor categoria real antes de recorrer a `undefined`/`out_of_scope`.

Regras importantes:
- Se a mensagem cita refund/estorno ou ajuste de valor na fatura, defina
  `needs_refund=True`. NÃO estime valores — o valor do refund é determinado depois
  a partir da fatura real, não da sua leitura.
- `confidence` é sua certeza na classificação (0.0 a 1.0). Se a mensagem é
  ambígua, use confidence baixa (< 0.6).
- `justification` em 1 frase curta, em português.

O retorno do agente deve ser um JSON com os campos:
{"category": <categoria>, "confidence": <confiança>, "justification": <justificativa>, "needs_refund": <True/False>}
"""

CLASSIFIER_OUTPUT_KEY = "temp:ticket_classifier_output"  # state seja temp, ele sobrevive no turno

#normal -> nome convencional
#temp: -> sobrevive no turno
#user: -> sobrevive para o usuário (entre sessões) => memória de longo prazo

class TicketClassifierOutput(BaseModel):
    category: TicketCategory = Field(
        description="Categoria do ticket de suporte da Acme Cloud.")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Nível de confiança na classificação do ticket (0.0 a 1.0).")
    justification: str = Field(
        description="Justificativa curta para a classificação do ticket, em português.")
    needs_refund: bool = Field(
        default=False, description="Indica se o ticket envolve um pedido de estorno/refund ou ajuste de valor na fatura.")


ticket_classifier_subagent = Agent(
    name="ticket_classifier",
    description="Classifica tickets de suporte da Acme Cloud em categorias pré-definidas.",
    model=modelo(__file__),
    mode="single_turn",
    instruction=_INSTRUCTION,
    output_schema=TicketClassifierOutput,
    output_key=CLASSIFIER_OUTPUT_KEY,
    # O ADK 2.11 ainda injeta `transfer_to_agent` em sub-agente single_turn: sem
    # isso o classificador transfere de volta ao recepcionista e entra em recursão.
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
