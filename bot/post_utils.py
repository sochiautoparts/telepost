"""Telepost Post Utilities — formatting, validation, category mapping."""
import re
import logging
from typing import Optional

logger = logging.getLogger("telepost.post")

# Category mapping: keywords → our categories
CATEGORY_KEYWORDS = {
    "elektronika": ["телефон", "смартфон", "iphone", "samsung", "ноутбук", "macbook", "планшет", "ipad", "компьютер", "pc", "наушники", "колонка", "зарядк", "кабель", "чехол", "стекло", "ксерокс", "принтер", "монитор", "клавиатура", "мышь", "webcam"],
    "avto": ["авто", "машина", "toyota", "bmw", "mercedes", "audi", "vaz", "лада", "запчаст", "шины", "диски", "колес", "мотор", "двигатель", "масло", "аккумулятор", "мото", "мотороллер"],
    "nedvizhimost": ["квартир", "дом", "дача", "участок", "земля", "коммерческ", "офис", "аренда", "продаю квартиру", "студия", "комната"],
    "uslugi": ["услуги", "ремонт", "электрик", "сантехник", "грузоперевозк", "переезд", "уборка", "маникюр", "стрижка", "массаж", "репетитор", "перевод"],
    "rabota": ["работа", "ваканси", "ищу", "требуется", "нужен", "оператор", "менеджер", "программист", "дизайнер", "водитель", "охранник", "кухня", "повар"],
    "moda": ["одежд", "куртк", "платье", "рубашк", "брюки", "джинсы", "обувь", "кроссовки", "сапоги", "сумка", "рюкзак", "часы", "кольцо", "цепочка"],
    "dom-sad": ["мебель", "диван", "кровать", "шкаф", "стол", "стул", "холодильник", "стиральн", "пылесос", "телевизор", "инструмент", "дрель", "перфоратор"],
    "hobbi": ["велосипед", "самокат", "коньки", "лыжи", "сноуборд", "удочка", "палатка", "гитара", "синтезатор", "книга", "игры", "playstation", "xbox", "nintendo"],
    "eda": ["продукты", "овощи", "фрукты", "мясо", "рыба", "выпечка", "торт", "напитки", "чай", "кофе", "алкоголь", "вино", "пиво"],
}

def detect_category(title: str, description: str = "") -> str:
    """Detect category from title and description by keywords."""
    text = (title + " " + description).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return "other"

def format_price(price: float, currency: str = "RUB") -> str:
    """Format price with currency symbol."""
    symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "KZT": "₸", "UAH": "₴", "BYN": "Br"}
    symbol = symbols.get(currency, currency)
    return f"{int(price):,} {symbol}".replace(",", " ")

def format_ad_post(ad: dict, site_url: str = "https://telepost.space") -> str:
    """Format ad data into a Telegram channel post caption."""
    lines = []
    lines.append(f"📢 <b>{escape_html(ad.get('title', ''))}</b>")

    if ad.get("price"):
        price_str = format_price(ad["price"], ad.get("currency", "RUB"))
        lines.append(f"💰 <b>{price_str}</b>")

    category = ad.get("category", "other")
    lines.append(f"📂 {category}")

    if ad.get("city"):
        lines.append(f"📍 {escape_html(ad['city'])}")

    if ad.get("address"):
        lines.append(f"🏷 {escape_html(ad['address'])}")

    lines.append("")  # Empty line

    desc = ad.get("description", "")
    if desc:
        # Truncate to 800 chars (Telegram caption limit is 1024)
        if len(desc) > 800:
            desc = desc[:797] + "..."
        lines.append(escape_html(desc))

    lines.append("")
    lines.append(f"🌐 <a href=\"{site_url}\">Telepost.Space</a>")

    return "\n".join(lines)

def format_place_post(place: dict, site_url: str = "https://telepost.space") -> str:
    """Format place/organization data into a channel post."""
    lines = []
    lines.append(f"🏪 <b>{escape_html(place.get('name', ''))}</b>")

    category = place.get("category", "other")
    lines.append(f"📂 {category}")

    if place.get("phone"):
        lines.append(f"📞 {escape_html(place['phone'])}")

    if place.get("website"):
        lines.append(f"🌐 <a href=\"{escape_html(place['website'])}\">Сайт</a>")

    if place.get("address"):
        lines.append(f"📍 {escape_html(place['address'])}")

    if place.get("city"):
        lines.append(f"🏙 {escape_html(place['city'])}")

    lines.append("")

    desc = place.get("description", "")
    if desc:
        if len(desc) > 600:
            desc = desc[:597] + "..."
        lines.append(escape_html(desc))

    lines.append("")
    lines.append(f"🌐 <a href=\"{site_url}\">Telepost.Space</a>")

    return "\n".join(lines)

def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def validate_title(title: str) -> tuple[bool, str]:
    """Validate ad title."""
    if not title or len(title.strip()) < 3:
        return False, "Заголовок слишком короткий (минимум 3 символа)"
    if len(title) > 100:
        return False, "Заголовок слишком длинный (максимум 100 символов)"
    return True, ""

def validate_price(price_str: str) -> tuple[bool, float, str]:
    """Parse and validate price. Returns (ok, price, error)."""
    if not price_str or price_str.lower() in ["договорная", "договор", "бесплатно", "free"]:
        return True, 0, ""
    try:
        # Remove spaces, currency symbols
        clean = re.sub(r"[^\d.,]", "", price_str.replace(",", "."))
        if not clean:
            return True, 0, ""
        price = float(clean)
        if price < 0:
            return False, 0, "Цена не может быть отрицательной"
        if price > 1000000000:
            return False, 0, "Слишком большая цена"
        return True, price, ""
    except:
        return False, 0, "Не удалось распознать цену"

# Spam detection (simple, without AI)
SPAM_KEYWORDS = ["casino", "ставки", "1win", "melbet", "заработок", "криптовалюта бесплатно", "развод", "пирамида", "млм", "mlm"]

def is_spam(text: str) -> bool:
    """Simple spam detection without AI."""
    lower = text.lower()
    return any(kw in lower for kw in SPAM_KEYWORDS)
