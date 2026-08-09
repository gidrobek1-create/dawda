from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.texts import t


def language_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    kb.button(text="🇷🇺 Русский", callback_data="lang_ru")
    kb.adjust(2)
    return kb.as_markup()


def subscription_kb(channels, lang: str | None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for ch in channels:
        title = ch["title"] or ch["chat_id"]
        link = ch["invite_link"] or f"https://t.me/{str(ch['chat_id']).lstrip('@')}"
        kb.row(InlineKeyboardButton(text=f"📢 {title}", url=link))
    kb.row(InlineKeyboardButton(text=t("check_button", lang), callback_data="check_subscription"))
    return kb.as_markup()
