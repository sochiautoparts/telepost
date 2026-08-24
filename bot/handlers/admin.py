"""Telepost Admin Handler — ban/unban users, stats, broadcast."""
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from bot.config import config
from bot import database as db

logger = logging.getLogger("telepost.admin")
admin_router = Router()

def is_admin(user_id: int) -> bool:
    return user_id == config.OWNER_ID or user_id in config.ADMIN_IDS

@admin_router.message(Command("ban"))
async def cmd_ban(message: Message):
    u = message.from_user
    if not u or not is_admin(u.id): return
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("Использование: /ban <user_id>")
        return
    target_id = int(parts[1])
    await db.ban_user(target_id, True)
    await message.reply(f"🚫 Пользователь {target_id} заблокирован.")

@admin_router.message(Command("unban"))
async def cmd_unban(message: Message):
    u = message.from_user
    if not u or not is_admin(u.id): return
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("Использование: /unban <user_id>")
        return
    target_id = int(parts[1])
    await db.ban_user(target_id, False)
    await message.reply(f"✅ Пользователь {target_id} разблокирован.")

@admin_router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    u = message.from_user
    if not u or not is_admin(u.id): return
    text = (message.text or "").split(" ", 1)
    if len(text) < 2:
        await message.reply("Использование: /broadcast <текст>")
        return
    # Post to channel
    try:
        await message.bot.send_message(
            chat_id=f"@{config.CHANNEL_USERNAME}",
            text=text[1],
            parse_mode="HTML"
        )
        await message.reply("✅ Сообщение отправлено в канал.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@admin_router.message(Command("aistats"))
async def cmd_ai_stats(message: Message):
    u = message.from_user
    if not u or not is_admin(u.id): return
    from ai import client
    stats = client.stats()
    await message.reply(
        f"🤖 <b>AI Stats</b>\n\n"
        f"Requests: {stats.get('requests', 0)}\n"
        f"Success: {stats.get('success', 0)}\n"
        f"Failed: {stats.get('fail', 0)}\n"
        f"Last error: {stats.get('last_error', 'none')[:100]}",
        parse_mode="HTML"
    )
