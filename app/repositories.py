import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import Customer, Message

logger = logging.getLogger("database")


def save_incoming_message(
    update_id: int,
    message: dict[str, Any],
    sender: dict[str, Any],
    chat_id: int,
    text: str,
) -> bool:
    with SessionLocal() as session:
        existing_id = session.scalar(
            select(Message.id).where(
                Message.telegram_update_id == update_id
            )
        )

        if existing_id is not None:
            logger.info(
                "Duplicate database message | update_id=%s",
                update_id,
            )
            return False

        customer = session.scalar(
            select(Customer).where(
                Customer.telegram_user_id == sender["id"]
            )
        )

        if customer is None:
            customer = Customer(
                telegram_user_id=sender["id"],
                telegram_chat_id=chat_id,
                username=sender.get("username"),
                first_name=sender.get("first_name"),
                last_name=sender.get("last_name"),
                language_code=sender.get("language_code"),
            )
            session.add(customer)
            session.flush()
        else:
            customer.telegram_chat_id = chat_id
            customer.username = sender.get("username")
            customer.first_name = sender.get("first_name")
            customer.last_name = sender.get("last_name")
            customer.language_code = sender.get("language_code")

        incoming_message = Message(
            customer_id=customer.id,
            telegram_update_id=update_id,
            telegram_message_id=message.get("message_id"),
            direction="incoming",
            message_type="text",
            content=text,
            delivery_status="received",
        )

        session.add(incoming_message)

        try:
            session.commit()

            customer_count = session.scalar(
                select(func.count(Customer.id))
            )
            message_count = session.scalar(
                select(func.count(Message.id))
            )

            logger.info(
                "Incoming DB commit verified | customer_id=%s | "
                "customers=%s | messages=%s",
                customer.id,
                customer_count,
                message_count,
            )

        except IntegrityError:
            session.rollback()
            logger.exception(
                "Incoming database integrity error | update_id=%s",
                update_id,
            )
            return False

    return True


def save_outgoing_message(
    chat_id: int,
    text: str,
    telegram_message_id: int | None,
) -> None:
    with SessionLocal() as session:
        customer = session.scalar(
            select(Customer).where(
                Customer.telegram_chat_id == chat_id
            )
        )

        if customer is None:
            raise ValueError(
                f"Customer not found for chat_id={chat_id}"
            )

        outgoing_message = Message(
            customer_id=customer.id,
            telegram_update_id=None,
            telegram_message_id=telegram_message_id,
            direction="outgoing",
            message_type="text",
            content=text,
            delivery_status="sent",
        )

        session.add(outgoing_message)
        session.commit()

        message_count = session.scalar(
            select(func.count(Message.id))
        )

        logger.info(
            "Outgoing DB commit verified | customer_id=%s | "
            "messages=%s",
            customer.id,
            message_count,
        )

def get_recent_conversation(
    chat_id: int,
    exclude_update_id: int | None = None,
    limit: int = 10,
) -> list[dict[str, str]]:
    with SessionLocal() as session:
        customer = session.scalar(
            select(Customer).where(
                Customer.telegram_chat_id == chat_id
            )
        )

        if customer is None:
            return []

        query = select(Message).where(
            Message.customer_id == customer.id
        )

        if exclude_update_id is not None:
            query = query.where(
                (
                    Message.telegram_update_id.is_(None)
                )
                | (
                    Message.telegram_update_id
                    != exclude_update_id
                )
            )

        messages = session.scalars(
            query.order_by(
                Message.created_at.desc()
            ).limit(limit)
        ).all()

        messages.reverse()

        return [
            {
                "role": (
                    "user"
                    if message.direction == "incoming"
                    else "assistant"
                ),
                "content": message.content,
            }
            for message in messages
        ]