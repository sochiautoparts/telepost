"""Telepost Chat Handler — /start, /help, /new, /my, /stats."""
import logging, json, time, html
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from bot.config import config
from bot import database as db

logger = logging.getLogger("telepost.chat")
chat_router = Router()

@chat_router.message(Command("start"))
async def cmd_start(message: Message):
    u = message.from_user
    if not u: return

    await db.upsert_user(u.id, u.username or "", u.first_name or "", u.last_name or "", u.is_bot)

    if await db.is_banned(u.id):
        await message.reply("🚫 Вы заблокированы.")
        return

    # Check for deep-link payload
    payload = message.text.split(" ", 1)[1].strip() if " " in message.text else ""

    if payload == "new":
        return await start_new_ad(message)
    elif payload.startswith("ad_"):
        ad_id = int(payload[3:]) if payload[3:].isdigit() else 0
        return await show_ad_info(message, ad_id)
    elif payload == "help":
        return await cmd_help(message)

    name = u.first_name or u.username or "друг"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Разместить объявление", callback_data="action_new_ad"),
         InlineKeyboardButton(text="🏪 Добавить организацию", callback_data="action_new_place")],
        [InlineKeyboardButton(text="📋 Мои объявления", callback_data="action_my_ads"),
         InlineKeyboardButton(text="🌐 Открыть сайт", url=config.SITE_URL)],
        [InlineKeyboardButton(text="📢 Канал", url=f"https://t.me/{config.CHANNEL_USERNAME}")],
    ])

    await message.reply(
        # Bot default parse_mode is HTML — user names must be escaped
        f"👋 Привет, {html.escape(name)}!\n\n"
        f"🛰 <b>Telepost.Space</b> — маркетплейс объявлений на карте.\n\n"
        f"Что я умею:\n"
        f"📍 Размещать объявления в канале @{config.CHANNEL_USERNAME}\n"
        f"🏪 Добавлять организации на карту\n"
        f"💰 Принимать оплату в Telegram Stars\n"
        f"📊 Показывать статистику\n\n"
        f"Жми кнопку, чтобы начать 👇",
        parse_mode="HTML",
        reply_markup=kb
    )

@chat_router.message(Command("help"))
async def cmd_help(message: Message):
    await message.reply(
        "🛰 <b>Telepost Bot — команды</b>\n\n"
        "/start — главное меню\n"
        "/new — создать объявление\n"
        "/place — добавить организацию\n"
        "/my — мои объявления\n"
        "/myplaces — мои организации\n"
        "/donate — поддержать проект ⭐\n"
        "/stats — статистика (админ)\n"
        "/help — этот текст\n\n"
        f"🌐 Сайт: {config.SITE_URL}\n"
        f"📢 Канал: @{config.CHANNEL_USERNAME}",
        parse_mode="HTML"
    )

@chat_router.message(Command("new"))
async def cmd_new(message: Message):
    await start_new_ad(message)

@chat_router.message(Command("place"))
async def cmd_place(message: Message):
    from bot.handlers.ad_flow import start_new_place
    await start_new_place(message)

@chat_router.message(Command("my"))
async def cmd_my(message: Message):
    u = message.from_user
    if not u: return
    ads = await db.get_user_ads(u.id, 10)
    if not ads:
        await message.reply("У вас пока нет объявлений. Напишите /new чтобы создать первое.")
        return
    # Hide expired ads (expires_at == 0/null means "never expires")
    now = int(time.time())
    ads = [a for a in ads if not a["expires_at"] or a["expires_at"] > now]
    if not ads:
        await message.reply("⏳ Все ваши объявления истекли. Напишите /new чтобы создать новое.")
        return
    text = "📋 <b>Ваши объявления:</b>\n\n"
    for ad in ads:
        status = "✅" if ad["status"] == "active" else "❌"
        text += f"{status} <b>{html.escape(str(ad['title'] or ''))}</b>"
        if ad["price"]:
            text += f" — {int(ad['price'])} {ad['currency']}"
        text += f"\n   {config.SITE_URL}\n\n"
    await message.reply(text, parse_mode="HTML", disable_web_page_preview=True)

@chat_router.message(Command("myplaces"))
async def cmd_myplaces(message: Message):
    u = message.from_user
    if not u: return
    places = await db.get_user_places(u.id, 10)
    if not places:
        await message.reply("У вас пока нет организаций. Напишите /place чтобы добавить.")
        return
    text = "🏪 <b>Ваши организации:</b>\n\n"
    for p in places:
        text += f"✅ <b>{html.escape(str(p['name'] or ''))}</b>"
        if p["city"]:
            text += f" — {html.escape(str(p['city']))}"
        text += "\n"
    await message.reply(text, parse_mode="HTML")

@chat_router.message(Command("stats"))
async def cmd_stats(message: Message):
    u = message.from_user
    if not u: return
    if u.id != config.OWNER_ID and u.id not in config.ADMIN_IDS:
        await message.reply("Команда доступна только администраторам.")
        return
    stats = await db.get_stats()
    await message.reply(
        f"📊 <b>Статистика Telepost</b>\n\n"
        f"👥 Пользователей: {stats['users']}\n"
        f"📢 Объявлений: {stats['ads']}\n"
        f"🏪 Организаций: {stats['places']}\n"
        f"⭐ Донатов: {stats['stars']}\n\n"
        f"🌐 {config.SITE_URL}",
        parse_mode="HTML"
    )

@chat_router.message(Command("donate"))
async def cmd_donate(message: Message):
    await message.reply_invoice(
        title="☕ Поддержать Telepost.Space",
        description="Спасибо за поддержку проекта!",
        payload="donate",
        currency="XTR",
        prices=[{"label": "Донат", "amount": 100}],
        provider_token="",
    )

async def start_new_ad(message: Message):
    """Start ad creation flow."""
    u = message.from_user
    if not u: return
    if await db.is_banned(u.id):
        await message.reply("🚫 Вы заблокированы.")
        return
    await db.set_state(u.id, "ad_title")
    await message.reply(
        "📝 <b>Создание объявления</b>\n\n"
        "Шаг 1: отправьте <b>заголовок</b> объявления (что продаёте).\n"
        "Например: «iPhone 15 Pro 256GB»\n\n"
        "Для отмены напишите /cancel",
        parse_mode="HTML"
    )

async def show_ad_info(message: Message, ad_id: int):
    """Show ad info by ID (deep-link)."""
    ad = await db.get_ad(ad_id)
    if not ad:
        await message.reply("Объявление не найдено.")
        return
    from bot.post_utils import format_ad_post
    text = format_ad_post(ad, config.SITE_URL)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Открыть на сайте", url=f"{config.SITE_URL}/ads/{ad_id}")],
        [InlineKeyboardButton(text="🚀 Поднять (50⭐)", callback_data=f"boost_rise_{ad_id}"),
         InlineKeyboardButton(text="📌 Закрепить (200⭐)", callback_data=f"boost_pin_{ad_id}")],
    ])
    await message.reply(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)

@chat_router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    u = message.from_user
    if not u: return
    await db.clear_state(u.id)
    await message.reply("❌ Действие отменено. Напишите /start для меню.")
