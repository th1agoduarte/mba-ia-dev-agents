# LangChain para quem já conhece o ADK

> Comparação de arquitetura entre os três frameworks (ADK, LangChain, LangGraph):
> [`docs/04-adk-langchain-langgraph-comparacao.md`](../docs/04-adk-langchain-langgraph-comparacao.md).
> Este README é o mapa exemplo-a-exemplo.

Porte dos exemplos de `agents/` (Google ADK) para LangChain 1.x, mantendo o mesmo
domínio — o atendimento de conta da Acme — para que a comparação seja direta.

Validado com `langchain 1.3.14`, `langgraph 1.2.10`, `langchain-google-genai 4.3.2`
e os mesmos modelos Gemini usados nos exemplos ADK.

---

## 1. Instalação

O LangChain 1.x é um pacote fino sobre o LangGraph. Você instala três camadas:

```bash
uv add langchain                      # create_agent, tools, middleware
uv add langchain-google-genai         # a integração do provedor (Gemini)
uv add langgraph-checkpoint-sqlite    # persistência de conversa em disco
uv add langchain-mcp-adapters         # tools vindas de servidores MCP (ex_11)
```

- `langchain` já traz `langchain-core` e `langgraph` como dependências.
- **A integração do provedor é um pacote separado.** Não existe "langchain com
  todos os modelos": cada provedor tem o seu (`langchain-openai`,
  `langchain-anthropic`, ...). É o que substitui o LiteLLM do ADK.
- Checkpointers persistentes também são pacotes à parte
  (`langgraph-checkpoint-sqlite`, `langgraph-checkpoint-postgres`). O
  `InMemorySaver` já vem no `langgraph`.

Cuidado com um nome: **`langchain-classic`** é o LangChain 0.x (chains, agents
antigos), mantido só para quem não migrou. Não é o que você quer. No monorepo do
projeto, o pacote publicado como `langchain` tem o código em `libs/langchain_v1/`,
enquanto `libs/langchain/` é o `langchain-classic`.

## 2. Configuração

A credencial é lida do ambiente na hora de **construir o modelo** — antes de
qualquer chamada de rede. Sem ela, `create_agent(...)` estoura um
`ValidationError` do pydantic, não um erro de autenticação.

```python
from dotenv import load_dotenv
load_dotenv()                 # precisa vir ANTES de create_agent
```

Duas armadilhas:

- `load_dotenv()` sem argumento procura o `.env` subindo a partir do **arquivo
  que chama**, não do diretório de trabalho. Em `acme/config.py` apontamos para a
  raiz do repo explicitamente.
- O provedor Gemini aceita `GOOGLE_API_KEY` ou `GEMINI_API_KEY`.

> **Gemini ou Anthropic.** `acme/config.py` respeita o mesmo `MODEL_PROVIDER` do
> `.env` da raiz usado pelos agentes ADK: `gemini` (padrão) ou `anthropic`. Em
> modo `anthropic`, `MODELO_RAPIDO`/`MODELO_PADRAO` viram `anthropic:claude-...`
> e é preciso `uv add langchain-anthropic` + `ANTHROPIC_API_KEY`. As variáveis
> de modelo por agente (`<NOME>_MODEL`) são só dos agentes ADK; aqui o modelo
> vem do `config.py`.

O modelo é declarado de duas formas:

```python
create_agent(model="google_genai:gemini-3.1-flash-lite")     # string "provider:modelo"
create_agent(model=init_chat_model("...", temperature=0))     # objeto, quando há parâmetros
```

A string é resolvida por `init_chat_model`. Note que `request.override(model=...)`
dentro de middleware **exige o objeto** — string quebra com
`AttributeError: 'str' object has no attribute 'bind_tools'`.

## 3. Organização de arquivos e pastas

A convenção oficial (`oss/langgraph/application-structure`) é orientada a deploy
no LangSmith:

```text
my-app/
├── my_agent/
│   ├── utils/
│   │   ├── tools.py      # ferramentas
│   │   ├── nodes.py      # funções de nó do grafo
│   │   └── state.py      # definição do estado
│   └── agent.py          # construção do grafo
├── .env
├── langgraph.json        # dependências, grafos e env do deploy
└── pyproject.toml
```

O `langgraph.json` só é necessário para `langgraph dev` / LangGraph Studio /
LangSmith Deployment. Para rodar como biblioteca — que é o caso destes exemplos e
provavelmente o seu — ele é dispensável.

O que vale como prática, independente de deploy:

- **Separe domínio de agente.** `acme/dados.py` não importa LangChain. Isso
  permite testar a regra de negócio sem LLM, e é o que evita que os 11 exemplos
  repitam a mesma lista de faturas (como acontece hoje em `agents/`).
- **Ferramentas em módulo próprio.** A docstring da tool é o que o modelo lê;
  tratá-la como prompt, e não como comentário, muda a qualidade do roteamento.
- **Exporte fábricas, não instâncias**, quando algo varia por processo. Em
  `ex_08_sessao/agente.py` o checkpointer muda entre script, API e teste, então o
  módulo exporta `criar_agente(checkpointer)`.
- **Estado em classe própria** (`class X(AgentState)`) junto do agente que o usa.

### Estrutura deste diretório

```text
exemplos_langchain/
├── acme/                  # domínio compartilhado (sem LangChain em dados.py)
│   ├── config.py          # .env + escolha de modelo
│   ├── dados.py           # FATURAS, ASSINATURAS, funções puras
│   └── tools.py           # as @tool
└── ex_NN_conceito/
    ├── agente.py          # o agente e o conceito da aula
    └── main.py            # como executar
```

O prefixo `ex_` existe por um motivo prático: `01_agente_minimo` não é um
identificador Python válido, então não daria para `import`. Com `ex_01_...` os
exemplos são pacotes de verdade e a ordem de leitura continua óbvia.

## 4. Como rodar

Sempre a partir da **raiz do repositório** — os imports são absolutos a partir
dela (`from exemplos_langchain.acme.config import ...`), então é a raiz que
precisa estar no `sys.path`:

```bash
uv run python -m exemplos_langchain.ex_01_agente_minimo.main
uv run python -m exemplos_langchain.ex_03_tools_hitl.main
uv run python -m exemplos_langchain.ex_03_tools_hitl.main recusar
uv run uvicorn exemplos_langchain.ex_08_sessao.web:app --port 8000
```

Rodar pelo caminho do arquivo também funciona (`uv run python
exemplos_langchain/ex_01_agente_minimo/main.py`): o `uv run` coloca a raiz do
projeto como primeira entrada do `sys.path`. Fora do `uv run`, aí sim só o `-m`
resolve — por isso os exemplos são documentados nessa forma.

### O `ex_11_mcp` roda diferente

É o único exemplo assíncrono da trilha, e isso não é estilo:

- carregar as tools do servidor MCP é I/O de rede (`await client.get_tools()`),
  então o agente só existe dentro de uma corrotina — o módulo exporta
  `async def criar_agente()` em vez de um `agente` pronto no topo;
- tools de MCP são assíncronas, então a conversa exige `await agente.ainvoke(...)`.
  Chamar `.invoke()` síncrono falha na hora de executar a tool.

Ele também é o único que fala com um serviço externo real (o Linear), e por isso
tem dois modos:

```bash
uv run python -m exemplos_langchain.ex_11_mcp.main          # somente leitura
uv run python -m exemplos_langchain.ex_11_mcp.main criar    # ABRE UM ISSUE REAL
```

O padrão da fábrica é `permitir_escrita=False`: sem o argumento explícito, a tool
de escrita nem é carregada. Uma alucinação do modelo não vira issue no Linear de
alguém.

## 4.1. Inspecionar os agentes no Studio (`langgraph dev`)

É o equivalente do `adk web`. Enquanto o `adk web` descobre os agentes varrendo
pastas, aqui a lista é declarada num arquivo: o **`langgraph.json`**.

### O `langgraph.json`

```json
{
  "dependencies": ["langchain", "langchain-google-genai", "langchain-mcp-adapters"],
  "graphs": {
    "01_agente_minimo": "./ex_01_agente_minimo/agente.py:agente",
    "...": "...",
    "10_recepcao_middleware": "./ex_10_recepcao_middleware/agente.py:agente",
    "11_mcp_linear": "./ex_11_mcp/agente.py:criar_agente",
    "langgraph_ticket_resolution": "../exemplos_langgraph/grafo/grafo.py:grafo"
  },
  "env": "../.env"
}
```

Três chaves:

- **`graphs`** — o mapa `nome_no_Studio: "caminho/arquivo.py:variavel"`. É aqui
  que os exemplos são expostos de uma vez — hoje 12.

  A convenção de nome importa porque o nome à esquerda é o que aparece no seletor
  do Studio: os exemplos desta trilha usam o prefixo numérico (`01_`…`11_`) para
  manter a ordem da aula, e o grafo da trilha vizinha entra como
  `langgraph_ticket_resolution` — sem número, porque não faz parte da progressão.
  O caminho dele é relativo a este arquivo (`../exemplos_langgraph/...`), o que
  funciona sem precisar de um segundo `langgraph.json`.

  O valor pode ser um grafo já pronto **ou uma fábrica** — inclusive `async`, que
  é o caso do `ex_11_mcp`, cujas tools só existem depois de uma chamada de rede. O nome à esquerda é o que aparece
  no seletor do Studio, por isso o prefixo numérico: mantém a ordem da aula.
- **`dependencies`** — os pacotes que o servidor precisa ter no ambiente.
- **`env`** — de onde ler as variáveis. Aponta para o `.env` da raiz do projeto,
  o mesmo que os exemplos usam quando rodam sozinhos.

### Rodar

```bash
uv add --dev "langgraph-cli[inmem]"      # uma vez; o extra traz o servidor
cd exemplos_langchain
uv run langgraph dev --config langgraph.json
```

O `--config langgraph.json` é o valor padrão do CLI, então pode ser omitido —
deixe explícito se preferir deixar claro de onde vem a lista de agentes.

O servidor sobe e imprime três endereços:

```text
- 🚀 API:       http://127.0.0.1:2024
- 🎨 Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
- 📚 API Docs:  http://127.0.0.1:2024/docs
```

- **API** — a REST local. Criar thread, mandar mensagem, ler estado, responder
  interrupt. É o que os testes deste repositório usaram.
- **Studio UI** — a interface visual. Repare no `?baseUrl=`: a página é servida
  pela LangSmith, mas **aponta para o seu servidor local**. Lá você escolhe o
  agente, conversa com ele, vê cada passo (prompt enviado, tool calls e
  retornos), inspeciona o estado da thread e edita valores para re-executar a
  partir de um ponto.
- **API Docs** — o OpenAPI do servidor, servido localmente. Não exige conta.

Verificado: os 10 grafos carregam sem erro, e o HITL do `ex_03` pausa e persiste
corretamente pela API.

Três coisas que você precisa saber:

**Não precisa de `LANGSMITH_API_KEY` para o servidor subir.** A doc lista a chave
como pré-requisito, mas o servidor sobe sem ela — testado. A chave é exigida pela
UI (o Studio, hospedado em `smith.langchain.com`). Sem conta você ainda tem a API
REST local, que é o que os testes acima usaram.

**O servidor RECUSA grafos com checkpointer próprio.** Não é aviso, é
`GraphLoadError` e o servidor não sobe:

```text
Your graph 'agente' includes a custom checkpointer (InMemorySaver). With
LangGraph API, persistence is handled automatically by the platform...
please remove the custom checkpointer from your graph definition.
```

Por isso os exemplos usam `acme.config.checkpointer_padrao()`, que devolve
`InMemorySaver` ao rodar direto e `None` sob o servidor. A detecção é
`"langgraph_api" in sys.modules`.

**Renomear um grafo deixa o antigo para trás.** O `langgraph dev` persiste os
assistentes em `.langgraph_api/`. Depois de renomear uma chave em `graphs`, o
`langgraph validate` reporta o número certo, mas a API continua listando o nome
velho junto com o novo. Apague a pasta para limpar:

```bash
rm -rf exemplos_langchain/.langgraph_api
```

**Cada grafo precisa ser uma variável de módulo (ou uma fábrica).** O `ex_08_sessao` exporta a
fábrica `criar_agente(checkpointer)`; para o `langgraph.json` ter o que apontar,
o módulo também expõe `agente = criar_agente()`.

### Não existe equivalente ao `adk run`

O `langgraph dev` cobre o `adk web`, mas **o `adk run` não tem equivalente**.

No ADK, `adk run <pasta_do_agente>` abre uma conversa no terminal, sem browser e
sem servidor. Ele ainda traz `--save_session` (grava a sessão em json ao sair) e
`--replay` (recria a sessão a partir de um json com as perguntas do usuário —
útil para repetir um roteiro).

O `langgraph-cli` não tem nada disso. Os comandos são:

```text
build  deploy  dev  dockerfile  new  up  validate
```

Todos giram em torno de servidor, imagem ou deploy — nenhum é um chat de
terminal.

**É por isso que rodar os exemplos localmente É o modo CLI de trabalhar aqui.**
O que no ADK seria `adk run operador_conta`, aqui é:

```bash
uv run python -m exemplos_langchain.ex_03_tools_hitl.main
```

Não é um contorno: é a forma normal. Como o agente é um objeto Python comum, o
"cliente de terminal" é o seu próprio `main.py` — e você ganha o que um REPL
genérico não daria, como imprimir só o que interessa, montar o cenário antes de
falar com o agente, e decidir o que fazer com o interrupt (ver
`ex_03_tools_hitl/main.py`, que aprova ou recusa conforme o argumento).

Divisão prática:

| Você quer | Use |
|---|---|
| rodar, depurar, repetir um cenário | `uv run python -m ex_NN.main` |
| inspecionar visualmente passo a passo | `langgraph dev` + Studio |
| chamar de outro processo ou serviço | a API em `127.0.0.1:2024` |

Não há substituto direto para o `--replay` do ADK: repetir um roteiro é escrever
a lista de mensagens no seu script — como o `verificar_exemplos.py` deste
diretório faz.

Nota: `langgraph validate` checa o `langgraph.json` sem subir servidor. Útil
depois de mexer no mapa de grafos.

## 5. Mapa dos exemplos

| # | Exemplo LangChain | Equivale a `agents/` | Conceito |
|---|---|---|---|
| 1 | `ex_01_agente_minimo` | `meu_agente1` | `create_agent`, `invoke` |
| 2 | `ex_02_modelo_instrucao` | `meu_agente2` | `system_prompt`, escolha de provedor |
| 3 | `ex_03_tools_hitl` | `operador_conta` | `@tool` + `HumanInTheLoopMiddleware` |
| 4 | `ex_04_handoffs` | `operador_conta_subagent` | handoffs por estado + `wrap_model_call` |
| 5 | `ex_05_subagente_tool` | `operador_conta_agenttool` | subagente como tool |
| 6 | `ex_06_subagente_oneshot` | `operador_conta_single_turn` | subagente + `response_format` |
| 7 | `ex_07_subagente_clarificacao` | `operador_conta_task` | `interrupt()` dentro do subagente |
| 8 | `ex_08_sessao` | `operador_conta_session` | `checkpointer` + `thread_id` (+ API) |
| 9 | `ex_09_estado` | `operador_conta_session_state` | `context_schema`, `state_schema`, `@dynamic_prompt` |
| 10 | `ex_10_recepcao_middleware` | `ticket_receptionist` | `ToolErrorMiddleware`, `ModelRetryMiddleware` |
| 11 | `ex_11_mcp` | `escalator` (MCP do Linear) | `MultiServerMCPClient`, execução assíncrona |

A resolução do ticket (`agents/ticket_resolution`, um `Workflow` do ADK) está na
trilha vizinha: [`exemplos_langgraph/`](../exemplos_langgraph/README.md).

## 6. Mapa de conceitos

| ADK | LangChain | Observação |
|---|---|---|
| `Agent(...)` | `create_agent(...)` | `model` é obrigatório; `name` é opcional |
| `instruction=` | `system_prompt=` | string fixa; para variar, `@dynamic_prompt` |
| `{chave?}` na instrução | `@dynamic_prompt` | não há template de estado no prompt |
| tool = função + docstring | `@tool` | igual: a docstring é a descrição |
| `ToolContext` | `ToolRuntime` | `.context`, `.state`, `.tool_call_id`, `.store` |
| `tool_context.state[...] = v` | tool devolve `Command(update=...)` | escrita explícita |
| `request_confirmation()` na tool | `HumanInTheLoopMiddleware` | quem pausa é o middleware, não a tool |
| `sub_agents=[...]` + transfer | padrão **handoffs** | estado + `wrap_model_call` |
| `AgentTool(x)` | `@tool` que chama `x.invoke()` | não existe classe; subagente é tool |
| `mode="single_turn"` | subagente + `response_format` | sem equivalente de `mode` |
| `mode="task"` (clarificação) | `interrupt()` dentro do subagente | retoma a execução, não abre turno novo |
| `output_schema=` | `response_format=` | resultado em `["structured_response"]` |
| `output_key=` | chave do `state_schema` | via `Command(update=...)` |
| `Runner` + `App` | o próprio agente | `agente.invoke(...)` |
| `SessionService` | `checkpointer` | `InMemorySaver` / `SqliteSaver` / `PostgresSaver` |
| `session.id` | `thread_id` no `config` | você escolhe o id; não há "criar sessão" |
| `session.state` semeado | `context_schema` + `context=` | dado estático da invocação |
| `on_tool_error_callback` | `ToolErrorMiddleware(on_error=...)` | opt-in: o que você não trata, sobe |
| `plugins=[...]` (`BasePlugin`) | middleware | `ModelRetryMiddleware` já vem pronto |
| `before_model_callback` | `@before_model` / `@wrap_model_call` | |
| `after_model_callback` | `@after_model` / `@wrap_model_call` | |
| `McpToolset` | `MultiServerMCPClient` | pacote `langchain-mcp-adapters` |
| `tool_filter=[...]` | filtrar a lista de `get_tools()` | não há parâmetro; é código |
| `adk web` | LangGraph Studio (`langgraph dev`) | exige `langgraph.json` |

### Contexto x estado

A divisão que o ADK não faz e que aqui é obrigatória:

- **contexto** — vem de fora, o agente não descobriu (`cliente_id`, conexão de
  banco). Passado a cada `invoke`, **não** é persistido no checkpoint.
- **estado** — a execução produziu e precisa sobreviver ao turno (resultado da
  pesquisa). Vive no checkpoint.

No ADK os dois moram em `session.state`. Ver `ex_09_estado`.

## 7. Pegadinhas encontradas ao portar

1. **`HumanInTheLoopMiddleware` só dispara se o modelo CHAMAR a tool.** Se o
   modelo pedir confirmação em texto — comportamento comum e "educado" — não há
   tool call para interceptar e nada pausa. As instruções dos exemplos mandam
   explicitamente executar direto.
2. **A chave do interrupt é `args`, não `arguments`.** A página
   `human-in-the-loop` da doc mostra `arguments` no exemplo de saída, mas o
   `TypedDict ActionRequest` no fonte usa `args`.
3. **`version="v2"` muda o retorno do `invoke`.** Com ele você recebe um
   `GraphOutput` (`.value`, `.interrupts`); sem ele, o dicionário de estado. Só
   use `version="v2"` quando for tratar interrupt.
4. **Interrupt exige `checkpointer` e `thread_id`.** Sem checkpointer o
   `interrupt()` estoura; sem `thread_id` não há o que retomar.
5. **`request.override(model=...)` exige objeto**, não string.
6. **Tools do middleware precisam estar declaradas no `create_agent`.** O
   `wrap_model_call` escolhe um subconjunto por turno; ele não registra tools que
   o agente não conhece.
7. **Handoff precisa devolver um `ToolMessage`.** O modelo emitiu uma tool call e
   espera a resposta; sem ela o histórico fica malformado.
8. **MCP não exige o saneamento de schema que o ADK exige.** O cliente do
   projeto ADK (`mcp_clients/linear_mcp.py`) tem 40+ linhas traduzindo
   `const` → `enum` e `oneOf` → `anyOf`, porque esses keywords estouram a
   validação do ADK e somem no conversor do Gemini. O `save_issue` do Linear
   continua expondo os dois, e o binding pelo LangChain funciona sem tradução —
   o `langchain-google-genai` apenas loga `not supported, ignoring` e segue.
   Sorte de implementação, não garantia do protocolo.
9. **`on_error` do `ToolErrorMiddleware` recebe DOIS argumentos**
   (`exc, request: ToolCallRequest`). Uma versão de um argumento só estoura
   `TypeError` no momento do erro — e um teste de comportamento ("não criou
   ticket duplicado") não pega, porque o modelo satisfaz a asserção só por não
   chamar a tool de novo. O `verificar_bordas.py` checa a aridade direto.
10. **Roteamento de handoff é probabilístico.** Medindo o `ex_04`, a primeira
   versão do prompt do coordenador falhava em 1 de 4 execuções: ele respondia ao
   cliente em vez de transferir adiante. O conserto foi no texto do prompt, não
   no grafo. Vale a pena medir com várias execuções antes de dar um exemplo de
   roteamento por estável.

## 9. Verificação

Dois scripts, ambos executáveis a partir da raiz do repositório:

```bash
uv run python -m exemplos_langchain.verificar_exemplos  # caminho feliz dos 11 exemplos, com LLM real
uv run python -m exemplos_langchain.verificar_bordas    # ramos de erro e persistência (quase tudo sem LLM)
```

`verificar_exemplos.py` roda cada exemplo em processo isolado e checa efeito
observável, não exit code — por exemplo, que no `ex_03` o status siga `ativa`
durante a pausa e só vire `cancelada` após o `approve`. Resultado registrado: 3
passadas, 29/30. A única falha foi a instabilidade de roteamento do `ex_04`
(item 8 acima), corrigida em seguida.

`verificar_bordas.py` cobre 17 casos: todos os ramos de erro das tools (senha
incorreta, cliente inexistente, plano inválido), o guard de `GOOGLE_API_KEY`, o
isolamento por contexto do `ex_09` e — o mais importante — que o `SqliteSaver`
sobrevive a um **restart de processo**: um interpretador grava a conversa, outro
interpretador novo lê o histórico e continua de onde parou.

### O que continua sem cobertura

Lista honesta, para você não confiar além do que foi medido:

- Tipos de decisão `edit` e `respond` do HITL. Só `approve` e `reject` foram
  exercitados.
- **O modo `criar` do `ex_11_mcp` não foi executado.** Ele abre um issue real
  no Linear; a bateria automática roda só o caminho de leitura, que é o que
  está verificado (tools carregadas do servidor e consulta respondida).
- `PostgresSaver`: aparece apenas no mapa de conceitos, por decisão. Não há
  exemplo com Postgres aqui, embora o `operador_conta_session` do ADK use
  `DatabaseSessionService` com Postgres. O exemplo de persistência em banco é o
  `ex_08_sessao/web.py`, em SQLite.
- Troca de provedor (Anthropic, OpenAI): os pacotes não estão instalados.
- `uvicorn ex_08_sessao.web:app` pela linha de comando. A API foi testada via
  `TestClient`, que usa o mesmo app ASGI mas não valida o comando.
- `/historico` com `thread_id` inexistente.
- Concorrência: várias threads simultâneas, interrupts simultâneos.
- `ex_05` e `ex_06` dependem do status sorteado da plataforma; os dois ramos da
  instrução (disponível x indisponível) não foram forçados deliberadamente.
- Cancelamento com senha incorreta no `ex_09` (via contexto). O equivalente em
  `acme/tools.py` está coberto.

Nada disso é `pytest`: são scripts. Como a saída de LLM é estocástica, trate
"passou" como evidência, não como garantia.

