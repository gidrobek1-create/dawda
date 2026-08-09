from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database import Database
from bot.keyboards.inline import subscription_kb
from bot.utils.subscription import is_subscribed, require_subscription
from bot.utils.texts import t

router = Router(name="promo")


def _packages_kb(packages: list[dict], lang: str | None):
    kb = InlineKeyboardBuilder()
    for pkg in packages:
        kb.button(
            text=t(
                "promo_package_button", lang,
                name=pkg["name"], price=pkg["price"], available=pkg["available"],
            ),
            callback_data=f"promo:buy:{pkg['id']}",
        )
    kb.adjust(1)
    return kb.as_markup()


@router.message(F.text.in_({t("btn_promo", "uz"), t("btn_promo", "ru")}))
async def btn_promo(message: Message, db: Database, bot: Bot) -> None:
    user = await db.get_user(message.from_user.id)
    lang = user["language"] if user else None

    # TZ: "Har bir muhim amalda obuna qayta tekshirilsin"
    if not await require_subscription(message, db, bot, lang):
        return

    packages = await db.list_promo_packages_with_counts(active_only=True)
    if not packages:
        await message.answer(t("promo_no_packages", lang))
        return

    await message.answer(t("promo_choose_package", lang), reply_markup=_packages_kb(packages, lang))


@router.callback_query(F.data.startswith("promo:buy:"))
async def cb_promo_buy(call: CallbackQuery, db: Database, bot: Bot) -> None:
    user = await db.get_user(call.from_user.id)
    lang = user["language"] if user else None

    # require_subscription Message.from_user'ga tayanadi — call.message bu yerda botning
    # o'z xabari bo'lgani uchun tekshiruvni to'g'ridan-to'g'ri call.from_user bilan qilamiz.
    channels = await db.get_required_channels()
    if channels and not await is_subscribed(bot, call.from_user.id, channels):
        await call.answer()
        await call.message.answer(t("subscribe_required", lang), reply_markup=subscription_kb(channels, lang))
        return

    package_id = int(call.data.split(":")[-1])
    package = await db.get_promo_package(package_id)
    if package is None or not package["active"]:
        await call.answer()
        await call.message.answer(t("promo_not_found", lang))
        return

    await call.answer()
    status, code = await db.purchase_promo_code(call.from_user.id, package_id)

    if status == "not_found":
        await call.message.answer(t("promo_not_found", lang))
        return
    if status == "insufficient":
        balance = user["balance"] if user else 0
        await call.message.answer(
            t("promo_insufficient", lang, name=package["name"], price=package["price"], balance=balance)
        )
        return
    if status == "empty":
        await call.message.answer(t("promo_empty", lang))
        return

    await call.message.answer(t("promo_success", lang, name=package["name"], code=code, price=package["price"]))
