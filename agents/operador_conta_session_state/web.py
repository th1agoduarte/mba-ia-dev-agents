from fastapi import FastAPI
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.adk import Runner
from google.genai import types
from google.adk.apps import App
from pydantic import BaseModel
from agents.operador_conta_session_state.agent import PesquisaSatisfacaoOutput, root_agent
from dotenv import load_dotenv
import os

load_dotenv()


CURRENT_PATH = __file__.rsplit("/", 1)[0]
# criar a pasta .adk se não existir
if not os.path.exists(f"{CURRENT_PATH}/.adk"):
    os.makedirs(f"{CURRENT_PATH}/.adk")
session_service = SqliteSessionService(f"{CURRENT_PATH}/.adk/session.db")

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

def get_user(user_id: str = "user_1") -> dict:
    users = [
        {"user_id": "user_1", "cliente_id": "cliente_123"},
        {"user_id": "user_2", "cliente_id": "cliente_456"},
    ]
    for user in users:
        if user["user_id"] == user_id:
            return user
    return {"user_id": user_id, "cliente_id": "cliente_123"}


class NovaSessaoRequest(BaseModel):
    user_id: str

@app.post("/sessao")
async def criar_sessao(request: NovaSessaoRequest | None = None):
    user_id = request.user_id if request and request.user_id else "user_1"
    user = get_user(user_id=user_id)
    sessao = await session_service.create_session(
        app_name=runner.app_name,
        user_id=user["user_id"],
        state={"cliente_id": user["cliente_id"]} 
    )
    return {"session_id": sessao.id}


class MensagemRequest(BaseModel):
    mensagem: str
    session_id: str
    


@app.post("/mensagem")
async def enviar_mensagem(request: MensagemRequest): 
    user = get_user()
    
    conteudo = types.Content(
        role="user",
        parts=[types.Part.from_text(text=request.mensagem)]
    )

    sessao = await session_service.get_session(
        session_id=request.session_id,
        user_id=user["user_id"],
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
        if event.is_final_response(): #coordenador, faturas, assinaturas
            if event.content and event.content.parts:
                print(event.actions.state_delta.get("operador_conta_resultado")) # padronizado
                message = event.content.parts[0].text
                
    return {"message": message}

@app.get("/")
async def teste_direto():
    user = get_user()
    sessao = await session_service.create_session( 
        app_name=runner.app_name,
        user_id=user["user_id"],
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
