"""Telepost Media Handler — download photos for channel posting."""
import logging
from aiogram import Bot
from aiogram.types import Message

logger = logging.getLogger("telepost.media")

async def download_photo(bot: Bot, message: Message) -> bytes | None:
    """Download the largest photo from a message. Returns raw bytes or None."""
    try:
        if not message.photo:
            return None
        # Get the largest photo
        photo = message.photo[-1]
        if photo.file_size and photo.file_size > 10_000_000:  # 10MB limit
            logger.warning(f"Photo too large: {photo.file_size}")
            return None

        file = await bot.get_file(photo.file_id)
        if not file.file_path:
            return None

        # Download using bot.download
        downloaded = await bot.download_file(file.file_path)
        if downloaded is None:
            return None

        raw = downloaded.read() if hasattr(downloaded, "read") else bytes(downloaded)
        if not raw:
            return None

        logger.info(f"Downloaded photo: {len(raw)} bytes")
        return raw
    except Exception as e:
        logger.error(f"Photo download error: {e}")
        return None

async def collect_photos(bot: Bot, message: Message) -> list[bytes]:
    """Collect all photos from a message (for media groups, only first photo)."""
    photos = []
    photo_data = await download_photo(bot, message)
    if photo_data:
        photos.append(photo_data)
    return photos

def extract_caption(message: Message) -> str:
    """Extract caption or text from message."""
    return (message.caption or message.text or "").strip()
