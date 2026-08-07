"""8. Sessão e persistência — equivale a `agents/operador_conta_session`.

Mapa direto do ADK para o LangChain:

| ADK                                   | LangChain / LangGraph                    |
|---------------------------------------|------------------------------------------|
| `Runner` + `App`                      | o próprio agente (`agente.invoke`)       |
| `SessionService`                      | `checkpointer`                           |
| `session.id`                          | `thread_id` no `config`                  |
| `InMemorySessionService`              | `InMemorySaver`                          |
| `SqliteSessionService(".../x.db")`    | `SqliteSaver` (langgraph-checkpoint-sqlite) |
| `DatabaseSessionService("postgres…")` | `PostgresSaver` (langgraph-checkpoint-postgres) |
| `create_session(...)` antes de falar  | nada: a thread nasce no primeiro invoke  |

A diferença conceitual que mais pega: no ADK você CRIA a sessão explicitamente e
recebe um id. No LangGraph o `thread_id` é escolhido por você — pode ser o id do
chamado, do usuário, um uuid — e a thread passa a existir no primeiro invoke.
Não há "sessão não encontrada": um thread_id desconhecido é simplesmente uma
conversa vazia.

Este módulo expõe uma FÁBRICA em vez de um agente pronto, porque o checkpointer
muda conforme o processo que executa (script, API, teste).
"""

from langchain.agents import create_agent

from exemplos_langchain.acme.config import MODELO_RAPIDO
from exemplos_langchain.acme.tools import cancelar_assinatura, consultar_assinatura, listar_faturas

INSTRUCAO = """
    Você é o atendente de conta interativo da Acme.
    Informe o cliente sobre sua assinatura (plano, status, renovação), tire
    dúvidas sobre faturas e cancele a assinatura quando solicitado.
    Peça o ID do cliente se ainda não souber, e a senha para cancelar.
    Seja cordial e direto.
"""


def criar_agente(checkpointer=None):
    """Monta o agente com o checkpointer escolhido por quem chama.

    `checkpointer=None` é o caso do Agent Server (`langgraph dev`): ele injeta a
    persistência sozinho, então o grafo não deve trazer a sua.
    """
    return create_agent(
        model=MODELO_RAPIDO,
        system_prompt=INSTRUCAO,
        tools=[listar_faturas, consultar_assinatura, cancelar_assinatura],
        checkpointer=checkpointer,
    )


# Grafo de módulo, para o `langgraph.json` ter o que apontar.
agente = criar_agente()
