import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, status

from app import models  # noqa: F401
from app.database import Base, engine


load_dotenv()

APP_NAME = os.getenv("APP_NAME", "Telegram AI Business Agent")
APP_ENV = os.getenv("APP_ENV", "development")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
TELEGRAM_SEND_ENABLED = (
    os.getenv("TELEGRAM_SEND_ENABLED", "false").lower() == "true"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(APP_NAME)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

app = FastAPI(
    title=APP_NAME,
    description="AI-powered Telegram customer support and sales platform",
    version="1.0.0",
)


async def send_telegram_message(chat_id: int, text: str) -> None:
    if not TELEGRAM_SEND_ENABLED:
        logger.info(
            "Telegram sending disabled locally | chat_id=%s | reply=%s",
            chat_id,
            text,
        )
        return

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

        logger.info("Telegram reply sent | chat_id=%s", chat_id)

    except httpx.HTTPError:
        logger.exception(
            "Telegram reply failed | chat_id=%s",
            chat_id,
        )
        raise


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
        logger.info("PostgreSQL tables initialized")

        return {
            "status": "initialized",
            "database": "postgresql",
        }

    except Exception:
        logger.exception("PostgreSQL initialization failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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

    webhook_url = payload.get("webhook_url", "")

    if not webhook_url.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid HTTPS webhook URL is required",
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
        async with httpx.AsyncClient(timeout=20.0) as client:
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
        logger.exception("Telegram webhook setup failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Telegram webhook setup failed",
        )
    
@app.post("/webhooks/telegram")
async def telegram_webhook(
    update: dict[str, Any],
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None
    ),
) -> dict[str, str]:
    if not TELEGRAM_WEBHOOK_SECRET:
        logger.error("TELEGRAM_WEBHOOK_SECRET is not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook security is not configured",
        )

    if (
        x_telegram_bot_api_secret_token
        != TELEGRAM_WEBHOOK_SECRET
    ):
        logger.warning("Rejected unauthorized Telegram webhook")
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
        return {"status": "ignored"}

    chat = message.get("chat", {})
    sender = message.get("from", {})
    chat_id = chat.get("id")
    text = message.get("text")

    if chat_id is None or not text:
        logger.info("Non-text Telegram message ignored")
        return {"status": "ignored"}

    logger.info(
        "Incoming Telegram message | update_id=%s | "
        "chat_id=%s | user_id=%s | username=%s | text=%s",
        update.get("update_id"),
        chat_id,
        sender.get("id"),
        sender.get("username"),
        text,
    )

    reply = (
        f"Hello {sender.get('first_name', 'there')}! "
        f"I received your message: {text}"
    )

    try:
        await send_telegram_message(chat_id, reply)
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Telegram message delivery failed",
        )

    return {"status": "processed"}