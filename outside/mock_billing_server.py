"""Mock do billing.acme.com.

Contrato (httpx MockTransport):
- `GET  /api/v1/invoices?customer_id=&month=`  → fatura única (404 se não existe)
- `GET  /api/v1/invoices?customer_id=`          → lista as faturas do cliente
- `POST /api/v1/refunds`  {customer_id, amount, reason}  → refund emitido

"""

import json

import httpx

BILLING_API = "https://billing.acme.com/api/v1"

# Faturas por (customer_id, month) → lista de linhas (line items) com descrição
# NEUTRA. Nada aqui diz "erro": é o agente que aplica a política.
_INVOICES = {
    # Plano + overage de uso (legítimo) — não há cobrança indevida.
    ("C-201", "2026-06"): [
        {"sku": "PLAN-PRO", "amount": 480, "description": "Assinatura Plano Pro"},
        {"sku": "OVERAGE-API", "amount": 200,
            "description": "Excedente de chamadas de API"},
    ],
    ("C-202", "2026-06"): [
        {"sku": "PLAN-ENT", "amount": 2400,
            "description": "Assinatura Plano Enterprise"},
    ],
    # Plano cobrado DUAS vezes no mesmo mês (duplicidade) → a 2ª linha é indevida.
    ("C-203", "2026-06"): [
        {"sku": "PLAN-PRO", "amount": 30, "description": "Assinatura Plano Pro"},
        {"sku": "PLAN-PRO", "amount": 30, "description": "Assinatura Plano Pro"},
    ],
    # Ajuste manual sem justificativa (suspeito) de valor pequeno.
    ("C-206", "2026-06"): [
        {"sku": "PLAN-PRO", "amount": 480, "description": "Assinatura Plano Pro"},
        {"sku": "ADJ-MISC", "amount": 40, "description": "Ajuste manual"},
    ],
    # Ajuste manual sem justificativa de valor médio.
    ("C-207", "2026-06"): [
        {"sku": "PLAN-PRO", "amount": 480, "description": "Assinatura Plano Pro"},
        {"sku": "ADJ-MISC", "amount": 120, "description": "Ajuste manual"},
    ],
    # Dois meses com ajuste manual suspeito → o agente precisa escolher o mês.
    ("C-204", "2026-05"): [
        {"sku": "PLAN-PRO", "amount": 480, "description": "Assinatura Plano Pro"},
        {"sku": "ADJ-MISC", "amount": 30, "description": "Ajuste manual"},
    ],
    ("C-204", "2026-06"): [
        {"sku": "PLAN-PRO", "amount": 480, "description": "Assinatura Plano Pro"},
        {"sku": "ADJ-MISC", "amount": 80, "description": "Ajuste manual"},
    ],
    # (C-205 não tem fatura → caso de ir para humano.)
}


def _invoice_payload(customer_id: str, month: str, items: list[dict]) -> dict:
    """Fatura com linhas identificadas (`id = "<month>-<i>"`) para o agente referenciar."""
    line_items = [
        {"id": f"{month}-{i}", **item} for i, item in enumerate(items)
    ]
    return {
        "customer_id": customer_id,
        "month": month,
        "total": sum(item["amount"] for item in items),
        "items": line_items,
    }


def _billing_handler(request: httpx.Request) -> httpx.Response:
    """Faz o papel do servidor billing.acme.com."""
    if request.method == "POST":  # /refunds
        body = json.loads(request.content)
        customer_id, amount, reason = body["customer_id"], body["amount"], body["reason"]
        return httpx.Response(201, json={
            "refund_id": f"REF-{customer_id}-{int(amount)}",
            "customer_id": customer_id,
            "amount": amount,
            "reason": reason,
            "status": "issued",
        })

    # GET /invoices
    customer_id = request.url.params.get("customer_id", "")
    month = request.url.params.get("month", "")

    if not month:  # lista todas as faturas do cliente
        invoices = [
            _invoice_payload(cid, m, items)
            for (cid, m), items in _INVOICES.items()
            if cid == customer_id
        ]
        invoices.sort(key=lambda i: i["month"], reverse=True)
        return httpx.Response(200, json={"customer_id": customer_id, "invoices": invoices})

    items = _INVOICES.get((customer_id, month))
    if items is None:
        return httpx.Response(404, json={"error": f"no invoice for {customer_id} in {month}"})
    return httpx.Response(200, json=_invoice_payload(customer_id, month, items))


_MOCK_TRANSPORT = httpx.MockTransport(_billing_handler)


async def list_invoices(customer_id: str) -> list[dict]:
    """Faturas recentes do cliente (cada uma com suas linhas). [] se nenhuma."""
    async with httpx.AsyncClient(transport=_MOCK_TRANSPORT, timeout=5.0) as client:
        resp = await client.get(f"{BILLING_API}/invoices",
                                params={"customer_id": customer_id})
        resp.raise_for_status()
        return resp.json()["invoices"]


async def get_invoice(customer_id: str, month: str) -> dict:
    """Fatura de um mês específico. Mês inexistente volta `{"error": ...}` (404)."""
    async with httpx.AsyncClient(transport=_MOCK_TRANSPORT, timeout=5.0) as client:
        resp = await client.get(f"{BILLING_API}/invoices",
                                params={"customer_id": customer_id, "month": month})
        if resp.status_code == 404:
            return resp.json()
        resp.raise_for_status()
        return resp.json()


async def issue_refund(customer_id: str, amount: float, reason: str) -> dict:
    async with httpx.AsyncClient(transport=_MOCK_TRANSPORT, timeout=5.0) as client:
        resp = await client.post(
            f"{BILLING_API}/refunds",
            json={"customer_id": customer_id,
                  "amount": amount, "reason": reason},
        )
        resp.raise_for_status()
        return resp.json()
