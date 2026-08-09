from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.database import Database
from bot.keyboards.reply import main_menu_kb, promo_packages_kb
from bot.states import PromoStates
from bot.utils.subscription import require_subscription
from bot.utils.texts import t

router = Router(name="promo")


def _fmt(amount: int) -> str:
    return f"{amount:,}"


def _package_label(pkg: dict, lang: str | None) -> str:
    return t(
        "promo_package_button", lang,
        name=pkg["name"], price=_fmt(pkg["price"]), available=pkg["available"],
    )


async def _show_packages(message: Message, db: Database, state: FSMContext, lang: str | None) -> bool:
    """Faol paketlarni reply-klaviatura qilib chiqaradi. Paket topilmasa False qaytaradi."""
    packages = await db.list_promo_packages_with_counts(active_only=True)
    if not packages:
        await state.clear()
        await message.answer(t("promo_no_packages", lang), reply_markup=main_menu_kb(lang))
        return False
    await state.set_state(PromoStates.choosing_package)
    await state.update_data(package_ids=[p["id"] for p in packages])
    await message.answer(t("promo_choose_package", lang), reply_markup=promo_packages_kb(packages, lang))
    return True


@router.message(F.text.in_({t("btn_promo", "uz"), t("btn_promo", "ru")}))
async def btn_promo(message: Message, db: Database, bot: Bot, state: FSMContext) -> None:
    user = await db.get_user(message.from_user.id)
    lang = user["language"] if user else None

    # TZ: "Har bir muhim amalda obuna qayta tekshirilsin"
    if not await require_subscription(message, db, bot, lang):
        return

    await _show_packages(message, db, state, lang)


@router.message(PromoStates.choosing_package, F.text.in_({t("btn_back_menu", "uz"), t("btn_back_menu", "ru")}))
async def promo_back_to_menu(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(message.from_user.id)
    lang = user["language"] if user else None
    await message.answer(t("main_menu_header", lang, id=message.from_user.id), reply_markup=main_menu_kb(lang))


@router.message(PromoStates.choosing_package, F.text)
async def promo_package_chosen(message: Message, db: Database, bot: Bot, state: FSMContext) -> None:
    user = await db.get_user(message.from_user.id)
    lang = user["language"] if user else None

    if not await require_subscription(message, db, bot, lang):
        return

    data = await state.get_data()
    known_ids = set(data.get("package_ids", []))
    packages = await db.list_promo_packages_with_counts(active_only=True)

    matched = next(
        (pkg for pkg in packages if pkg["id"] in known_ids and _package_label(pkg, lang) == message.text),
        None,
    )

    if matched is None:
        # Tugma matni mos kelmadi — ehtimol narx/miqdor shu orada o'zgargan.
        # Ro'yxatni yangilab qayta ko'rsatamiz.
        await _show_packages(message, db, state, lang)
        return

    await state.clear()
    status, code = await db.purchase_promo_code(message.from_user.id, matched["id"])

    if status == "not_found":
        await message.answer(t("promo_not_found", lang), reply_markup=main_menu_kb(lang))
    elif status == "insufficient":
        balance = user["balance"] if user else 0
        await message.answer(
            t("promo_insufficient", lang, name=matched["name"], price=_fmt(matched["price"]), balance=_fmt(balance)),
            reply_markup=main_menu_kb(lang),
        )
    elif status == "empty":
        await message.answer(t("promo_empty", lang), reply_markup=main_menu_kb(lang))
    else:
        await message.answer(
            t("promo_success", lang, name=matched["name"], code=code, price=_fmt(matched["price"])),
            reply_markup=main_menu_kb(lang),
        )
