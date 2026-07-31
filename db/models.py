from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, Float, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, composite, mapped_column

class Base(DeclarativeBase):
    pass

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_ticket_id() -> str:
    return f"TCK-{uuid4().hex[:8].upper()}"


class TicketCategory(str, Enum):
    BILLING = "billing"
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    ONBOARDING = "onboarding"
    COMPOSITE = "composite"
    UNDEFINED = "undefined"
    OUT_OF_SCOPE = "out_of_scope"

    SECURITY_INCIDENT = "security_incident"


class TicketStatus(str, Enum):
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    FAILED = "failed"
    AUTO_CLOSED = "auto_closed"


@dataclass
class ClassificationModel:
    """Value object embutido (composite) — espelha o ClassificationSchema.

    NÃO é tabela/relacionamento: estes campos viram colunas `cls_*` na própria
    linha de `tickets` e são acessados como um único objeto `classification`.
    """
    category: TicketCategory
    confidence: float
    justification: str
    needs_refund: bool


class TicketModel(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=_new_ticket_id)
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[TicketStatus] = mapped_column(
        SqlEnum(TicketStatus), default=TicketStatus.PENDING)
    classification: Mapped[ClassificationModel] = composite(
        mapped_column("cls_category", SqlEnum(TicketCategory)),
        mapped_column("cls_confidence", Float),
        mapped_column("cls_justification", Text),
        mapped_column("cls_needs_refund", Boolean),
    )
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

class TicketEscalationModel(Base):
    __tablename__ = "ticket_escalations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(16), default="open")
    external_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )