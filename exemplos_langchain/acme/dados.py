"""Domínio da Acme: dados falsos e funções puras.

Nada de LangChain aqui de propósito. Este módulo é o "sistema externo" que os
agentes consultam — mantê-lo separado deixa os exemplos mostrarem só o conceito
novo de cada aula, e permite testar a regra de negócio sem chamar LLM.
"""

from __future__ import annotations

import random

FATURAS: list[dict] = [
    {
        "id": "fatura_001",
        "cliente_id": "cliente_123",
        "valor": 49.99,
        "data_emissao": "2024-01-01",
        "data_vencimento": "2024-01-15",
        "status": "paga",
    },
    {
        "id": "fatura_002",
        "cliente_id": "cliente_123",
        "valor": 49.99,
        "data_emissao": "2024-02-01",
        "data_vencimento": "2024-02-15",
        "status": "pendente",
    },
    {
        "id": "fatura_003",
        "cliente_id": "cliente_456",
        "valor": 29.99,
        "data_emissao": "2024-01-10",
        "data_vencimento": "2024-01-25",
        "status": "paga",
    },
    {
        "id": "fatura_004",
        "cliente_id": "cliente_456",
        "valor": 29.99,
        "data_emissao": "2024-02-10",
        "data_vencimento": "2024-02-25",
        "status": "pendente",
    },
]

ASSINATURAS: dict[str, dict] = {
    "cliente_123": {"plano": "Pro", "status": "ativa", "renovacao": "2026-07-01"},
    "cliente_456": {"plano": "Basic", "status": "ativa", "renovacao": "2025-12-15"},
}

SENHA_VALIDA = "senha_secreta"

# Quem já respondeu a pesquisa de satisfação nos últimos 3 meses.
RESPONDERAM_PESQUISA = {"cliente_123"}


def buscar_faturas(cliente_id: str) -> list[dict]:
    return [f for f in FATURAS if f["cliente_id"] == cliente_id]


def buscar_assinatura(cliente_id: str) -> dict | None:
    return ASSINATURAS.get(cliente_id)


def cancelar(cliente_id: str) -> bool:
    """Cancela a assinatura. Devolve False se o cliente não existe."""
    assinatura = ASSINATURAS.get(cliente_id)
    if assinatura is None:
        return False
    assinatura["status"] = "cancelada"
    return True


def status_plataforma() -> str:
    """Sorteia o status da plataforma (simula um sistema externo instável)."""
    return random.choice(["operacional", "manutencao", "intermitente"])
