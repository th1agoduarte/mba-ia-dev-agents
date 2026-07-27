from db.engine import async_session
from db.models import TicketModel


# TICKET ############################
async def create_ticket(
    model: TicketModel
) -> TicketModel:
    async with async_session.begin() as session:
        session.add(model)
        await session.flush()
        return model


async def update_ticket(
    model: TicketModel
) -> TicketModel:
    async with async_session.begin() as session:
        await session.merge(model)
        await session.flush()
        return model


async def get_ticket(
    ticket_id: str
) -> TicketModel | None:
    async with async_session.begin() as session:
        return await session.get(TicketModel, ticket_id)
