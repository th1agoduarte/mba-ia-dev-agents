import httpx

# Endpoint da status page (em produção, o host real). O MockTransport abaixo
# responde por ele localmente; trocar por um cliente sem `transport` fala com a URL.
STATUS_URL = "https://status.acme.com/api/v1/status"

_STATUS = {
    "api": "operational",
    "dashboard": "operational",
    "board": "degraded",
    "billing": "operational",
    "auth": "operational",
}

_INCIDENTS = [
    {
        "id": "INC-2026-052",
        "service": "board",
        "summary": "Boards com >500 cards apresentam lentidão extrema (regression no patch 3.14.2)",
        "started_at": "2026-05-26T08:00:00Z",
        "status": "investigating",
    },
]


def _status_page_handler(request: httpx.Request) -> httpx.Response:
    """Faz o papel do servidor status.acme.com: devolve o JSON do status page.

    É aqui que, em produção, estaria o serviço externo. O MockTransport chama
    este handler em vez de abrir um socket de rede.
    """
    return httpx.Response(
        200,
        json={"services": dict(_STATUS), "open_incidents": list(_INCIDENTS)},
    )


# Transport que serve as respostas em memória (sem rede/servidor). Em produção,
# este transport some e o httpx.Client fala com o STATUS_URL real.
_MOCK_TRANSPORT = httpx.MockTransport(_status_page_handler)


def get_service_status() -> dict:
    """Status atual de cada serviço — busca na status page via HTTP (mockada).
    Equivale a `GET https://status.acme.com/api/v1/status`.
    """
    with httpx.Client(transport=_MOCK_TRANSPORT, timeout=5.0) as client:
        resp = client.get(STATUS_URL)
        resp.raise_for_status()
        return resp.json()
