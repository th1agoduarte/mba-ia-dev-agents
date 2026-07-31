from db.engine import async_session
from db.models import TicketEscalationModel, TicketModel
from sqlalchemy import select

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


async def create_ticket_escalation(
    ticket_escalation: TicketEscalationModel
) -> TicketEscalationModel:
    async with async_session.begin() as session:
        session.add(ticket_escalation)
        await session.flush()
        return ticket_escalation


async def get_ticket_escalation(
    ticket_id: str
) -> TicketEscalationModel | None:
    async with async_session.begin() as session:
        result = await session.execute(
            select(TicketEscalationModel).where(
                TicketEscalationModel.ticket_id == ticket_id
            )
        )
        return result.scalars().first()