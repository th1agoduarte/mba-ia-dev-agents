#!/usr/bin/env python3
"""Renderiza uma página da doc do LangChain em Python puro.

O repo langchain-ai/docs é um site Mintlify: as páginas .mdx guardam só a prosa e
importam os exemplos de código de /snippets/code-samples/*.mdx. Este script faz o que
o pipeline Mintlify faria: resolve os imports, inlina os snippets Python, remove os
blocos :::js e imprime a página pronta para leitura.

Uso:
    uv run python scripts/lcdoc.py oss/langchain/agents
    uv run python scripts/lcdoc.py src/oss/langgraph/interrupts.mdx
    uv run python scripts/lcdoc.py --list oss/langchain   # lista páginas do diretório
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "docs" / "langchain-docs" / "src"

RE_IMPORT = re.compile(r"^import\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"];?\s*$", re.M)
RE_COMPONENTE = re.compile(r"^\s*<(\w+)\s*/>\s*$", re.M)
RE_CERCA = re.compile(r"^:::(python|js)\s*$", re.M)


def resolver(alvo: str) -> Path:
    """Resolve o alvo em caminho: aceita com ou sem .mdx, com ou sem prefixo src/."""
    p = Path(alvo)
    if p.is_absolute() and p.exists():
        return p
    limpo = alvo.removeprefix("src/").removesuffix(".mdx")
    caminho = RAIZ / f"{limpo}.mdx"
    if not caminho.exists():
        sys.exit(f"não encontrei: {caminho}")
    return caminho


def carregar_snippet(destino: str) -> str:
    """'/snippets/code-samples/x-py.mdx' -> conteúdo do arquivo."""
    caminho = RAIZ / destino.lstrip("/")
    if not caminho.exists():
        return f"<!-- snippet ausente: {destino} -->"
    return caminho.read_text(encoding="utf-8").strip()


def filtrar_linguagem(texto: str, manter: str = "python") -> str:
    """Remove os blocos da outra linguagem e as cercas ::: da linguagem mantida."""
    saida: list[str] = []
    lingua_atual: str | None = None
    for linha in texto.splitlines():
        cerca = RE_CERCA.match(linha)
        if cerca:
            lingua_atual = cerca.group(1)
            continue
        if linha.strip() == ":::" and lingua_atual:
            lingua_atual = None
            continue
        if lingua_atual and lingua_atual != manter:
            continue
        saida.append(linha)
    return "\n".join(saida)


def renderizar(caminho: Path, manter: str = "python") -> str:
    texto = caminho.read_text(encoding="utf-8")

    # 1. coleta os imports de snippet e os remove do corpo
    imports: dict[str, str] = dict(RE_IMPORT.findall(texto))
    texto = RE_IMPORT.sub("", texto)

    # 2. descarta a outra linguagem
    texto = filtrar_linguagem(texto, manter)

    # 3. inlina <Componente /> quando veio de um import de snippet
    def trocar(m: re.Match[str]) -> str:
        nome = m.group(1)
        destino = imports.get(nome)
        if destino is None:
            return m.group(0)  # componente Mintlify de verdade (Note, Tabs...)
        return carregar_snippet(destino)

    texto = RE_COMPONENTE.sub(trocar, texto)

    # 4. compacta linhas em branco repetidas
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def main() -> None:
    """Ponto de entrada da CLI."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("alvo", help="caminho da página, ex.: oss/langchain/agents")
    ap.add_argument("--js", action="store_true", help="renderiza TypeScript no lugar de Python")
    ap.add_argument("--list", action="store_true", help="lista as páginas do diretório")
    args = ap.parse_args()

    if args.list:
        base = RAIZ / args.alvo.removeprefix("src/")
        if not base.is_dir():
            sys.exit(f"não é diretório: {base}")
        for f in sorted(base.rglob("*.mdx")):
            print(f.relative_to(RAIZ).with_suffix(""))
        return

    print(renderizar(resolver(args.alvo), "js" if args.js else "python"))


if __name__ == "__main__":
    main()
