import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from bot.database import Database
from bot.keyboards.inline import subscription_kb
from bot.utils.texts import t

logger = logging.getLogger(__name__)

NOT_MEMBER_STATUSES = {"left", "kicked"}


async def _check_one(bot: Bot, user_id: int, chat_id) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status not in NOT_MEMBER_STATUSES
    except TelegramBadRequest as e:
        logger.warning("Obunani tekshirishda xato (%s): %s", chat_id, e)
        return False


async def is_subscribed(bot: Bot, user_id: int, channels) -> bool:
    """Foydalanuvchi barcha majburiy kanallarga obuna bo'lganmi, tekshiradi.
    Kanallar BIR VAQTDA (parallel) tekshiriladi — ilgari ketma-ket bo'lgani uchun
    har bir kanal Telegram API'ga alohida so'rov va shuncha kutish vaqti qo'shardi;
    3-4 ta kanalda bu "✅ Tekshirish" tugmasini sezilarli sekinlashtirar edi."""
    if not channels:
        return True
    results = await asyncio.gather(
        *(_check_one(bot, user_id, ch["chat_id"]) for ch in channels)
    )
    return all(results)


async def require_subscription(message: Message, db: Database, bot: Bot, lang: str | None) -> bool:
    """Muhim amallardan oldin (masalan promo sotib olish) obunani qayta tekshiradi.
    Obuna yo'q bo'lsa — xabar yuboradi va False qaytaradi (chaqiruvchi davom etmasligi kerak)."""
    channels = await db.get_required_channels()
    if not channels:
        return True
    if await is_subscribed(bot, message.from_user.id, channels):
        return True
    await message.answer(t("subscribe_required", lang), reply_markup=subscription_kb(channels, lang))
    return False
