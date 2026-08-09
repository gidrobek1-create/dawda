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


def promo_packages_kb(packages: list[dict], lang: str | None) -> ReplyKeyboardMarkup:
    """Promo paketlarni rasmdagidek to'liq kenglikdagi, bir-birining ustida
    joylashgan reply-tugmalar qilib chiqaradi (inline emas)."""
    kb = ReplyKeyboardBuilder()
    for pkg in packages:
        kb.button(text=t(
            "promo_package_button", lang,
            name=pkg["name"], price=f"{pkg['price']:,}", available=pkg["available"],
        ))
    kb.button(text=t("btn_back_menu", lang))
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)
