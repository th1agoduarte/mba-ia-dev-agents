"""Casos de borda: ramos de erro e persistência entre processos.

Complementa `verificar.py` (que exercita o caminho feliz de cada exemplo com LLM
de verdade). Aqui a maior parte NÃO chama modelo: as tools são invocadas direto,
então é determinístico e rápido.

    uv run python -m exemplos_langchain.verificar_bordas
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import inspect
from typing import cast

from langchain.agents.middleware import ToolCallRequest
from langchain.tools import ToolRuntime

from exemplos_langchain.acme import dados, tools
from exemplos_langchain.ex_07_subagente_clarificacao.agente import aplicar_troca_de_plano
from exemplos_langchain.ex_10_recepcao_middleware.agente import (
    JaRegistradoError,
    _tratar_erro_de_tool,
)

RESULTADOS: list[tuple[bool, str, str]] = []


def checar(nome: str, obtido, esperado) -> None:
    ok = obtido == esperado
    RESULTADOS.append((ok, nome, "" if ok else f"esperado {esperado!r}, veio {obtido!r}"))


# --- ramos de erro das tools (sem LLM) ---------------------------------------

checar(
    "listar_faturas: cliente inexistente devolve lista vazia",
    tools.listar_faturas.invoke({"cliente_id": "cliente_999"}),
    {"faturas": []},
)

checar(
    "consultar_assinatura: cliente inexistente",
    tools.consultar_assinatura.invoke({"cliente_id": "cliente_999"}),
    {"erro": "cliente não encontrado"},
)

checar(
    "cancelar_assinatura: senha incorreta",
    tools.cancelar_assinatura.invoke({"cliente_id": "cliente_123", "senha": "errada"}),
    {"status": "nao_cancelada", "motivo": "senha incorreta"},
)

checar(
    "cancelar_assinatura: senha errada NÃO altera o dado",
    dados.ASSINATURAS["cliente_123"]["status"],
    "ativa",
)

checar(
    "cancelar_assinatura: cliente inexistente com senha certa",
    tools.cancelar_assinatura.invoke(
        {"cliente_id": "cliente_999", "senha": dados.SENHA_VALIDA}
    ),
    {"status": "nao_cancelada", "motivo": "cliente não encontrado"},
)

checar(
    "aplicar_troca_de_plano: plano inválido",
    aplicar_troca_de_plano.invoke(
        {"cliente_id": "cliente_123", "novo_plano": "Platinum"}
    ),
    {"status": "recusada", "motivo": "plano inválido: Platinum"},
)

checar(
    "aplicar_troca_de_plano: plano inválido NÃO altera o dado",
    dados.ASSINATURAS["cliente_123"]["plano"],
    "Pro",
)

checar(
    "aplicar_troca_de_plano: cliente inexistente",
    aplicar_troca_de_plano.invoke({"cliente_id": "cliente_999", "novo_plano": "Basic"}),
    {"status": "recusada", "motivo": "cliente não encontrado"},
)

# --- contrato do ToolErrorMiddleware -----------------------------------------
# O middleware chama `on_error(exc, request)` — DOIS argumentos. Uma versão de um
# argumento só estoura TypeError na hora do erro, e um teste de comportamento
# ("não criou ticket duplicado") NÃO pega isso: o modelo satisfaz a asserção só
# por não chamar a tool de novo. Por isso a aridade é verificada aqui, direto.

checar(
    "on_error: aceita exatamente (excecao, requisicao)",
    len(inspect.signature(_tratar_erro_de_tool).parameters),
    2,
)
# Uma requisição de mentira, só para respeitar o contrato do middleware. A função
# não toca no argumento — o que importa aqui é a assinatura aceitar os dois.
_requisicao = ToolCallRequest(
    tool_call={"name": "registrar_ticket", "args": {}, "id": "call-1", "type": "tool_call"},
    tool=None,
    state={},
    runtime=cast("ToolRuntime", None),
)

checar(
    "on_error: erro de negócio vira mensagem para o modelo",
    _tratar_erro_de_tool(JaRegistradoError("ticket já existe"), _requisicao),
    "ticket já existe",
)
checar(
    "on_error: erro desconhecido NÃO é serializado (propaga)",
    _tratar_erro_de_tool(KeyError("chave interna"), _requisicao),
    None,
)

# --- guard de configuração ---------------------------------------------------

# GOOGLE_API_KEY="" já está em os.environ, e load_dotenv(override=False) não
# sobrescreve o que já existe — então o .env da raiz não "salva" o processo.
_sem_chave = subprocess.run(
    [sys.executable, "-c", "import exemplos_langchain.acme.config"],
    cwd=Path(__file__).resolve().parents[1],
    capture_output=True,
    text=True,
    env={**os.environ, "GOOGLE_API_KEY": "", "GEMINI_API_KEY": ""},
)
checar(
    "config.py: sem chave, o import ABORTA (exit != 0)",
    _sem_chave.returncode != 0,
    True,
)
checar(
    "config.py: e a mensagem diz o que fazer",
    "GOOGLE_API_KEY não encontrada" in _sem_chave.stderr,
    True,
)

# --- ramos de erro do ex_09, que lê o cliente do CONTEXTO ---------------------
# Estas tools recebem `ToolRuntime` injetado pelo framework, então não dá para
# invocá-las direto: o caminho é passar um contexto com cliente inexistente.

from exemplos_langchain.ex_09_estado.agente import Contexto  # noqa: E402
from exemplos_langchain.ex_09_estado.agente import agente as agente_estado  # noqa: E402

_r = agente_estado.invoke(
    {"messages": [{"role": "user", "content": "Quais são as minhas faturas?"}]},
    config={"configurable": {"thread_id": "borda-cliente-inexistente"}},
    context=Contexto(cliente_id="cliente_999"),
)
_texto_ferramentas = " ".join(
    str(m.content) for m in _r["messages"] if m.type == "tool"
)
checar(
    "ex_09: contexto com cliente inexistente NÃO devolve faturas de outro cliente",
    "fatura_00" in _texto_ferramentas,
    False,
)

# --- persistência entre PROCESSOS (a razão de existir o SqliteSaver) ---------

_ESCRITOR = """
import sqlite3, sys
from langgraph.checkpoint.sqlite import SqliteSaver
from exemplos_langchain.ex_08_sessao.agente import criar_agente

conn = sqlite3.connect(sys.argv[1], check_same_thread=False)
saver = SqliteSaver(conn); saver.setup()
agente = criar_agente(saver)
agente.invoke(
    {"messages": [{"role": "user", "content": "Oi, meu nome é Ana e sou a cliente_123."}]},
    config={"configurable": {"thread_id": "restart"}},
)
conn.commit(); conn.close()
print("ESCREVEU")
"""

_LEITOR = """
import sqlite3, sys
from langgraph.checkpoint.sqlite import SqliteSaver
from exemplos_langchain.ex_08_sessao.agente import criar_agente

conn = sqlite3.connect(sys.argv[1], check_same_thread=False)
agente = criar_agente(SqliteSaver(conn))
estado = agente.get_state({"configurable": {"thread_id": "restart"}})
print("MENSAGENS", len(estado.values.get("messages", [])))
r = agente.invoke(
    {"messages": [{"role": "user", "content": "Qual é o meu nome?"}]},
    config={"configurable": {"thread_id": "restart"}},
)
print("RESPOSTA", r["messages"][-1].text.replace(chr(10), " "))
"""


def _rodar(codigo: str, banco: str) -> str:
    proc = subprocess.run(
        [sys.executable, "-c", codigo, banco],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=300,
    )
    return proc.stdout + proc.stderr


_tmp = tempfile.mkdtemp()
try:
    _banco = str(Path(_tmp) / "restart.sqlite")
    _saida_escrita = _rodar(_ESCRITOR, _banco)
    checar("SqliteSaver: processo 1 gravou", "ESCREVEU" in _saida_escrita, True)

    _saida_leitura = _rodar(_LEITOR, _banco)
    _tem_historico = any(
        linha.startswith("MENSAGENS") and int(linha.split()[1]) >= 2
        for linha in _saida_leitura.splitlines()
    )
    checar(
        "SqliteSaver: processo 2 (novo interpretador) leu o histórico",
        _tem_historico,
        True,
    )
    checar(
        "SqliteSaver: processo 2 lembra do nome dito no processo 1",
        "Ana" in _saida_leitura,
        True,
    )
finally:
    shutil.rmtree(_tmp, ignore_errors=True)


# --- placar ------------------------------------------------------------------

_falhas = [r for r in RESULTADOS if not r[0]]
for ok, nome, detalhe in RESULTADOS:
    print(f"{'passou' if ok else 'FALHOU'}  {nome}")
    if detalhe:
        print(f"          {detalhe}")
print(f"\n{len(RESULTADOS) - len(_falhas)}/{len(RESULTADOS)} casos de borda passaram")
sys.exit(1 if _falhas else 0)
