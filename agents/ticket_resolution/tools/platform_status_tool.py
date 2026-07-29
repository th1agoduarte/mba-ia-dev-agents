from outside.mock_platform_status_server import get_service_status

async def platform_status() -> dict:
    """Status atual dos serviços da plataforma Acme + incidents em aberto.

    Equivale a `GET https://status.acme.com/api/v1/status`. Use para checar se há um
    incident correlacionado ao problema do cliente.

    Returns:
        Dict com `services` (mapa serviço→estado, ex.: `board: degraded`) e
        `open_incidents` (lista com `id`, `service`, `summary`, `status`).
    """
    return get_service_status()
