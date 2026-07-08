from fastapi import FastAPI
from google.adk.sessions import InMemorySessionService
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.adk.sessions import DatabaseSessionService
from google.adk import Runner
from google.genai import types
from google.adk.apps import App
from pydantic import BaseModel
from agents.operador_conta_session.agent import root_agent
from dotenv import load_dotenv

load_dotenv()

#session_service = InMemorySessionService()  # memoria ram
#session_service = SqliteSessionService("./operador_conta_session.sqlite")  # sqlite
session_service = DatabaseSessionService("postgresql+asyncpg://acme:acme@localhost:5432/acme")

# db
adk_app = App(
    root_agent=root_agent,
    name="operador_conta",
)

runner = Runner(
    app=adk_app,
    session_service=session_service,
)

app = FastAPI(title="Operador de Conta Acme")


@app.post("/sessao")
async def criar_sessao():
    sessao = await session_service.create_session(
        app_name=runner.app_name,
        user_id="cliente_123",
    )
    return {"session_id": sessao.id}


class MensagemRequest(BaseModel):
    mensagem: str
    session_id: str
    


@app.post("/mensagem")
async def enviar_mensagem(request: MensagemRequest): 
    conteudo = types.Content(
        role="user",
        parts=[types.Part.from_text(text=request.mensagem)]
    )

    sessao = await session_service.get_session(
        session_id=request.session_id,
        user_id="cliente_123",
        app_name=runner.app_name
    )

    if not sessao:
        return {"error": "Sessão não encontrada."}

    message = None
    async for event in runner.run_async( # await llm, session, tool (db, disco, etc)
            session_id=sessao.id,
            user_id=sessao.user_id,
            new_message=conteudo
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                message = event.content.parts[0].text
    return {"message": message}

@app.get("/")
async def teste_direto():
    sessao = await session_service.create_session( 
        app_name=runner.app_name,
        user_id="cliente_123",
    )

    conteudo = types.Content(
        role="user",
        parts=[types.Part.from_text(text="listar minhas faturas")]
    )

    message = None
    async for event in runner.run_async(
        session_id=sessao.id,
        user_id=sessao.user_id,
        new_message=conteudo
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                message = event.content.parts[0].text
    return {"message": message}
