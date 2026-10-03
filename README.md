# Desenvolvimento de Agentes com IA

Projeto da disciplina **Desenvolvimento de Agentes com IA** do MBA de Engenharia de Software com IA da [Full Cycle](https://fullcycle.com.br).

O objetivo da disciplina é ensinar os **fundamentos da construção de agentes** — tools, aprovação humana, composição entre agentes, sessão, estado, plugins, MCP e orquestração em grafo — e não uma biblioteca específica. O framework principal é o **Google ADK 2.x**; cada conceito é depois reescrito em **LangChain** e **LangGraph**, sobre o mesmo domínio, para separar o que é ideia do que é API.

Todos os exemplos giram em torno da **Acme Cloud**: uma empresa fictícia de SaaS com faturas, assinaturas e uma central de tickets de suporte.

## Professor

<a href="https://github.com/argentinaluiz">
    <img src="https://avatars.githubusercontent.com/u/4926329?v=4?s=100" width="100px;" alt=""/>
    <br />
    <sub>
        <b>Luiz Carlos</b>
    </sub>
</a>

---

## Materiais de aula

- [Quadro Branco](./whiteboard.svg) — os diagramas construídos durante as aulas.
- [Slides](./slides.pdf) — o material de apoio.

---

## 📋 Pré-requisitos

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — gerenciador de dependências e ambiente virtual. Todo comando do repositório é prefixado com `uv run`; nenhum exemplo usa o Python global da máquina.
- **Chave da API do Gemini** — [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- **Docker** *(opcional)* — só para o exemplo de sessão em PostgreSQL. O default é SQLite.
- **Conta no Linear** *(opcional)* — só para os exemplos de MCP. Sem ela, o escalonamento grava um card local e o fluxo continua.

## ⚙️ Configuração

```bash
# instala tudo (ADK, LangChain, LangGraph, drivers) no .venv do projeto
uv sync

# variáveis de ambiente
cp .env.example .env
# preencha GOOGLE_API_KEY
```

O `.env.example` documenta cada variável. Três observações:

- `GOOGLE_API_KEY` é a única realmente obrigatória para começar (com o provider padrão).
- `ACCOUNT_MCP_HOST` e `ACCOUNT_MCP_PORT` **não têm valor default no código** — sem elas o `ticket_resolution` falha já no import. Já vêm preenchidas no `.env.example`.
- `MODEL_PROVIDER` escolhe o modelo de **todos** os agentes — veja abaixo.

### Gemini ou Anthropic (Claude)

Todos os agentes passam pelo seletor central [`agents/model_config.py`](agents/model_config.py), que troca de provider pela variável `MODEL_PROVIDER` no `.env` — sem mexer em código:

```bash
MODEL_PROVIDER=gemini      # padrão — usa GOOGLE_API_KEY
MODEL_PROVIDER=anthropic   # usa ANTHROPIC_API_KEY (via litellm)
```

Com `anthropic`, cada modelo Gemini é mapeado para um equivalente Claude (`flash` → Sonnet, `flash-lite` → Haiku); ajuste os IDs em `agents/model_config.py` se necessário. Os exemplos em `exemplos_langchain/` respeitam o mesmo switch, mas em modo `anthropic` exigem `uv add langchain-anthropic`.

### Modelo por agente (variáveis no `.env` da raiz)

Tudo fica no **`.env` da raiz**. Cada agente tem a **sua própria variável** de modelo, mais uma variável com o **valor padrão**:

```bash
# valor padrão (SEM CUSTO), usado por quem não tiver variável preenchida
DEFAULT_MODEL=gemini-3.5-flash-lite

# variável de cada agente (vazio = usa DEFAULT_MODEL)
MEU_AGENTE1_MODEL=
OPERADOR_CONTA_MODEL=gemini-3.5-flash     # override só deste agente
```

Regras:

- O nome da variável é o **nome da pasta do agente em MAIÚSCULAS + `_MODEL`** (ex.: `agents/operador_conta/` → `OPERADOR_CONTA_MODEL`). Cada agente chama `modelo(__file__)` e a chave é derivada automaticamente.
- **Vazia ou ausente** → o agente usa `DEFAULT_MODEL` (sem custo). Sem nem o `DEFAULT_MODEL`, o código cai em `gemini-3.5-flash-lite`.
- O valor é um nome de modelo **Gemini**; com `MODEL_PROVIDER=anthropic`, ele é mapeado para o Claude equivalente automaticamente.
- Todas essas variáveis já vêm listadas (vazias) no [`.env.example`](.env.example). A lógica está em [`agents/model_config.py`](agents/model_config.py).

## 🚀 Como rodar

### A interface do ADK (`adk web`)

É a forma principal de trabalhar durante as aulas. O `adk web` varre a pasta e lista **todos** os agentes num dropdown, com o grafo de eventos ao lado da conversa:

```bash
PYTHONPATH=. uv run adk web agents
```

> **Por que `PYTHONPATH=.`?** A partir do ADK 2.11 o loader do `adk web` coloca
> só a pasta `agents/` no `sys.path` — não a raiz do repo. Os agentes
> multi-arquivo (`ticket_resolution`, `ticket_receptionist`) importam seus
> sub-agentes com `from agents....`, então sem a raiz no path eles falham com
> `No module named 'agents'`. `PYTHONPATH=.` (rodando da raiz) resolve.

Para conversar no terminal, com um agente específico:

```bash
PYTHONPATH=. uv run adk run agents/operador_conta
```

> O detalhe de como o ADK descobre e carrega esses agentes está em [`docs/01`](./docs/01-adk-run-carregamento-de-agentes.md).

### Os exemplos que têm driver próprio

Alguns exemplos não cabem no `adk web` porque precisam montar o cenário antes de falar com o agente (semear estado, aprovar uma pausa, comparar backends de sessão). Esses trazem um `main.py` ou um `web.py`:

```bash
uv run python agents/operador_conta_session/main.py
uv run uvicorn agents.operador_conta_session.web:app --port 8000
```

### A aplicação completa

O `web.py` da raiz costura os dois agentes grandes numa API só: o **recepcionista** conversa com o cliente e abre o ticket; o **workflow de resolução** o resolve — e pode **pausar** pedindo aprovação humana quando o estorno passa do limiar.

```bash
# servidor MCP da conta, usado pelo account_operator
uv run python outside/account_mcp_server.py

# a API
uv run uvicorn web:app --port 8000
```

As requisições prontas estão em [`api_tickets.http`](./api_tickets.http). O fluxo é:

| Rota | O que faz |
|---|---|
| `POST /sessao` | abre a conversa com o recepcionista |
| `POST /mensagem` | fala com o recepcionista, que classifica e abre o ticket |
| `GET /tickets/{id}` | lê o ticket no banco |
| `POST /tickets/{id}/resolucao` | roda o workflow — pode **pausar** aqui |
| `POST /tickets/{id}/aprovacao` | responde a pausa e **retoma** o workflow |

O cliente usado decide o caminho: `C-203` cai em estorno automático, `C-207` **pausa** pedindo aprovação, `C-204` estoura o teto e vira handoff humano. A lista completa está comentada no topo do `web.py`.

Para trocar o backend de sessão por PostgreSQL:

```bash
docker compose up -d
SESSION_BACKEND=postgres uv run uvicorn web:app --port 8000
```

### As trilhas complementares

```bash
# LangChain — 11 exemplos, um por conceito
uv run python -m exemplos_langchain.ex_03_tools_hitl.main

# LangGraph — o porte do workflow de resolução
uv run python exemplos_langgraph/main.py
```

Cada trilha tem README próprio com o mapa de conceitos e as pegadinhas do porte: [`exemplos_langchain/`](./exemplos_langchain/README.md) e [`exemplos_langgraph/`](./exemplos_langgraph/README.md).

O equivalente do `adk web` no ecossistema LangChain é o `langgraph dev`, que sobe uma API local e é inspecionada pelo LangGraph Studio. Os 12 grafos das duas trilhas estão declarados num `langgraph.json` único:

```bash
cd exemplos_langchain && uv run langgraph dev
```

**Não existe equivalente ao `adk run`** — não há REPL de terminal no LangChain. Por isso os exemplos das trilhas complementares têm sempre um `main.py`: rodar o script *é* o modo CLI de trabalhar.

## 🧭 Mapa de conceitos

Cada linha é um conceito, na ordem em que aparece nas aulas. A coluna do ADK é o exemplo principal; as outras duas são o mesmo conceito reescrito.

| # | Conceito | ADK — `agents/` | LangChain | LangGraph |
|---|---|---|---|---|
| 01 | Agente mínimo | `meu_agente1` | `ex_01_agente_minimo` | |
| 02 | Instrução e escolha de modelo | `meu_agente2` | `ex_02_modelo_instrucao` | |
| 03 | Tools + aprovação humana (HITL) | `operador_conta` | `ex_03_tools_hitl` | |
| 04 | Delegação por transfer | `operador_conta_subagent` | `ex_04_handoffs` | |
| 05 | Sub-agente como ferramenta | `operador_conta_agenttool` | `ex_05_subagente_tool` | |
| 06 | Sub-agente de passagem única | `operador_conta_single_turn` | `ex_06_subagente_oneshot` | |
| 07 | Sub-agente que pede esclarecimento | `operador_conta_task` | `ex_07_subagente_clarificacao` | |
| 08 | Sessão e persistência | `operador_conta_session` | `ex_08_sessao` | |
| 09 | Estado e prompt dinâmico | `operador_conta_session_state` | `ex_09_estado` | |
| 10 | Plugins e callbacks | `ticket_receptionist` | `ex_10_recepcao_middleware` | |
| 11 | Tools de um servidor MCP | `mcp_clients/linear_mcp.py` | `ex_11_mcp` | |
| 12 | Grafo, rota por código e pausa | `ticket_resolution` | | `exemplos_langgraph/` |

A comparação de **arquitetura** entre os três — o que cada framework decide por você, onde mora o estado, quem manda pausar — está em [`docs/04`](./docs/04-adk-langchain-langgraph-comparacao.md).

## 🛠️ Estrutura do Projeto

```text
dev-agents-ia/
├── agents/                          # 🅐 trilha principal — ADK 2.x
│   ├── meu_agente1/                 #    agente mínimo
│   ├── meu_agente2/                 #    instrução e escolha de modelo
│   ├── operador_conta*/             #    tools, HITL, composição, sessão, estado
│   ├── ticket_receptionist/         #    plugins, callbacks e subagente classificador
│   │   ├── plugins.py               #    ModelRetryPlugin (retry de resposta vazia)
│   │   └── subagents/
│   └── ticket_resolution/           #    Workflow: rota por código, agentes como nós, pausa
│       ├── agent.py                 #    a montagem do grafo (edges)
│       ├── nodes.py                 #    os nós determinísticos
│       ├── agents/                  #    atendente, investigador, escalonador, conta
│       └── tools/
├── exemplos_langchain/              # 🅑 os mesmos conceitos em LangChain 1.x
│   ├── acme/                        #    domínio compartilhado (dados e tools)
│   ├── ex_01..ex_11/                #    um exemplo por conceito
│   ├── langgraph.json               #    declara os 12 grafos para o `langgraph dev`
│   ├── verificar_exemplos.py        #    12 casos, caminho feliz com LLM
│   └── verificar_bordas.py          #    17 casos de borda
├── exemplos_langgraph/              # 🅒 o ticket_resolution em StateGraph
│   ├── grafo/                       #    estado, nós, agentes e a montagem
│   └── verificar.py                 #    30 asserções
├── docs/                            # material de aprofundamento (ver abaixo)
├── db/                              # SQLAlchemy: engine, models e repositório
├── mcp_clients/                     # clientes MCP (Linear e conta)
├── outside/                         # os "sistemas externos": billing, status, conta
├── scripts/lcdoc.py                 # lê a doc do LangChain resolvendo os snippets
├── web.py                           # a aplicação completa (recepção + resolução)
├── api_tickets.http                 # requisições prontas para o fluxo acima
├── docker-compose.yml               # PostgreSQL (opcional)
└── .env.example
```

## ✅ Verificação

As trilhas complementares trazem verificadores que rodam os exemplos de ponta a ponta e conferem **efeito observável** — não só que o processo não quebrou:

```bash
uv run python -m exemplos_langchain.verificar_exemplos   # 12 casos (chama o LLM)
uv run python -m exemplos_langchain.verificar_bordas     # 17 casos de borda
uv run python exemplos_langgraph/verificar.py            # 30 asserções
```

Saída de LLM é estocástica: trate "passou" como evidência, não como garantia. Cada README traz a seção *O que continua sem cobertura*.

## 📚 Documentação

| Documento | Assunto |
|---|---|
| [01 — Carregamento de agentes](./docs/01-adk-run-carregamento-de-agentes.md) | como `adk run`, `adk web` e `adk api_server` descobrem e importam um agente |
| [02 — Subagents](./docs/02-subagents.md) | as formas de delegar tarefa entre agentes e quando usar cada uma |
| [03 — Runtime do ADK](./docs/03-adk-runtime-app-runner-aula.md) | `App`, `Runner`, `InvocationContext` e o fluxo de eventos |
| [04 — ADK × LangChain × LangGraph](./docs/04-adk-langchain-langgraph-comparacao.md) | comparação de arquitetura: camadas, estado, roteamento, HITL e extensão |

A pasta `docs/` também guarda **clones locais** da documentação e do código-fonte upstream (ADK, LangChain, LangGraph), para consulta offline.

## 📖 Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Framework principal | Google ADK 2.2 |
| Frameworks comparados | LangChain 1.x, LangGraph |
| Modelos | Gemini (`gemini-2.5-flash`), com LiteLLM para outros provedores |
| Integração externa | MCP (Model Context Protocol) — Linear e servidor próprio |
| API | FastAPI + Uvicorn |
| Persistência | SQLAlchemy · SQLite (default) · PostgreSQL 16 (opcional) |
| Ambiente | uv, Python 3.11+ |
