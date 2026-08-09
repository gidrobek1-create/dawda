from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database import Database
from bot.utils.texts import t

router = Router(name="balance")


def _history_kb(lang: str | None):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("history_button", lang), callback_data="show_history")
    return kb.as_markup()


@router.message(F.text.in_({t("btn_balance", "uz"), t("btn_balance", "ru")}))
async def btn_balance(message: Message, db: Database) -> None:
    user = await db.get_user(message.from_user.id)
    lang = user["language"] if user else None
    balance = user["balance"] if user else 0
    await message.answer(
        t("balance_info", lang, balance=balance),
        reply_markup=_history_kb(lang),
    )


@router.callback_query(F.data == "show_history")
async def cb_show_history(call: CallbackQuery, db: Database) -> None:
    user = await db.get_user(call.from_user.id)
    lang = user["language"] if user else None
    history = await db.get_purchase_history(call.from_user.id)

    lines = []
    for p in history["payments"]:
        lines.append(t("history_payment_line", lang, date=p["created_at"].strftime("%Y-%m-%d %H:%M"), amount=p["amount"]))
    for pr in history["promos"]:
        used_at = pr["used_at"].strftime("%Y-%m-%d %H:%M") if pr["used_at"] else "-"
        lines.append(t(
            "history_promo_line", lang,
            date=used_at, code=pr["code"], price=pr["price_paid"] or 0,
            name=pr["package_name"] or "Promokod",
        ))

    await call.answer()
    if not lines:
        await call.message.answer(t("history_empty", lang))
        return

    lines.sort(reverse=True)
    text = t("history_header", lang) + "\n\n" + "\n".join(lines[:20])
    await call.message.answer(text)
