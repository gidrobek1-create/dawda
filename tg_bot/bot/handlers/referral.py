from aiogram import Bot, F, Router
from aiogram.types import Message

from bot.database import Database
from bot.utils.texts import t

router = Router(name="referral")


@router.message(F.text.in_({t("btn_referral", "uz"), t("btn_referral", "ru")}))
async def btn_referral(message: Message, db: Database, bot: Bot) -> None:
    user = await db.get_user(message.from_user.id)
    lang = user["language"] if user else None

    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{message.from_user.id}"

    stats = await db.get_referral_stats(message.from_user.id)
    await message.answer(
        t("referral_info", lang, link=link, count=stats["count"], total=stats["total_earned"])
    )
