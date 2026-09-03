from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Customer, Message


def get_or_create_customer(
    session: Session,
    sender: dict[str, Any],
    chat_id: int,
) -> Customer:
    telegram_user_id = sender["id"]

    customer = session.scalar(
        select(Customer).where(
            Customer.telegram_user_id == telegram_user_id
        )
    )

    if customer is None:
        customer = Customer(
            telegram_user_id=telegram_user_id,
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

    return customer


def save_incoming_message(
    update_id: int,
    message: dict[str, Any],
    sender: dict[str, Any],
    chat_id: int,
    text: str,
) -> bool:
    with SessionLocal() as session:
        existing_message = session.scalar(
            select(Message).where(
                Message.telegram_update_id == update_id
            )
        )

        if existing_message is not None:
            return False

        customer = get_or_create_customer(
            session=session,
            sender=sender,
            chat_id=chat_id,
        )

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
        except IntegrityError:
            session.rollback()
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
            raise ValueError("Customer does not exist")

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