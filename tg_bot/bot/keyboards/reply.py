from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from bot.utils.texts import t


def main_menu_kb(lang: str | None) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text=t("btn_balance", lang))
    kb.button(text=t("btn_topup", lang))
    kb.button(text=t("btn_promo", lang))
    kb.button(text=t("btn_referral", lang))
    kb.adjust(2, 2)
    return kb.as_markup(resize_keyboard=True)
