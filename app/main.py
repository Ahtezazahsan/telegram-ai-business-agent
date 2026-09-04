import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, status
from sqlalchemy import func, select, text

from app import models  # noqa: F401
from app.database import Base, SessionLocal, engine
from app.repositories import (
    get_recent_conversation,
    save_incoming_message,
    save_outgoing_message,
)

load_dotenv()

APP_NAME = os.getenv(
    "APP_NAME",
    "Telegram AI Business Agent",
)
APP_ENV = os.getenv("APP_ENV", "development")

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "",
).strip()

TELEGRAM_WEBHOOK_SECRET = os.getenv(
    "TELEGRAM_WEBHOOK_SECRET",
    "",
).strip()

ADMIN_TELEGRAM_CHAT_ID = os.getenv(
    "ADMIN_TELEGRAM_CHAT_ID",
    "",
).strip()

N8N_ORCHESTRATION_URL = os.getenv(
    "N8N_ORCHESTRATION_URL",
    "",
).strip()

N8N_INTERNAL_API_KEY = os.getenv(
    "N8N_INTERNAL_API_KEY",
    "",
).strip()

TELEGRAM_SEND_ENABLED = (
    os.getenv("TELEGRAM_SEND_ENABLED", "false").lower()
    == "true"
)

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
)

logger = logging.getLogger(APP_NAME)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

app = FastAPI(
    title=APP_NAME,
    description=(
        "AI-powered Telegram customer support "
        "and sales platform"
    ),
    version="1.0.0",
)


async def send_telegram_message(
    chat_id: int,
    message_text: str,
) -> dict[str, Any]:
    if not TELEGRAM_SEND_ENABLED:
        logger.info(
            "Telegram sending disabled | chat_id=%s",
            chat_id,
        )
        return {}

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not configured"
        )

    telegram_url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": message_text,
    }

    try:
        timeout_config = httpx.Timeout(
            timeout=20.0,
            connect=10.0,
        )

        async with httpx.AsyncClient(
            timeout=timeout_config
        ) as client:
            response = await client.post(
                telegram_url,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        logger.info(
            "Telegram message sent | chat_id=%s",
            chat_id,
        )

        return result.get("result", {})

    except httpx.HTTPError:
        logger.exception(
            "Telegram message failed | chat_id=%s",
            chat_id,
        )
        raise


async def call_n8n_orchestrator(
    chat_id: int,
    sender: dict[str, Any],
    message_text: str,
    conversation_history: list[dict[str, str]],
) -> dict[str, Any]:
    if not N8N_ORCHESTRATION_URL:
        raise RuntimeError(
            "N8N_ORCHESTRATION_URL is not configured"
        )

    if not N8N_INTERNAL_API_KEY:
        raise RuntimeError(
            "N8N_INTERNAL_API_KEY is not configured"
        )

    payload = {
        "telegram_user_id": sender.get("id"),
        "chat_id": chat_id,
        "username": sender.get("username"),
        "first_name": sender.get("first_name"),
        "message": message_text,
        "conversation_history": conversation_history,
    }

    headers = {
        "X-Internal-API-Key": N8N_INTERNAL_API_KEY,
    }

    timeout_config = httpx.Timeout(
        timeout=60.0,
        connect=10.0,
    )

    try:
        async with httpx.AsyncClient(
            timeout=timeout_config
        ) as client:
            response = await client.post(
                N8N_ORCHESTRATION_URL,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()

        logger.info(
            "n8n orchestration completed | "
            "chat_id=%s | intent=%s",
            chat_id,
            result.get("intent"),
        )

        return result

    except httpx.HTTPError:
        logger.exception(
            "n8n request failed | chat_id=%s",
            chat_id,
        )
        raise


async def send_human_handoff_alert(
    chat_id: int,
    sender: dict[str, Any],
    customer_message: str,
    ai_reply: str,
) -> None:
    if not ADMIN_TELEGRAM_CHAT_ID:
        logger.warning(
            "Human handoff requested but "
            "ADMIN_TELEGRAM_CHAT_ID is not configured"
        )
        return

    username = sender.get("username")

    username_text = (
        f"@{username}"
        if username
        else "not_available"
    )

    first_name = sender.get("first_name") or "Unknown"

    alert_text = (
        "🚨 HUMAN HANDOFF REQUIRED\n\n"
        f"Customer: {first_name}\n"
        f"Username: {username_text}\n"
        f"Customer Chat ID: {chat_id}\n"
        f"Message: {customer_message}\n\n"
        f"AI Reply: {ai_reply}"
    )

    try:
        admin_chat_id = int(ADMIN_TELEGRAM_CHAT_ID)

        await send_telegram_message(
            admin_chat_id,
            alert_text,
        )

        logger.info(
            "Human handoff alert sent | "
            "customer_chat_id=%s",
            chat_id,
        )

    except (ValueError, httpx.HTTPError, RuntimeError):
        logger.exception(
            "Human handoff alert failed | "
            "customer_chat_id=%s",
            chat_id,
        )


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": APP_NAME,
        "status": "running",
        "environment": APP_ENV,
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
    }


@app.get("/admin/database/stats")
def database_stats(
    x_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    if x_admin_key != TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key",
        )

    with SessionLocal() as session:
        database_info = session.execute(
            text(
                "SELECT current_database(), "
                "current_schema()"
            )
        ).one()

        customer_count = session.scalar(
            select(func.count(models.Customer.id))
        )

        message_count = session.scalar(
            select(func.count(models.Message.id))
        )

    return {
        "database": database_info[0],
        "schema": database_info[1],
        "customers": customer_count or 0,
        "messages": message_count or 0,
    }


@app.post("/admin/database/init")
def initialize_database(
    x_admin_key: str | None = Header(default=None),
) -> dict[str, str]:
    if x_admin_key != TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key",
        )

    try:
        Base.metadata.create_all(bind=engine)

        logger.info(
            "PostgreSQL tables initialized"
        )

        return {
            "status": "initialized",
            "database": "postgresql",
        }

    except Exception:
        logger.exception(
            "PostgreSQL initialization failed"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail="Database initialization failed",
        )


@app.post("/admin/telegram/setup-webhook")
async def setup_telegram_webhook(
    payload: dict[str, str],
    x_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    if x_admin_key != TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key",
        )

    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail="Telegram bot token is not configured",
        )

    webhook_url = payload.get(
        "webhook_url",
        "",
    ).strip()

    if not webhook_url.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A valid HTTPS webhook URL is required"
            ),
        )

    telegram_url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    )

    telegram_payload = {
        "url": webhook_url,
        "secret_token": TELEGRAM_WEBHOOK_SECRET,
        "allowed_updates": ["message"],
        "drop_pending_updates": True,
    }

    try:
        timeout_config = httpx.Timeout(
            timeout=20.0,
            connect=10.0,
        )

        async with httpx.AsyncClient(
            timeout=timeout_config
        ) as client:
            response = await client.post(
                telegram_url,
                json=telegram_payload,
            )
            response.raise_for_status()
            result = response.json()

        logger.info(
            "Telegram webhook configured | url=%s",
            webhook_url,
        )

        return result

    except httpx.HTTPError:
        logger.exception(
            "Telegram webhook setup failed"
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Telegram webhook setup failed",
        )


@app.post("/webhooks/telegram")
async def telegram_webhook(
    update: dict[str, Any],
    x_telegram_bot_api_secret_token: (
        str | None
    ) = Header(default=None),
) -> dict[str, str]:
    if not TELEGRAM_WEBHOOK_SECRET:
        logger.error(
            "TELEGRAM_WEBHOOK_SECRET is not configured"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Webhook security is not configured"
            ),
        )

    if (
        x_telegram_bot_api_secret_token
        != TELEGRAM_WEBHOOK_SECRET
    ):
        logger.warning(
            "Rejected unauthorized Telegram webhook"
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret",
        )

    message = update.get("message")

    if not message:
        logger.info(
            "Telegram update ignored | update_id=%s",
            update.get("update_id"),
        )

        return {
            "status": "ignored",
        }

    chat = message.get("chat", {})
    sender = message.get("from", {})

    chat_id = chat.get("id")
    message_text = message.get("text")
    update_id = update.get("update_id")

    if chat_id is None or not message_text:
        logger.info(
            "Non-text Telegram message ignored"
        )

        return {
            "status": "ignored",
        }

    if update_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram update ID is missing",
        )

    is_new_message = save_incoming_message(
        update_id=update_id,
        message=message,
        sender=sender,
        chat_id=chat_id,
        text=message_text,
    )

    if not is_new_message:
        logger.info(
            "Duplicate Telegram update ignored | "
            "update_id=%s",
            update_id,
        )

        return {
            "status": "duplicate",
        }

    logger.info(
        "Incoming Telegram message | "
        "update_id=%s | chat_id=%s | "
        "user_id=%s | username=%s | text=%s",
        update_id,
        chat_id,
        sender.get("id"),
        sender.get("username"),
        message_text,
    )

    conversation_history = get_recent_conversation(
        chat_id=chat_id,
        exclude_update_id=update_id,
        limit=10,
    )

    orchestration_result: dict[str, Any] = {}

    try:
        orchestration_result = (
            await call_n8n_orchestrator(
                chat_id=chat_id,
                sender=sender,
                message_text=message_text,
                conversation_history=(
                    conversation_history
                ),
            )
        )

        reply = orchestration_result.get("reply")

        if not reply:
            raise ValueError(
                "n8n response does not contain reply"
            )

    except (
        httpx.HTTPError,
        ValueError,
        RuntimeError,
    ):
        logger.exception(
            "n8n orchestration failed | chat_id=%s",
            chat_id,
        )

        reply = (
            "Sorry, I could not process your request "
            "right now. Please try again shortly."
        )

    try:
        sent_message = await send_telegram_message(
            chat_id,
            reply,
        )

        save_outgoing_message(
            chat_id=chat_id,
            text=reply,
            telegram_message_id=(
                sent_message.get("message_id")
            ),
        )

    except (httpx.HTTPError, RuntimeError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Telegram message delivery failed"
            ),
        )

    if (
        orchestration_result.get("requires_human")
        is True
    ):
        await send_human_handoff_alert(
            chat_id=chat_id,
            sender=sender,
            customer_message=message_text,
            ai_reply=reply,
        )

    return {
        "status": "processed",
    }