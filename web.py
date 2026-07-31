"""O fluxo completo de tickets da Acme Cloud atrás de uma API.

Costura os dois agentes do projeto:

- `ticket_receptionist` (chat)    — conversa com o cliente, classifica e ABRE o
  ticket no banco (tool `registrar_ticket`).
- `ticket_resolution` (`Workflow`) — resolve um ticket já aberto. Pode PAUSAR
  pedindo aprovação humana (`RequestInput`) quando o refund passa do limiar.

Rodar:

    uv run uvicorn web:app --port 8000

Os botões para experimentar (backend de sessão, cliente padrão, nomes) estão no
bloco "Configuração", logo abaixo dos imports.

Endpoints (requests prontas em `api_tickets.http`):

    POST /sessao                          abre a sessão de conversa
    POST /mensagem                        fala com o recepcionista (abre o ticket)
    GET  /tickets/{ticket_id}             lê o ticket no banco
    POST /tickets/{ticket_id}/resolucao   roda o workflow de resolução
    POST /tickets/{ticket_id}/aprovacao   responde o `RequestInput` e RETOMA o workflow
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from google.adk import Runner
from google.adk.apps import App
from google.adk.events import Event
from google.adk.sessions import DatabaseSessionService, InMemorySessionService, Session
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.genai import types
from pydantic import BaseModel, Field
import env

from agents.ticket_receptionist.agent import app as receptionist_app
from agents.ticket_resolution.agent import root_agent as ticket_resolution
from db import repo
from db.engine import close_db, init_db
from db.models import TicketModel

# --------------------------------------------------------------------------- #
# Configuração — os botões para brincar estão todos aqui                       #
# --------------------------------------------------------------------------- #

CURRENT_PATH = __file__.rsplit("/", 1)[0]

# Onde as sessões (e portanto a pausa do refund) são guardadas:
#   "sqlite"   — arquivo local; sobrevive ao restart do servidor
#   "memoria"  — some junto com o processo: bom para ver a pausa MORRER
#   "postgres" — o banco do docker-compose
# Como a aprovação chega em OUTRA requisição, só os dois persistentes seguram a
# pausa se o servidor cair no meio.
SESSION_BACKEND = os.environ.get("SESSION_BACKEND", "sqlite")
SESSION_DB_PATH = f"{CURRENT_PATH}/.adk/tickets_session.db"
SESSION_DB_URL = os.environ.get(
    "SESSION_DB_URL", "postgresql+asyncpg://acme:acme@localhost:5432/acme")

API_TITLE = "Central de Tickets Acme"
RESOLUTION_APP_NAME = "ticket_resolution"

# Cliente usado quando o POST /sessao não manda `customer_id`. Os que existem no
# mock de billing (`outside/mock_billing_server.py`):
#   C-201  fatura legítima            → cai no atendimento geral
#   C-203  plano duplicado de $30     → refund automático
#   C-204  plano duplicado de $480    → acima do teto, vira handoff humano
#   C-205  sem fatura nenhuma         → handoff humano
#   C-206  ajuste manual de $40       → refund automático
#   C-207  ajuste manual de $120      → PAUSA pedindo aprovação humana
# Os limites que decidem entre esses caminhos são o `REFUND_APPROVAL_THRESHOLD`
# e o `REFUND_MAX_LIMIT` do `.env` (lidos em `env.py`).
CUSTOMER_ID_PADRAO = "C-203"

# Tool do recepcionista de onde sai o `ticket_id` recém-registrado.
TOOL_REGISTRAR_TICKET = "registrar_ticket"

# Nome da function_call que o `RequestInput` de um nó gera no stream de eventos.
# É por ela que a pausa é detectada e o resume é endereçado.
REQUEST_INPUT = "adk_request_input"


# --------------------------------------------------------------------------- #
# Montagem: SessionService -> Apps -> Runners -> API                           #
# --------------------------------------------------------------------------- #

if SESSION_BACKEND == "memoria":
    session_service = InMemorySessionService()
elif SESSION_BACKEND == "postgres":
    session_service = DatabaseSessionService(SESSION_DB_URL)
else:
    os.makedirs(f"{CURRENT_PATH}/.adk", exist_ok=True)
    session_service = SqliteSessionService(SESSION_DB_PATH)

resolution_app = App(
    root_agent=ticket_resolution,
    name=RESOLUTION_APP_NAME,
)

receptionist_runner = Runner(
    app=receptionist_app, session_service=session_service)
resolution_runner = Runner(app=resolution_app, session_service=session_service)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(title=API_TITLE, lifespan=lifespan)


# --------------------------------------------------------------------------- #
# Helpers de leitura do stream de eventos                                      #
# --------------------------------------------------------------------------- #


def _texto(event: Event) -> str | None:
    """Texto do evento (None se ele só carrega function_call/response)."""
    if not event.content or not event.content.parts:
        return None
    partes = [part.text for part in event.content.parts if part.text]
    return "\n".join(partes) if partes else None


def _ticket_registrado(event: Event) -> str | None:
    """Pesca o `ticket_id` no retorno da tool `registrar_ticket`.

    O texto do agente é para o humano; o id é dado de máquina — por isso vem do
    `function_response`, não de um parse da resposta em linguagem natural.
    """
    for function_response in event.get_function_responses():
        if function_response.name != TOOL_REGISTRAR_TICKET:
            continue
        resposta = function_response.response
        if isinstance(resposta, dict) and resposta.get("status") == "success":
            return resposta.get("ticket_id")
    return None


def _aprovacao_pendente(sessao: Session) -> tuple[str, str] | None:
    """`(interrupt_id, mensagem)` do `RequestInput` ainda sem resposta, se houver.

    Um interrupt cujo id JÁ tem um `function_response` na sessão foi respondido —
    ignorá-lo é o que torna o endpoint de aprovação idempotente (um segundo POST
    não retoma o workflow de novo).
    """
    pendentes: dict[str, str] = {}
    for event in sessao.events:
        if not event.content or not event.content.parts:
            continue
        for part in event.content.parts:
            function_call = part.function_call
            if function_call and function_call.name == REQUEST_INPUT and function_call.id:
                pendentes[function_call.id] = (
                    function_call.args or {}).get("message", "")
            function_response = part.function_response
            if (
                function_response
                and function_response.name == REQUEST_INPUT
                and function_response.id
            ):
                pendentes.pop(function_response.id, None)
    if not pendentes:
        return None
    interrupt_id, mensagem = list(pendentes.items())[-1]
    return interrupt_id, mensagem


# --------------------------------------------------------------------------- #
# 1. Sessão de conversa + 2. abertura do ticket (ticket_receptionist)          #
# --------------------------------------------------------------------------- #


class NovaSessaoRequest(BaseModel):
    customer_id: str = Field(
        default=CUSTOMER_ID_PADRAO, description="Id do cliente na Acme.")


@app.post("/sessao")
async def criar_sessao(request: NovaSessaoRequest):
    sessao = await session_service.create_session(
        app_name=receptionist_runner.app_name,
        user_id=request.customer_id,
    )
    return {"session_id": sessao.id, "customer_id": request.customer_id}


class MensagemRequest(BaseModel):
    session_id: str
    customer_id: str
    mensagem: str


@app.post("/mensagem")
async def enviar_mensagem(request: MensagemRequest):
    """Um turno de conversa com o recepcionista.

    Quando o turno registra o ticket, devolve também o `ticket_id` — é ele que
    alimenta o `/resolucao`.
    """
    sessao = await session_service.get_session(
        app_name=receptionist_runner.app_name,
        user_id=request.customer_id,
        session_id=request.session_id,
    )
    if not sessao:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    conteudo = types.Content(
        role="user",
        parts=[types.Part.from_text(text=request.mensagem)],
    )

    message: str | None = None
    ticket_id: str | None = None
    async for event in receptionist_runner.run_async(
        session_id=sessao.id,
        user_id=sessao.user_id,
        new_message=conteudo,
    ):
        registrado = _ticket_registrado(event)
        if registrado is not None:
            ticket_id = registrado
        if event.is_final_response():
            texto = _texto(event)
            if texto is not None:
                message = texto

    return {"message": message, "ticket_id": ticket_id}


# --------------------------------------------------------------------------- #
# 3. Resolução do ticket (ticket_resolution) + 4. aprovação humana do refund   #
# --------------------------------------------------------------------------- #


async def _rodar_resolucao(ticket: TicketModel, sessao: Session, conteudo: types.Content):
    """Roda (ou retoma) o grafo e monta a resposta a partir do que ficou no banco.

    A leitura do desfecho é feita DEPOIS do `run_async`, fora do grafo: o corpo
    de um nó re-executa no resume, então quem finaliza a requisição é o driver,
    não o grafo.
    """
    async for _ in resolution_runner.run_async(
        session_id=sessao.id,
        user_id=sessao.user_id,
        new_message=conteudo,
    ):
        pass

    # Relê a sessão: os eventos da rodada — inclusive uma eventual pausa — só
    # estão gravados depois que o `run_async` termina.
    sessao_apos_run = await session_service.get_session(
        app_name=resolution_runner.app_name,
        user_id=sessao.user_id,
        session_id=sessao.id,
    )
    pendente = _aprovacao_pendente(
        sessao_apos_run) if sessao_apos_run else None

    # Relê o ticket: quem gravou status/response foram os nós, durante o run.
    ticket_apos_run = await repo.get_ticket(ticket.id)
    if ticket_apos_run:
        ticket = ticket_apos_run

    if pendente:
        interrupt_id, pergunta = pendente
        return {
            "ticket_id": ticket.id,
            "status": ticket.status,
            "aprovacao_pendente": {"interrupt_id": interrupt_id, "message": pergunta},
        }

    return {
        "ticket_id": ticket.id,
        "status": ticket.status,
        "message": ticket.response,
    }


@app.post("/tickets/{ticket_id}/resolucao")
async def resolver_ticket(ticket_id: str):
    ticket = await repo.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=404, detail=f"Ticket {ticket_id} não encontrado.")

    # Uma sessão por ticket (`session_id == ticket_id`): é o que deixa o resume
    # endereçável mais tarde, só com o id do ticket em mãos.
    sessao = await session_service.get_session(
        app_name=resolution_runner.app_name,
        user_id=ticket.customer_id,
        session_id=ticket_id,
    )

    if not sessao:
        sessao = await session_service.create_session(
            app_name=resolution_runner.app_name,
            user_id=ticket.customer_id,
            session_id=ticket_id,
            state={"ticket_id": ticket_id},  # o `triage_ticket_node` lê daqui
        )

    conteudo = types.Content(
        role="user",
        parts=[
            types.Part.from_text(text="resolva")
        ],
    )

    return await _rodar_resolucao(ticket, sessao, conteudo)


class AprovacaoRequest(BaseModel):
    confirmed: bool


@app.post("/tickets/{ticket_id}/aprovacao")
async def responder_aprovacao(ticket_id: str, request: AprovacaoRequest):
    """Responde o `RequestInput` do refund e RETOMA o workflow de onde parou.

    O resume é um `FunctionResponse` com o **id do interrupt** e o nome
    `adk_request_input`, SEM `invocation_id`: o grafo recupera o nó em WAITING e
    entrega esse payload ao nó seguinte (`refund_with_confirmation`).
    """
    ticket = await repo.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=404, detail=f"Ticket {ticket_id} não encontrado.")

    sessao = await session_service.get_session(
        app_name=resolution_runner.app_name,
        user_id=ticket.customer_id,
        session_id=ticket_id,
    )
    if not sessao:
        raise HTTPException(
            status_code=404,
            detail=f"A resolução do ticket {ticket_id} ainda não foi iniciada.",
        )

    pendente = _aprovacao_pendente(sessao)
    if not pendente:
        raise HTTPException(
            status_code=409,
            detail=f"Não há aprovação pendente no ticket {ticket_id}.",
        )

    interrupt_id, _ = pendente
    resposta = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=interrupt_id,
                    name=REQUEST_INPUT,
                    response={"confirmed": request.confirmed},
                )
            )
        ],
    )
    return await _rodar_resolucao(ticket, sessao, resposta)


@app.get("/tickets/{ticket_id}")
async def consultar_ticket(ticket_id: str):
    """Lê o ticket direto do banco — sem chamar agente nenhum."""
    ticket = await repo.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=404, detail=f"Ticket {ticket_id} não encontrado.")
    return {
        "ticket_id": ticket.id,
        "customer_id": ticket.customer_id,
        "status": ticket.status,
        "message": ticket.message,
        "response": ticket.response,
        "classification": ticket.classification,
    }
