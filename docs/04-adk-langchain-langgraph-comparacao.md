# ADK, LangChain e LangGraph — como cada um pensa

Comparação conceitual. O mapa API-a-API (`sub_agents` vira o quê, `output_schema`
vira o quê) está no README de `exemplos_langchain/`; aqui é só o **porquê**.

---

## TL;DR

Duas ideias explicam quase todas as diferenças.

**1. Não são três coisas equivalentes.** ADK é um framework. LangChain e LangGraph
são duas camadas do mesmo framework — o `create_agent` é um grafo LangGraph
pré-montado. Escolher entre eles não é escolher produto, é escolher altitude.

```text
ADK                          LangChain / LangGraph
─────────────────────────    ──────────────────────────────
Agent      (LLM em laço)  ≈  create_agent      ← camada alta
Workflow   (grafo)        ≈  StateGraph        ← camada baixa
   ↑ tipos irmãos               ↑ um roda sobre o outro
```

**2. O ADK decide mais por você.** Ele é co-autor do seu agente: escreve parte do
prompt que o modelo recebe. O LangChain é executor: manda o que você escreveu e
não acrescenta nada. Começar rápido de um lado, prever do outro.

O resto do documento desdobra essas duas.

---

## 1. Camadas, não produtos

O `create_agent` te dá um laço fixo: o modelo chama tools, o resultado volta para
ele, repete até parar de chamar. Quem decide o caminho é sempre o LLM.

Isso serve para a maioria dos agentes. Deixa de servir quando você precisa de rota
decidida por código, etapa determinística no meio do fluxo, ou pausa fora de uma
tool call. Aí você desce para o `StateGraph` — sem trocar de framework e sem
reescrever as tools.

No ADK a divisão é entre dois tipos irmãos: `Agent` para o laço, `Workflow` para o
grafo. Mesma biblioteca, APIs diferentes.

## 2. Quanto do seu agente está no seu código

### O ADK é co-autor

Você declara `sub_agents=[consultor_faturas, consultor_assinaturas]` — duas
linhas. Na hora da chamada, o ADK escreve várias mais e as manda ao modelo junto
com a sua instrução:

- apresenta o agente ("você se chama X, sua descrição é Y");
- lista os especialistas disponíveis, com nome e descrição;
- explica quando delegar e ordena que a delegação seja uma chamada de ferramenta;
- cria essa ferramenta (`transfer_to_agent`) e a registra.

**É isso que o autoflow é.** Boas `description` e o roteamento funciona, sem você
escrever lógica de roteamento. O preço é que o prompt que o modelo recebe não está
em lugar nenhum do seu código.

O padrão se repete: pedir `output_schema` junto de tools faz o ADK inventar uma
ferramenta e um parágrafo de instrução para garantir a saída estruturada.

### O LangChain é executor

O `create_agent` pega o seu `system_prompt` e o coloca na frente das mensagens. Só
isso. Nada é acrescentado, nenhuma ferramenta aparece sem você declarar.

Por isso não existe `sub_agents`: se você quer que um especialista assuma a
conversa, escreve a ferramenta de transferência e a regra de troca. É mais código
— e é código que você lê, versiona e testa.

### O que cada escolha otimiza

| | ADK | LangChain |
|---|---|---|
| Filosofia | o framework colabora | o framework executa |
| Roteamento multi-agente | vem pronto | você escreve |
| Onde está o prompt efetivo | montado em runtime | no arquivo que você abriu |
| Comportamento estranho | inspecionar o que o framework montou | ler o código basta |
| Começar rápido | ✅ | |
| Prever e auditar | | ✅ |

Nenhum é melhor em abstrato. Protótipo com cinco especialistas sai mais rápido no
ADK. Sistema que alguém vai depurar às três da manhã tende a doer menos quando o
prompt está no `git`.

A mesma filosofia aparece na extensão. No ADK, um plugin é um gancho numa cadeia
interna. No LangChain, um middleware vira **um nó do grafo** — com nome, visível
no desenho, inspecionável passo a passo. Por isso `create_agent` e `StateGraph`
não são mundos separados: o agente já é um grafo, e descer de camada é passar a
declarar os nós você mesmo.

<details>
<summary>Onde conferir isso no fonte</summary>

- ADK: `flows/llm_flows/single_flow.py` monta a cadeia de processadores que mutam
  o request; `auto_flow.py` acrescenta o `agent_transfer` a ela. O texto de
  roteamento está em `agent_transfer.py::_build_transfer_instruction_body`, a
  apresentação do agente em `identity.py`, e a ferramenta sintética de saída
  estruturada em `_output_schema_processor.py`.
- LangChain: `agents/factory.py` — a montagem das mensagens é
  `messages = [request.system_message, *messages]`; os nós de middleware são
  criados logo abaixo, com nomes como `<middleware>.before_model`.

</details>

## 3. Um dicionário contra dois conceitos

No ADK tudo mora em `session.state`: o `cliente_id` semeado na criação da sessão,
o resultado que uma tool gravou, a saída do agente. Um dicionário plano, lido com
`tool_context.state.get(...)` e injetado no prompt com `{chave}`.

O LangChain divide isso em dois, e a divisão é útil:

- **`context`** — o que veio de fora e o agente não descobriu: quem é o usuário,
  conexão de banco, feature flags. Passado a cada `invoke`, **não** persistido. É
  injeção de dependência.
- **`state`** — o que a execução produziu e precisa sobreviver ao turno. Vive no
  checkpoint.

Duas consequências. A escrita fica explícita: a tool não atribui na hora, ela
devolve um `Command(update=...)` que o grafo aplica — mais verboso, mais
auditável. E não existe template de estado no prompt: `system_prompt` é string
fixa, então prompt que varia com o estado se faz com middleware, e você passa a
controlar o caso "o dado ainda não existe".

Num fluxo em grafo há mais uma diferença. O ADK passa a saída de um nó ao seguinte
implicitamente (`node_input`); o LangGraph não passa nada — cada nó lê do estado o
que precisa. Parece burocracia e é a maior melhoria de legibilidade: lendo a
definição do estado você sabe tudo que circula.

## 4. Quem manda pausar

No ADK a tool sabe que existe aprovação: ela chama `request_confirmation()` por
dentro e se suspende.

No LangChain a tool volta a ser só a ação. Quem pausa é o middleware, que
intercepta a chamada antes de executá-la, comparando-a com uma política declarada
no agente (`interrupt_on={"cancelar_assinatura": True}`). O humano pode aprovar,
editar os argumentos, recusar ou responder no lugar da tool.

No LangGraph, mais abaixo, `interrupt()` pausa em qualquer ponto de qualquer nó —
não precisa haver tool call nenhuma.

**A pegadinha que a inversão cria:** o middleware só dispara se o modelo
efetivamente **chamar** a tool. Se ele "pede confirmação" educadamente em texto —
comportamento comum —, não há o que interceptar e nada pausa. A instrução precisa
mandar executar direto.

Nos dois frameworks, pausar exige persistência, e o efeito precisa ser
idempotente: retomar pode reexecutar código que já rodou.

## 5. O que vem pronto e o que você escreve

O ADK oferece **ganchos vazios** — callbacks e plugins marcam a posição, a
política é sua. O `ModelRetryPlugin` do `ticket_receptionist` são 96 linhas para
detectar resposta vazia, remontar o request e tentar de novo.

O LangChain traz middleware pronto para o mesmo problema: `ModelRetryMiddleware()`
— com backoff exponencial e jitter, que a versão artesanal não tinha. Junto vêm
`HumanInTheLoopMiddleware`, `ToolErrorMiddleware`, `ToolRetryMiddleware`,
`SummarizationMiddleware`, `PIIMiddleware`, `ModelFallbackMiddleware`, limites de
chamada, e outros.

A inversão da seção 2 aparece de novo, ao contrário: aqui é o LangChain que
entrega comportamento pronto, e o ADK que espera você escrever.

Uma diferença de projeto no tratamento de erro vale registrar: o
`ToolErrorMiddleware` é **opt-in** — você devolve mensagem só para os erros que
reconhece, e o resto propaga. O `on_tool_error_callback` do ADK captura tudo,
então um `KeyError` acidental vira texto para o cliente.

## 6. Persistência e identidade da conversa

No ADK você cria a sessão e recebe um id. No LangChain/LangGraph **você escolhe o
id** (`thread_id`) e a conversa passa a existir no primeiro `invoke` — não existe
"sessão não encontrada", um id desconhecido é só uma conversa vazia. O componente
que grava chama-se `checkpointer` em vez de `SessionService`, com as mesmas três
opções de sempre: memória, SQLite, banco.

## 7. O modo de trabalhar

O `adk web` serve a própria interface e descobre os agentes varrendo pastas. O
equivalente, `langgraph dev`, sobe só a API local; a interface é o Studio,
hospedado, que aponta para a sua máquina — e a lista de agentes é declarada num
`langgraph.json`, não descoberta.

Mas a diferença que mais muda a rotina é outra: **não existe equivalente ao
`adk run`.** Não há REPL de terminal, nem `--replay`. Por isso, rodar o exemplo
localmente é o modo CLI de trabalhar: o que seria `adk run operador_conta` vira
`uv run python -m ex_03_tools_hitl.main`.

Isso não é contorno. O agente é um objeto Python comum, então o cliente de
terminal é o seu próprio script — e você ganha o que um REPL genérico não daria:
montar o cenário antes de falar com o agente, imprimir só o que interessa, e
decidir em código o que fazer com uma pausa.

## 8. Como escolher a altitude

Vale para os dois frameworks, trocando os nomes:

| Situação | ADK | LangChain / LangGraph |
|---|---|---|
| Uma tarefa, algumas tools, LLM decide | `Agent` | `create_agent` |
| Coordenador delega e usa o resultado | `AgentTool` | subagente como `@tool` |
| Especialista conversa com o usuário | `sub_agents` + transfer | handoffs |
| Etapa determinística ou rota por código | `Workflow` | `StateGraph` |
| Pausa fora de uma tool call | `RequestInput` num nó | `interrupt()` num nó |

## 9. Onde ver cada coisa neste repositório

| Conceito | ADK | Porte |
|---|---|---|
| tools e aprovação humana | `agents/operador_conta` | `exemplos_langchain/ex_03_tools_hitl` |
| transfer entre especialistas | `agents/operador_conta_subagent` | `exemplos_langchain/ex_04_handoffs` |
| especialista que devolve valor | `agents/operador_conta_agenttool` | `exemplos_langchain/ex_05_subagente_tool` |
| sessão e persistência | `agents/operador_conta_session` | `exemplos_langchain/ex_08_sessao` |
| contexto e estado | `agents/operador_conta_session_state` | `exemplos_langchain/ex_09_estado` |
| plugins e callbacks | `agents/ticket_receptionist` | `exemplos_langchain/ex_10_recepcao_middleware` |
| tools de um servidor MCP | `mcp_clients/linear_mcp.py` | `exemplos_langchain/ex_11_mcp` |
| grafo com rota e pausa | `agents/ticket_resolution` | `exemplos_langgraph/` |

O mapa detalhado de conceitos, com as pegadinhas de cada porte, está em
`exemplos_langchain/README.md`.
