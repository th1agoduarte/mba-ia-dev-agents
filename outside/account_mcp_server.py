import os

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()  # Carrega variáveis de ambiente do arquivo .env

_HOST = os.environ.get("ACCOUNT_MCP_HOST")
_PORT = int(os.environ.get("ACCOUNT_MCP_PORT")) #type: ignore

# stateless_http + json_response: cada chamada é independente (sem sessão SSE de
# longa duração) — mais simples e robusto para um agente que conecta, usa e sai.
mcp = FastMCP(
    name="acme-account",
    host=_HOST, #type: ignore
    port=_PORT,
    stateless_http=True,
    json_response=True,
)

# Estado mock: cliente -> e-mails dos membros da equipe. Este servidor É o sistema
# de verdade da conta (como billing.acme.com é o de faturamento).
_TEAM: dict[str, list[str]] = {
    "C-201": ["ana@acme-customer.com"],
    "C-202": ["dev@bigcorp.com", "ops@bigcorp.com"],
}


@mcp.tool()
def list_team_members(customer_id: str) -> dict:
    """
        Lista os e-mails dos membros atuais da equipe do cliente.
        Args:
            customer_id (str): ID do cliente (ex.: "C-201").
        Returns:
            Dict com `customer_id` e `members` (lista de e-mails).
    """
    if not customer_id:
        raise ValueError("customer_id é obrigatório.")

    return {"customer_id": customer_id, "members": list(_TEAM.get(customer_id, []))}


@mcp.tool()
def add_team_member(customer_id: str, email: str) -> dict:
    """
        Adiciona um membro à equipe do cliente.
        Args:
            customer_id (str): ID do cliente (ex.: "C-201").
            email (str): E-mail do membro a adicionar.
        Returns:
            Dict com `status` ("added", "already_member", "invalid_email"), `email` e `members` (lista de e-mails).
    """
    if not customer_id:
        raise ValueError("customer_id é obrigatório.")

    if not email:
        raise ValueError("email é obrigatório.")
    
    members = _TEAM.setdefault(customer_id, [])
    email = email.strip().lower()
    if "@" not in email or "." not in email:
        return {"status": "invalid_email", "email": email}
    if email in members:
        return {"status": "already_member", "email": email, "members": list(members)}
    members.append(email)
    return {"status": "added", "email": email, "members": list(members)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
