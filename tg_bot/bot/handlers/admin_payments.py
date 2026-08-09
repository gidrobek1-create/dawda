import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.database import Database
from bot.states import AdminRejectStates
from bot.utils.texts import t

logger = logging.getLogger(__name__)
router = Router(name="admin_payments")


async def _is_admin(db: Database, user_id: int) -> bool:
    role = await db.get_admin_role(user_id)
    return role in ("super", "moderator")


async def _update_notifications(bot: Bot, db: Database, payment_id: int, suffix: str) -> None:
    notifications = await db.get_payment_notifications(payment_id)
    for n in notifications:
        try:
            payment = await db.get_payment(payment_id)
            base_caption = t(
                "admin_new_payment",
                None,
                user_id=payment["user_id"],
                username="-",
                amount=payment["amount"],
            )
            await bot.edit_message_caption(
                chat_id=n["chat_id"],
                message_id=n["message_id"],
                caption=base_caption + suffix,
                reply_markup=None,
            )
        except Exception as e:
            logger.warning("Admin xabarini yangilab bo'lmadi (chat=%s): %s", n["chat_id"], e)


@router.callback_query(F.data.startswith("pay_approve:"))
async def cb_approve(call: CallbackQuery, db: Database, bot: Bot) -> None:
    if not await _is_admin(db, call.from_user.id):
        await call.answer(t("admin_no_permission", None), show_alert=True)
        return

    payment_id = int(call.data.split(":", 1)[1])
    ok = await db.resolve_payment(payment_id, approve=True, admin_id=call.from_user.id)
    if not ok:
        await call.answer(t("admin_already_reviewed", None), show_alert=True)
        return

    payment = await db.get_payment(payment_id)
    await call.answer("OK")

    suffix = t("admin_approved_suffix", None, admin=f"@{call.from_user.username or call.from_user.id}")
    await _update_notifications(bot, db, payment_id, suffix)

    user = await db.get_user(payment["user_id"])
    user_lang = user["language"] if user else None
    try:
        await bot.send_message(
            payment["user_id"],
            t("topup_approved_user", user_lang, amount=payment["amount"]),
        )
    except Exception as e:
        logger.warning("Foydalanuvchiga xabar yuborilmadi: %s", e)


@router.callback_query(F.data.startswith("pay_reject:"))
async def cb_reject(call: CallbackQuery, db: Database, state: FSMContext) -> None:
    if not await _is_admin(db, call.from_user.id):
        await call.answer(t("admin_no_permission", None), show_alert=True)
        return

    payment_id = int(call.data.split(":", 1)[1])
    payment = await db.get_payment(payment_id)
    if payment is None or payment["status"] != "pending":
        await call.answer(t("admin_already_reviewed", None), show_alert=True)
        return

    await call.answer()
    await state.set_state(AdminRejectStates.waiting_reason)
    await state.update_data(payment_id=payment_id)
    await call.message.answer(t("admin_ask_reject_reason", None))


@router.message(AdminRejectStates.waiting_reason, F.text)
async def got_reject_reason(message: Message, db: Database, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    payment_id = data.get("payment_id")
    await state.clear()

    reason = message.text.strip()
    ok = await db.resolve_payment(payment_id, approve=False, admin_id=message.from_user.id, reason=reason)
    if not ok:
        await message.answer(t("admin_already_reviewed", None))
        return

    payment = await db.get_payment(payment_id)
    suffix = t(
        "admin_rejected_suffix", None,
        admin=f"@{message.from_user.username or message.from_user.id}", reason=reason,
    )
    await _update_notifications(bot, db, payment_id, suffix)

    user = await db.get_user(payment["user_id"])
    user_lang = user["language"] if user else None
    try:
        await bot.send_message(
            payment["user_id"],
            t("topup_rejected_user", user_lang, reason=reason),
        )
    except Exception as e:
        logger.warning("Foydalanuvchiga xabar yuborilmadi: %s", e)
