"""Telepost Ad & Place Creation Flow — FSM via database state."""
import logging, json
from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command
from bot.config import config
from bot import database as db
from bot.post_utils import (
    detect_category, format_price, format_ad_post, format_place_post,
    validate_title, validate_price, is_spam, escape_html
)
from bot.media_handler import download_photo
from ai import client as ai_client

logger = logging.getLogger("telepost.ad_flow")
flow_router = Router()

# States: ad_title → ad_description → ad_price → ad_category → ad_city → ad_photo → (post)
# States: place_name → place_category → place_phone → place_city → place_address → place_desc → place_photo → (post)

@flow_router.message(F.text, F.chat.type == "private")
async def handle_flow_message(message: Message, bot: Bot):
    """Handle messages based on user's current state."""
    u = message.from_user
    if not u: return

    state, data_str = await db.get_state(u.id)
    if not state:
        return  # No active flow — let other handlers process

    data = json.loads(data_str) if data_str else {}
    text = (message.text or "").strip()

    if state == "ad_title":
        await handle_ad_title(message, bot, u.id, text, data)
    elif state == "ad_description":
        await handle_ad_description(message, bot, u.id, text, data)
    elif state == "ad_price":
        await handle_ad_price(message, bot, u.id, text, data)
    elif state == "ad_category":
        await handle_ad_category(message, bot, u.id, text, data)
    elif state == "ad_city":
        await handle_ad_city(message, bot, u.id, text, data)
    elif state == "ad_photo":
        await handle_ad_photo_step(message, bot, u.id, text, data)
    elif state == "place_name":
        await handle_place_name(message, bot, u.id, text, data)
    elif state == "place_category":
        await handle_place_category(message, bot, u.id, text, data)
    elif state == "place_phone":
        await handle_place_phone(message, bot, u.id, text, data)
    elif state == "place_city":
        await handle_place_city(message, bot, u.id, text, data)
    elif state == "place_desc":
        await handle_place_desc(message, bot, u.id, text, data)
    elif state == "place_photo":
        await handle_place_photo_step(message, bot, u.id, text, data)

# ─── Photo handler (for ad_photo and place_photo states) ────────────────────

@flow_router.message(F.photo, F.chat.type == "private")
async def handle_flow_photo(message: Message, bot: Bot):
    """Handle photo uploads during ad/place creation."""
    u = message.from_user
    if not u: return

    state, data_str = await db.get_state(u.id)
    if not state:
        return

    data = json.loads(data_str) if data_str else {}

    if state == "ad_photo":
        await handle_ad_photo(message, bot, u.id, data)
    elif state == "place_photo":
        await handle_place_photo(message, bot, u.id, data)

# ─── AD FLOW ────────────────────────────────────────────────────────────────

async def handle_ad_title(message, bot, user_id, text, data):
    ok, err = validate_title(text)
    if not ok:
        await message.reply(f"❌ {err}\n\nПопробуйте ещё раз:")
        return
    if is_spam(text):
        await message.reply("🚫 Похоже на спам. Пожалуйста, опишите ваш товар честно.")
        return
    data["title"] = text
    await db.set_state(user_id, "ad_description", json.dumps(data))
    await message.reply(
        f"✅ Заголовок: <b>{escape_html(text)}</b>\n\n"
        f"Шаг 2: отправьте <b>описание</b> товара.\n"
        f"Опишите состояние, комплектацию, особенности.\n"
        f"Максимум 1000 символов.",
        parse_mode="HTML"
    )

async def handle_ad_description(message, bot, user_id, text, data):
    if len(text) > 1000:
        await message.reply("❌ Описание слишком длинное (максимум 1000 символов).")
        return
    data["description"] = text

    # AI moderation (optional)
    if config.has_cf():
        await message.reply("⏳ Проверяю текст...")
        moderation = await ai_client.moderate_text(text)
        if not moderation.get("ok"):
            await message.reply(f"🚫 Текст не прошёл модерацию: {moderation.get('reason', 'неизвестно')}")
            return

    await db.set_state(user_id, "ad_price", json.dumps(data))
    await message.reply(
        "✅ Описание сохранено.\n\n"
        "Шаг 3: укажите <b>цену</b>.\n"
        "Например: 85000\n"
        "Или напишите «договорная» если цена не фиксирована."
    )

async def handle_ad_price(message, bot, user_id, text, data):
    ok, price, err = validate_price(text)
    if not ok:
        await message.reply(f"❌ {err}\n\nПопробуйте ещё раз:")
        return
    data["price"] = price
    data["currency"] = "RUB"

    # Auto-detect category
    detected = detect_category(data.get("title", ""), data.get("description", ""))

    # AI category suggestion (optional)
    if config.has_cf():
        ai_cat = await ai_client.generate_category_suggestion(data.get("title", ""), data.get("description", ""))
        if ai_cat and ai_cat != "other":
            detected = ai_cat

    data["category"] = detected
    await db.set_state(user_id, "ad_city", json.dumps(data))

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Пропустить город", callback_data="skip_city")
    ]])
    await message.reply(
        f"✅ Цена: {format_price(price) if price else 'договорная'}\n"
        f"📂 Категория: {detected}\n\n"
        f"Шаг 4: укажите <b>город</b>.\n"
        f"Например: Москва",
        reply_markup=kb
    )

async def handle_ad_category(message, bot, user_id, text, data):
    # This state is skipped — category auto-detected
    pass

async def handle_ad_city(message, bot, user_id, text, data):
    data["city"] = text
    await db.set_state(user_id, "ad_photo", json.dumps(data))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Без фото", callback_data="skip_photo")
    ]])
    await message.reply(
        f"✅ Город: {text}\n\n"
        f"Шаг 5: отправьте <b>фото</b> товара.\n"
        f"Можно отправить 1 фото. Или нажмите «Без фото».",
        reply_markup=kb
    )

async def handle_ad_photo_step(message, bot, user_id, text, data):
    # Text in photo state — user might type something
    if text.lower() == "пропустить":
        await finish_ad_creation(message, bot, user_id, data, has_photo=False)
    else:
        await message.reply("📸 Отправьте фото или нажмите «Без фото».")

async def handle_ad_photo(message, bot, user_id, data):
    """Handle photo upload for ad."""
    await finish_ad_creation(message, bot, user_id, data, has_photo=True, photo_message=message)

async def finish_ad_creation(message, bot, user_id, data, has_photo=False, photo_message=None):
    """Create ad in DB and post to channel."""
    try:
        # Download photo if provided
        photo_bytes = None
        if has_photo and photo_message:
            photo_bytes = await download_photo(bot, photo_message)

        # Create ad in DB
        ad_id = await db.create_ad(
            user_id=user_id,
            title=data["title"],
            description=data.get("description", ""),
            price=data.get("price", 0),
            currency=data.get("currency", "RUB"),
            category=data.get("category", "other"),
            city=data.get("city", ""),
            lat=0, lng=0,  # Will be set when site processes
            address="",
            photos=""  # Photo is in Telegram channel
        )

        # Format post
        ad_data = {
            "title": data["title"],
            "description": data.get("description", ""),
            "price": data.get("price", 0),
            "currency": data.get("currency", "RUB"),
            "category": data.get("category", "other"),
            "city": data.get("city", ""),
        }
        caption = format_ad_post(ad_data, config.SITE_URL)

        # Post to channel
        if photo_bytes:
            msg = await bot.send_photo(
                chat_id=f"@{config.CHANNEL_USERNAME}",
                photo=photo_bytes,
                caption=caption,
                parse_mode="HTML"
            )
        else:
            msg = await bot.send_message(
                chat_id=f"@{config.CHANNEL_USERNAME}",
                text=caption,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        # Update ad with TG message ID
        post_url = f"https://t.me/{config.CHANNEL_USERNAME}/{msg.message_id}"
        await db.update_ad_tg(ad_id, msg.message_id, post_url)

        # Clear state
        await db.clear_state(user_id)

        # Set 3 reactions
        try:
            await bot.set_message_reaction(
                chat_id=f"@{config.CHANNEL_USERNAME}",
                message_id=msg.message_id,
                reaction=[{"type": "emoji", "emoji": "👍"}, {"type": "emoji", "emoji": "🔥"}]
            )
        except:
            pass

        await message.reply(
            f"✅ <b>Объявление опубликовано!</b>\n\n"
            f"📢 В канале: {post_url}\n"
            f"🌐 На сайте: {config.SITE_URL}\n\n"
            f"ID объявления: {ad_id}\n"
            f"Напишите /my чтобы увидеть все ваши объявления.",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ad creation failed: {e}")
        await db.clear_state(user_id)
        await message.reply(f"❌ Ошибка при создании объявления: {e}\n\nПопробуйте позже или напишите /start.")

# ─── PLACE FLOW ────────────────────────────────────────────────────────────

async def start_new_place(message: Message):
    """Start place creation flow."""
    u = message.from_user
    if not u: return
    if await db.is_banned(u.id):
        await message.reply("🚫 Вы заблокированы.")
        return
    await db.set_state(u.id, "place_name")
    await message.reply(
        "🏪 <b>Добавление организации</b>\n\n"
        "Шаг 1: отправьте <b>название</b> организации.\n"
        "Например: «Кофейня Утро»\n\n"
        "Для отмены напишите /cancel",
        parse_mode="HTML"
    )

async def handle_place_name(message, bot, user_id, text, data):
    if len(text) < 2 or len(text) > 100:
        await message.reply("❌ Название должно быть 2-100 символов.")
        return
    data["name"] = text
    await db.set_state(user_id, "place_category", json.dumps(data))
    await message.reply(
        f"✅ Название: <b>{escape_html(text)}</b>\n\n"
        f"Шаг 2: укажите <b>категорию</b>.\n"
        f"Например: кафе, магазин, автосервис, салон красоты, аптека, клиника"
    )

async def handle_place_category(message, bot, user_id, text, data):
    data["category"] = text
    await db.set_state(user_id, "place_phone", json.dumps(data))
    await message.reply(
        f"✅ Категория: {text}\n\n"
        f"Шаг 3: укажите <b>телефон</b>.\n"
        f"Например: +7 999 123-45-67\n"
        f"Или напишите «нет» если нет телефона."
    )

async def handle_place_phone(message, bot, user_id, text, data):
    data["phone"] = "" if text.lower() == "нет" else text
    await db.set_state(user_id, "place_city", json.dumps(data))
    await message.reply(
        "✅ Телефон сохранён.\n\n"
        "Шаг 4: укажите <b>город</b>.\n"
        "Например: Москва"
    )

async def handle_place_city(message, bot, user_id, text, data):
    data["city"] = text
    await db.set_state(user_id, "place_desc", json.dumps(data))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Без описания", callback_data="skip_desc")
    ]])
    await message.reply(
        f"✅ Город: {text}\n\n"
        f"Шаг 5: отправьте <b>описание</b> организации.\n"
        f"Что вы предлагаете, часы работы, особенности.\n"
        f"Максимум 500 символов.",
        reply_markup=kb
    )

async def handle_place_desc(message, bot, user_id, text, data):
    if len(text) > 500:
        await message.reply("❌ Описание слишком длинное (максимум 500 символов).")
        return
    data["description"] = text
    await db.set_state(user_id, "place_photo", json.dumps(data))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Без фото", callback_data="skip_place_photo")
    ]])
    await message.reply(
        "✅ Описание сохранено.\n\n"
        "Шаг 6: отправьте <b>фото</b> организации.\n"
        "Можно 1 фото. Или нажмите «Без фото».",
        reply_markup=kb
    )

async def handle_place_photo_step(message, bot, user_id, text, data):
    if text.lower() == "пропустить":
        await finish_place_creation(message, bot, user_id, data, has_photo=False)
    else:
        await message.reply("📸 Отправьте фото или нажмите «Без фото».")

async def handle_place_photo(message, bot, user_id, data):
    await finish_place_creation(message, bot, user_id, data, has_photo=True, photo_message=message)

async def finish_place_creation(message, bot, user_id, data, has_photo=False, photo_message=None):
    """Create place in DB and post to channel."""
    try:
        photo_bytes = None
        if has_photo and photo_message:
            photo_bytes = await download_photo(bot, photo_message)

        place_id = await db.create_place(
            user_id=user_id,
            name=data["name"],
            category=data.get("category", "other"),
            phone=data.get("phone", ""),
            website="",
            address="",
            city=data.get("city", ""),
            lat=0, lng=0,
            description=data.get("description", ""),
            photos=""
        )

        place_data = dict(data)
        caption = format_place_post(place_data, config.SITE_URL)

        if photo_bytes:
            msg = await bot.send_photo(
                chat_id=f"@{config.CHANNEL_USERNAME}",
                photo=photo_bytes,
                caption=caption,
                parse_mode="HTML"
            )
        else:
            msg = await bot.send_message(
                chat_id=f"@{config.CHANNEL_USERNAME}",
                text=caption,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        post_url = f"https://t.me/{config.CHANNEL_USERNAME}/{msg.message_id}"
        await db.update_place_tg(place_id, msg.message_id, post_url)
        await db.clear_state(user_id)

        # Set reactions
        try:
            await bot.set_message_reaction(
                chat_id=f"@{config.CHANNEL_USERNAME}",
                message_id=msg.message_id,
                reaction=[{"type": "emoji", "emoji": "👍"}, {"type": "emoji", "emoji": "👏"}]
            )
        except:
            pass

        await message.reply(
            f"✅ <b>Организация опубликована!</b>\n\n"
            f"📢 В канале: {post_url}\n"
            f"🌐 На сайте: {config.SITE_URL}\n\n"
            f"ID: {place_id}",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Place creation failed: {e}")
        await db.clear_state(user_id)
        await message.reply(f"❌ Ошибка: {e}")

# ─── Callback handlers ─────────────────────────────────────────────────────

@flow_router.callback_query(F.data == "action_new_ad")
async def cb_new_ad(callback: CallbackQuery):
    await callback.answer()
    await start_new_ad(callback.message)

@flow_router.callback_query(F.data == "action_new_place")
async def cb_new_place(callback: CallbackQuery):
    await callback.answer()
    await start_new_place(callback.message)

@flow_router.callback_query(F.data == "action_my_ads")
async def cb_my_ads(callback: CallbackQuery):
    await callback.answer()
    # Simulate /my command
    callback.message.from_user = callback.from_user
    from bot.handlers.chat import cmd_my
    await cmd_my(callback.message)

@flow_router.callback_query(F.data == "skip_city")
async def cb_skip_city(callback: CallbackQuery):
    await callback.answer()
    u = callback.from_user
    state, data_str = await db.get_state(u.id)
    data = json.loads(data_str) if data_str else {}
    data["city"] = ""
    await db.set_state(u.id, "ad_photo", json.dumps(data))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Без фото", callback_data="skip_photo")
    ]])
    await callback.message.reply(
        "✅ Город пропущен.\n\n"
        "Шаг 5: отправьте <b>фото</b> товара.\n"
        "Можно 1 фото. Или нажмите «Без фото».",
        reply_markup=kb
    )

@flow_router.callback_query(F.data == "skip_photo")
async def cb_skip_photo(callback: CallbackQuery):
    await callback.answer()
    u = callback.from_user
    state, data_str = await db.get_state(u.id)
    data = json.loads(data_str) if data_str else {}
    await finish_ad_creation(callback.message, callback.bot, u.id, data, has_photo=False)

@flow_router.callback_query(F.data == "skip_desc")
async def cb_skip_desc(callback: CallbackQuery):
    await callback.answer()
    u = callback.from_user
    state, data_str = await db.get_state(u.id)
    data = json.loads(data_str) if data_str else {}
    data["description"] = ""
    await db.set_state(u.id, "place_photo", json.dumps(data))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Без фото", callback_data="skip_place_photo")
    ]])
    await callback.message.reply(
        "✅ Описание пропущено.\n\n"
        "Шаг 6: отправьте <b>фото</b> организации.\n"
        "Или нажмите «Без фото».",
        reply_markup=kb
    )

@flow_router.callback_query(F.data == "skip_place_photo")
async def cb_skip_place_photo(callback: CallbackQuery):
    await callback.answer()
    u = callback.from_user
    state, data_str = await db.get_state(u.id)
    data = json.loads(data_str) if data_str else {}
    await finish_place_creation(callback.message, callback.bot, u.id, data, has_photo=False)

@flow_router.callback_query(F.data.startswith("boost_"))
async def cb_boost(callback: CallbackQuery):
    await callback.answer("Для буста откройте объявление на сайте", show_alert=True)
