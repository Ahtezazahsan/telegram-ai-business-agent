from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )
    telegram_chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    first_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    last_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    language_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_update_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        unique=True,
        nullable=True,
        index=True,
    )
    telegram_message_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    direction: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    message_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="text",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    delivery_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="received",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    customer: Mapped["Customer"] = relationship(
        back_populates="messages",
    )