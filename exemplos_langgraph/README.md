# LangGraph: quando o grafo é seu

Porte do `agents/ticket_resolution` (ADK `Workflow`) para LangGraph, mesmo domínio
Acme Cloud, sem banco e sem serviços externos.

Se você veio de `exemplos_langchain/`, a diferença é de camada, não de produto:
o `create_agent` de lá **já é** um grafo LangGraph, só que pronto. Aqui você
desenha o seu.

## Quando descer para o LangGraph

O `create_agent` te dá um grafo fixo: modelo → tools → modelo, em laço, até o
modelo parar de chamar tools. Quem decide o caminho é sempre o LLM.

Isso deixa de servir quando você precisa de:

- **rota decidida por código**, não pelo modelo (aqui: ticket fora de escopo é
  recusado sem chamar modelo nenhum);
- **etapas determinísticas** no meio do fluxo (aqui: a soma do valor do refund);
- **agentes como peças** de um fluxo maior, e não como o fluxo inteiro;
- **pausa em ponto específico** do processo, não numa tool call.

O `ticket_resolution` tem os quatro.

## Como rodar

A partir da **raiz do repositório** — os imports são absolutos
(`from exemplos_langgraph.grafo...`), então é a raiz que precisa estar no
`sys.path`:

Precisa de `GOOGLE_API_KEY` no `.env` da raiz — três dos quatro cenários chamam
o Gemini.

```bash
uv run python exemplos_langgraph/main.py           # 4 cenários; o último aprova
uv run python exemplos_langgraph/main.py recusar   # o último recusa
uv run python exemplos_langgraph/verificar.py      # 30 asserções
```

Para inspecionar o grafo visualmente, ele também está no `langgraph dev` da
trilha vizinha, como `langgraph_ticket_resolution`:

```bash
cd exemplos_langchain && uv run langgraph dev
```

Por causa disso, `construir_grafo()` usa `acme.config.checkpointer_padrao()`:
`InMemorySaver` ao rodar direto, `None` sob o Agent Server — que injeta a
persistência e recusa carregar um grafo que traga a sua.

### Por onde começar a ler

1. `grafo/estado.py` — o contrato. Saber o que circula explica o resto.
2. `grafo/nos.py` — onde está a lógica, determinística e agêntica lado a lado.
3. `grafo/grafo.py` — a montagem; curta, porque as rotas moram nos nós.

## Estrutura

```text
exemplos_langgraph/
├── acme/
│   ├── config.py       # .env, modelos e limiares da política
│   └── dominio.py      # tickets, faturas e escalações em memória
├── grafo/
│   ├── estado.py       # o contrato: o que circula entre os nós
│   ├── agentes.py      # os 3 agentes que ocupam nós
│   ├── nos.py          # os nós determinísticos e os que chamam agentes
│   └── grafo.py        # a montagem (StateGraph)
├── main.py
└── verificar.py
```

## Topologia

```text
START → triagem ─┬─ recusar ───────────────────────────────────→ END
                 ├─ no_atendente → finalizar ──────────────────→ END
                 └─ no_investigador → triagem_refund ─┬─ refund_automatico → END
                                                      └─ no_escalonador
                                                           → triagem_escalacao ─┬─ encerrar_escalado → END
                                                                                └─ aguardar_aprovacao
                                                                                     ⏸ interrupt
                                                                                     → efetivar_refund → END
```

Quatro cenários cobrem os caminhos principais (o handoff sem aprovação,
`encerrar_escalado`, não é exercitado ponta a ponta — ver Verificação):

| Ticket | Situação | Caminho |
|---|---|---|
| `TICKET-0004` | "qual a cotação do bitcoin?" | recusa determinística, sem modelo |
| `TICKET-0003` | dúvida de onboarding | atendente |
| `TICKET-0001` | plano duplicado, $49,99 | refund automático (abaixo do limiar de $50) |
| `TICKET-0002` | ajuste de $120 sem justificativa | escala, **pausa**, e só estorna após aprovação |

## Mapa ADK → LangGraph

| ADK (`Workflow`) | LangGraph |
|---|---|
| `Workflow(edges=[...])` | `StateGraph` + `add_node` / `add_edge` |
| `(START, no, {"rota_a": …, "rota_b": …})` | `Command(goto=...)` no nó, ou `add_conditional_edges` |
| `@node async def f(ctx)` | função comum `def f(state) -> dict` |
| `Event(actions=EventActions(route=..., state_delta=...))` | `Command(goto=..., update={...})` |
| `node_input` (saída do nó anterior) | não existe: o dado passa pelo **estado** |
| `ctx.state["x"]` | `state.get("x")`, tipado no `TypedDict` |
| agente como nó | agente como nó (é um subgrafo) |
| `RequestInput(...)` | `interrupt(...)` |
| retomar com `FunctionResponse(adk_request_input)` | `Command(resume=...)` |
| `SessionService` | `checkpointer` |

### O parâmetro do nó precisa se chamar `state`

O protocolo `StateNode` do LangGraph declara o nó como `(state: T) -> Any`, e a
checagem de tipo casa **pelo nome do parâmetro**. Escrever `def triagem(estado:
EstadoResolucao)` roda perfeitamente — a chamada é posicional — mas o pyright
reclama em todo `add_node`:

```text
Parameter name mismatch: "state" versus "estado"
```

Ou seja: o nome faz parte do contrato, mesmo sem efeito em runtime. Por isso os
nós aqui recebem `state`, com o corpo em português.

Segunda consequência de tipagem: chaves `NotRequired` do `TypedDict` não podem
ser lidas com `state["x"]` — o pyright avisa que a chave pode não existir. Só
`ticket_id` é obrigatória (é a entrada do grafo); todo o resto é lido com
`state.get("x", padrao)`.

### A diferença que mais muda o código

No ADK, um nó recebe `node_input` — a saída do nó anterior — implicitamente. No
LangGraph isso não existe: cada nó devolve um dicionário parcial que é **mesclado
no estado**, e o próximo nó lê do estado o que precisar.

Parece burocrático e é melhor: a dependência entre nós fica escrita. Lendo
`grafo/estado.py` você sabe tudo que circula. No ADK você precisa rastrear qual
nó produziu o quê.

## O invariante que sustenta o fluxo

**O LLM nunca produz o valor do estorno.** O investigador aponta QUAIS linhas da
fatura são indevidas (`item_ids`); quem soma é `_somar_linhas`, em Python. Um
modelo que alucine um número não consegue causar prejuízo, porque nenhum número
vem dele.

O mesmo vale para a severidade da escalação: `_severidade` é uma tabela em
código, não um julgamento do modelo.

Os dois efeitos com dinheiro ou com carga externa — `emitir_refund` e
`criar_escalacao` — são **idempotentes por `ticket_id`**. Isso não é zelo
excessivo: um grafo que pausa pode reexecutar o corpo de um nó ao retomar, e sem
idempotência o cliente receberia o estorno duas vezes.

## Simplificações em relação ao original

Registradas para você não esperar o que não está aqui:

- **Sem banco.** `db/repo.py` virou dicionário em memória (`acme/dominio.py`).
- **Sem Linear.** O escalonador grava um card local em vez de abrir issue via
  MCP, para a trilha rodar sem rede. A idempotência por `ticket_id`, que é a
  parte interessante, foi preservada. MCP de verdade está em
  `exemplos_langchain/ex_11_mcp`, contra o mesmo servidor do Linear.
- **Sem `account_operator` aninhado.** No original o atendente chamava um
  sub-agente via `AgentTool` para ações de conta; aqui ele tem a tool
  `adicionar_membro` direto. O padrão de subagente já está no
  `exemplos_langchain/ex_05_subagente_tool`.
- **Sem webhook de aprovação.** A retomada é feita no `main.py` com
  `Command(resume=...)`. Ligar isso a um endpoint HTTP é o mesmo padrão do
  `exemplos_langchain/ex_08_sessao/web.py`.

## Verificação

`verificar.py` cobre 30 casos. Os 17 primeiros são determinísticos (não chamam
modelo): cálculo do refund em todos os ramos, tabela de severidade e idempotência
dos dois efeitos. Os 13 finais rodam os cenários ponta a ponta com Gemini,
checando efeito observável — inclusive que **nada é estornado durante a pausa** e
que a recusa não estorna.

### O que continua sem cobertura

- Checkpointer persistente: o grafo usa `InMemorySaver`. A troca por `SqliteSaver`
  está demonstrada em `exemplos_langchain/ex_08_sessao/web.py`.
- Reexecução do corpo de um nó após retomada: a idempotência está testada
  isoladamente (`emitir_refund` chamado duas vezes), mas não forcei o cenário de
  crash e replay.
- Concorrência: dois tickets pausados ao mesmo tempo.
- O ramo `acima_do_teto` chegando ao grafo ponta a ponta: está coberto no nível da
  função `_somar_linhas`, mas nenhum ticket de exemplo o dispara pelo fluxo
  completo.
- Estabilidade: 3 passadas completas. Saída de LLM é estocástica; trate "passou"
  como evidência, não garantia.
