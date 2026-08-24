"""Telepost Payments Handler — Telegram Stars, pre_checkout, donations."""
import logging
from aiogram import Router, F
from aiogram.types import Message, PreCheckoutQuery
from bot.config import config
from bot import database as db

logger = logging.getLogger("telepost.payments")
payments_router = Router()

@payments_router.pre_checkout_query()
async def handle_pre_checkout(query: PreCheckoutQuery):
    """Approve all pre-checkout queries."""
    try:
        await query.answer(ok=True)
    except Exception as e:
        logger.error(f"Pre-checkout failed: {e}")
        try:
            await query.answer(ok=False, error_message="Ошибка оплаты. Попробуйте позже.")
        except:
            pass

@payments_router.message(F.successful_payment)
async def handle_successful_payment(message: Message):
    """Process successful payment."""
    sp = message.successful_payment
    payload = sp.invoice_payload or ""
    amount = sp.total_amount or 0
    charge_id = sp.telegram_payment_charge_id or f"unknown_{message.message_id}"
    user_id = message.from_user.id if message.from_user else 0

    logger.info(f"Payment received: user={user_id}, amount={amount}⭐, payload={payload}")

    if payload == "donate":
        await db.record_donation(user_id, amount, charge_id)
        await message.reply(
            f"⭐ Спасибо за поддержку! {amount} Stars получено.\n\n"
            f"📢 Подписка на канал: https://t.me/{config.CHANNEL_USERNAME}"
        )
    else:
        # Generic payment
        await message.reply(f"✅ Оплата получена! {amount}⭐")

# Set reactions on channel posts
@payments_router.channel_post()
async def handle_channel_post(message: Message):
    """Set positive reactions on all channel posts."""
    try:
        await message.bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[
                {"type": "emoji", "emoji": "👍"},
                {"type": "emoji", "emoji": "🔥"},
            ]
        )
    except Exception as e:
        logger.debug(f"Channel reaction failed: {e}")
