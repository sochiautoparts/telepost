"""Telepost Bot Main — aiogram bot for ad & place posting to channel."""
import asyncio, logging, os, sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from bot.config import config
from bot import database as db
from ai import client as ai_client

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("telepost.main")

# Suppress noisy loggers
for noisy in ["aiogram.event", "httpx", "httpcore", "aiosqlite"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)

# Import routers
from bot.handlers.chat import chat_router
from bot.handlers.ad_flow import flow_router
from bot.handlers.payments import payments_router
from bot.handlers.admin import admin_router

async def main():
    """Start the bot."""
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN not set! Exiting.")
        sys.exit(1)

    logger.info(f"Starting Telepost Bot @{config.BOT_USERNAME}")
    logger.info(f"Channel: @{config.CHANNEL_USERNAME}")
    logger.info(f"Site: {config.SITE_URL}")
    logger.info(f"Cloudflare AI: {'configured' if config.has_cf() else 'NOT configured (running without AI)'}")

    # Initialize database
    await db.init_db()

    # Initialize AI client
    await ai_client.initialize()

    # Create bot
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers (order matters: flow_router handles text based on state)
    dp.include_router(admin_router)
    dp.include_router(chat_router)  # Commands: /start, /help, /new, /my, etc.
    dp.include_router(flow_router)  # FSM-based ad/place creation
    dp.include_router(payments_router)  # Pre-checkout, payments, channel reactions

    # Set bot commands
    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="new", description="Создать объявление"),
        BotCommand(command="place", description="Добавить организацию"),
        BotCommand(command="my", description="Мои объявления"),
        BotCommand(command="myplaces", description="Мои организации"),
        BotCommand(command="donate", description="Поддержать проект ⭐"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="cancel", description="Отменить действие"),
    ])

    # Get bot info
    me = await bot.get_me()
    logger.info(f"Bot started: @{me.username} (id={me.id})")

    # Start polling
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query", "pre_checkout_query", "channel_post"])
    finally:
        await ai_client.shutdown()
        await db.close_db()
        await bot.session.close()
        logger.info("Bot stopped.")

if __name__ == "__main__":
    asyncio.run(main())
