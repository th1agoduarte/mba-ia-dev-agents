from google.adk.sessions import InMemorySessionService
from google.adk import Runner
from google.genai import types
from google.adk.apps import App
from agents.operador_conta_session.agent import root_agent
import asyncio
from dotenv import load_dotenv

load_dotenv()

session_service = InMemorySessionService() # memoria ram
# db
app = App(
    root_agent=root_agent, 
    name="operador_conta",

)

runner = Runner(
    app=app,
    session_service=session_service,
)

async def run_agent():

    # message (opcional) e sessao

    #db i/o - bloqueante
    sessao = await session_service.create_session(
        app_name=runner.app_name,
        user_id="cliente_123",
    )

    conteudo = types.Content(
        role="user",
        parts=[types.Part.from_text(text="listar minhas faturas")]
    )

    #i/o -> http -> bloqueante
    async for event in runner.run_async(
        session_id=sessao.id,
        user_id=sessao.user_id,
        new_message=conteudo
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                print("Resposta final:", event.content.parts[0].text)

asyncio.run(run_agent())

