"""Re-roda todos os exemplos em processos limpos e apura efeitos observáveis.

Cada exemplo roda isolado (subprocess) para que o estado mutável de acme.dados
não vaze de um para o outro. Além do exit code, checamos um EFEITO concreto na
saída — exit 0 com resposta errada não conta como passou.
"""

import re
import subprocess
import sys
import time
from pathlib import Path

# Os exemplos usam imports absolutos a partir da raiz do repositório
# (`exemplos_langchain.ex_NN_.../...`), então os subprocessos rodam com a raiz
# como cwd — e não a pasta deste arquivo.
RAIZ = Path(__file__).resolve().parents[1]

# (módulo, args, [(rótulo, regex que precisa casar na saída)])
CASOS = [
    ("ex_01_agente_minimo.main", [], [("respondeu algo", r"[\s\S]{60,}")]),
    ("ex_02_modelo_instrucao.main", [], [("gerou código print", r"print\(")]),
    (
        "ex_03_tools_hitl.main",
        [],
        [
            ("pausou antes do efeito", r"status durante a pausa: ativa"),
            ("aprovou", r"decisão humana: approve"),
            ("efetivou só após aprovar", r"status final: cancelada"),
        ],
    ),
    (
        "ex_03_tools_hitl.main",
        ["recusar"],
        [
            ("recusou", r"decisão humana: reject"),
            ("NÃO efetivou", r"status final: ativa"),
        ],
    ),
    (
        "ex_04_handoffs.main",
        [],
        [
            ("transferiu para faturas", r"especialista ativo: faturas"),
            ("transferiu para assinaturas", r"especialista ativo: assinaturas"),
        ],
    ),
    (
        "ex_05_subagente_tool.main",
        [],
        [("delegou ao subagente após erro", r"consultar_status_plataforma")],
    ),
    (
        "ex_06_subagente_oneshot.main",
        [],
        [("saída tipada", r"tipo: StatusPlataforma"), ("campo bool", r"disponivel: (True|False)")],
    ),
    (
        "ex_07_subagente_clarificacao.main",
        [],
        [
            ("subagente perguntou", r"\[subagente pergunta\]"),
            ("retomou e aplicou", r"plano final: Enterprise"),
        ],
    ),
    (
        "ex_08_sessao.main",
        [],
        [("thread nova sem histórico", r"thread nova \(sem histórico\)")],
    ),
    (
        "ex_09_estado.main",
        [],
        [
            ("gravou pesquisa no estado", r"pesquisa_satisfacao: \{'feedback'"),
            ("sentimento negativo", r"'sentimento': 'negativo'"),
        ],
    ),
    (
        "ex_10_recepcao_middleware.main",
        [],
        [
            ("classificou como billing", r"classificação no estado: billing"),
            ("detectou pedido de refund", r"precisa_refund: True"),
            ("registrou o ticket", r"ticket registrado: TICKET-\d+"),
            ("trava impediu duplicata", r"tickets no repositório: 1 -> 1"),
            ("fallback out_of_scope", r"classificação: out_of_scope"),
        ],
    ),
    (
        # Somente leitura: o modo `criar` escreve no Linear de verdade e não
        # entra em bateria automática.
        "ex_11_mcp.main",
        [],
        [
            ("carregou tools do servidor MCP", r"tools carregadas do MCP: \['get_issue', 'list_teams'\]"),
            ("consultou o Linear de verdade", r"\[agente\][\s\S]{40,}"),
        ],
    ),
]


def rodar(modulo: str, args: list[str]) -> tuple[int, str, float]:
    inicio = time.time()
    proc = subprocess.run(
        [sys.executable, "-m", f"exemplos_langchain.{modulo}", *args],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=420,
    )
    return proc.returncode, proc.stdout + proc.stderr, time.time() - inicio


def main() -> int:
    falhas = 0
    for modulo, args, checagens in CASOS:
        rotulo = f"{modulo}{' ' + ' '.join(args) if args else ''}"
        codigo, saida, dur = rodar(modulo, args)
        problemas = []
        if codigo != 0:
            problemas.append(f"exit={codigo}")
        for nome, padrao in checagens:
            if not re.search(padrao, saida):
                problemas.append(f"faltou: {nome}")
        if problemas:
            falhas += 1
            print(f"FALHOU  {rotulo}  ({dur:.0f}s)")
            for p in problemas:
                print(f"          - {p}")
            print("        últimas linhas:")
            for linha in saida.strip().splitlines()[-6:]:
                print(f"          | {linha[:150]}")
        else:
            oks = ", ".join(n for n, _ in checagens)
            print(f"passou  {rotulo}  ({dur:.0f}s)  [{oks}]")

    print(f"\n{len(CASOS) - falhas}/{len(CASOS)} casos passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
