import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import CallbackQuery, Message

from bot.database import Database
from bot.keyboards.inline import language_kb, subscription_kb
from bot.keyboards.reply import main_menu_kb
from bot.utils.subscription import is_subscribed
from bot.utils.texts import t

logger = logging.getLogger(__name__)
router = Router(name="start")


def _parse_start_payload(command: CommandObject | None) -> tuple[int | None, str | None]:
    """start payload'ni tahlil qiladi: ref_<id> yoki oyin_<campaign_id>.
    Qaytaradi: (referrer_id, campaign_id)"""
    if not command or not command.args:
        return None, None
    arg = command.args
    if arg.startswith("ref_") and arg[4:].isdigit():
        return int(arg[4:]), None
    if arg.startswith("oyin_"):
        return None, arg[5:]
    return None, None


async def _show_main_menu(message: Message, lang: str | None) -> None:
    await message.answer(
        t("main_menu_header", lang, id=message.chat.id),
        reply_markup=main_menu_kb(lang),
    )


async def _proceed_after_subscription(bot: Bot, db: Database, user_id: int,
                                       chat_id: int, send) -> None:
    """Obuna tasdiqlangandan keyingi qadam: til tanlanmagan bo'lsa so'raymiz,
    aks holda asosiy menyuni ko'rsatamiz. `send` — message.answer yoki callback javobi uchun funksiya."""
    user = await db.get_user(user_id)
    if user is None or not user["is_registered"]:
        await send(t("choose_language", None), reply_markup=language_kb())
        return
    await send(
        t("main_menu_header", user["language"], id=user_id),
        reply_markup=main_menu_kb(user["language"]),
    )


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, db: Database, bot: Bot) -> None:
    referrer_id, campaign_id = _parse_start_payload(command)

    await db.upsert_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        referrer_id=referrer_id if referrer_id != message.from_user.id else None,
    )

    channels = await db.get_required_channels()
    if channels and not await is_subscribed(bot, message.from_user.id, channels):
        user = await db.get_user(message.from_user.id)
        lang = user["language"] if user else None
        await message.answer(
            t("subscribe_required", lang),
            reply_markup=subscription_kb(channels, lang),
        )
        return

    # TODO (keyingi bosqich — 7-bo'lim): campaign_id mavjud bo'lsa, meva captcha ko'rsatish.
    await _proceed_after_subscription(bot, db, message.from_user.id, message.chat.id, message.answer)


@router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(call: CallbackQuery, db: Database, bot: Bot) -> None:
    channels = await db.get_required_channels()
    user = await db.get_user(call.from_user.id)
    lang = user["language"] if user else None

    if channels and not await is_subscribed(bot, call.from_user.id, channels):
        await call.answer(t("subscribe_missing", lang), show_alert=True)
        return

    await call.answer(t("subscribe_ok", lang))
    await call.message.delete()
    await _proceed_after_subscription(bot, db, call.from_user.id, call.message.chat.id, call.message.answer)


@router.callback_query(F.data.startswith("lang_"))
async def cb_set_language(call: CallbackQuery, db: Database) -> None:
    lang = call.data.split("_", 1)[1]  # "uz" | "ru"

    # Bonus bir marta berilishi uchun — til birinchi marta tanlanyaptimi, oldindan tekshiramiz.
    user_before = await db.get_user(call.from_user.id)
    was_registered = bool(user_before and user_before["is_registered"])
    referrer_id = user_before["referrer_id"] if user_before else None

    await db.set_language(call.from_user.id, lang)

    if not was_registered and referrer_id:
        await db.apply_referral_bonus(referrer_id)

    await call.answer()
    await call.message.delete()
    await _show_main_menu(call.message, lang)


@router.message(Command("til"))
async def cmd_change_language(message: Message) -> None:
    await message.answer(t("choose_language", None), reply_markup=language_kb())
