"""A mesma conversa atrás de uma API, com persistência em SQLite.

Espelha o `web.py` do `agents/operador_conta_session`, trocando
`SqliteSessionService` por `SqliteSaver`.

    uv run uvicorn exemplos_langchain.ex_08_sessao.web:app --port 8000

    curl -s -XPOST localhost:8000/sessao | jq
    curl -s -XPOST localhost:8000/mensagem -H 'content-type: application/json' \\
         -d '{"thread_id":"...","mensagem":"quais minhas faturas? sou o cliente_123"}' | jq
"""

import sqlite3
import uuid
from pathlib import Path

from fastapi import FastAPI
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel

from exemplos_langchain.ex_08_sessao.agente import criar_agente

BANCO = Path(__file__).parent / ".dados" / "conversas.sqlite"
BANCO.parent.mkdir(exist_ok=True)

# `SqliteSaver.from_conn_string` é um context manager, útil em script. Numa API
# de vida longa, construa com a conexão na mão. `check_same_thread=False` porque
# o uvicorn atende requisições em threads diferentes.
conexao = sqlite3.connect(BANCO, check_same_thread=False)
checkpointer = SqliteSaver(conexao)
checkpointer.setup()  # cria as tabelas na primeira execução

agente = criar_agente(checkpointer)

app = FastAPI(title="Operador de Conta Acme (LangChain)")


@app.post("/sessao")
def criar_sessao() -> dict:
    """No LangGraph não existe 'criar sessão': basta escolher um thread_id.

    Este endpoint só existe para espelhar o exemplo ADK. Em código real, use um
    id que você já tem (id do chamado, do usuário, da conversa no seu produto).
    """
    return {"thread_id": str(uuid.uuid4())}


class MensagemRequest(BaseModel):
    thread_id: str
    mensagem: str


@app.post("/mensagem")
def enviar_mensagem(request: MensagemRequest) -> dict:
    resultado = agente.invoke(
        {"messages": [{"role": "user", "content": request.mensagem}]},
        config={"configurable": {"thread_id": request.thread_id}},
    )
    return {"message": resultado["messages"][-1].text}


@app.get("/historico/{thread_id}")
def historico(thread_id: str) -> dict:
    """Lê o estado persistido sem chamar o modelo.

    É o equivalente ao `session_service.get_session(...)` do ADK.
    """
    estado = agente.get_state({"configurable": {"thread_id": thread_id}})
    return {
        "mensagens": [
            {"tipo": m.type, "texto": m.text} for m in estado.values.get("messages", [])
        ]
    }
