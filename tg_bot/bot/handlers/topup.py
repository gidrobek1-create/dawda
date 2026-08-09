import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database import Database
from bot.states import TopUpStates
from bot.utils.texts import t

logger = logging.getLogger(__name__)
router = Router(name="topup")


def _admin_review_kb(payment_id: int, lang: str | None):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("admin_btn_approve", lang), callback_data=f"pay_approve:{payment_id}")
    kb.button(text=t("admin_btn_reject", lang), callback_data=f"pay_reject:{payment_id}")
    kb.adjust(2)
    return kb.as_markup()


@router.message(F.text.in_({t("btn_topup", "uz"), t("btn_topup", "ru")}))
async def btn_topup(message: Message, db: Database, state: FSMContext) -> None:
    user = await db.get_user(message.from_user.id)
    lang = user["language"] if user else None

    card_number = await db.get_setting("card_number", "-")
    card_holder = await db.get_setting("card_holder", "-")

    await state.set_state(TopUpStates.waiting_photo)
    await message.answer(
        t("topup_card_info", lang, card_number=card_number, card_holder=card_holder) + t("cancel_hint", lang),
    )


@router.message(TopUpStates.waiting_photo, F.photo)
async def got_receipt_photo(message: Message, db: Database, state: FSMContext) -> None:
    user = await db.get_user(message.from_user.id)
    lang = user["language"] if user else None

    file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=file_id)
    await state.set_state(TopUpStates.waiting_amount)
    await message.answer(t("topup_ask_amount", lang) + t("cancel_hint", lang))


@router.message(TopUpStates.waiting_photo)
async def waiting_photo_wrong_type(message: Message, db: Database) -> None:
    user = await db.get_user(message.from_user.id)
    lang = user["language"] if user else None
    await message.answer(t("topup_send_photo", lang) + t("cancel_hint", lang))


@router.message(TopUpStates.waiting_amount, F.text)
async def got_amount(message: Message, db: Database, state: FSMContext, bot: Bot) -> None:
    user = await db.get_user(message.from_user.id)
    lang = user["language"] if user else None

    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer(t("topup_invalid_amount", lang) + t("cancel_hint", lang))
        return
    amount = int(text)

    limit_raw = await db.get_setting("payment_request_limit_per_hour", "3")
    limit = int(limit_raw) if limit_raw and limit_raw.isdigit() else 3
    recent_count = await db.count_recent_payment_requests(message.from_user.id, minutes=60)
    if recent_count >= limit:
        await state.clear()
        await message.answer(t("topup_spam_limit", lang))
        return

    data = await state.get_data()
    photo_file_id = data.get("photo_file_id")
    await state.clear()

    payment_id = await db.create_payment(message.from_user.id, photo_file_id, amount)

    admin_ids = await db.get_all_admin_ids()
    caption = t(
        "admin_new_payment",
        None,
        user_id=message.from_user.id,
        username=message.from_user.username or "-",
        amount=amount,
    )
    for admin_id in admin_ids:
        try:
            sent = await bot.send_photo(
                chat_id=admin_id,
                photo=photo_file_id,
                caption=caption,
                reply_markup=_admin_review_kb(payment_id, None),
            )
            await db.add_payment_notification(payment_id, admin_id, admin_id, sent.message_id)
        except Exception as e:
            logger.warning("Adminga (%s) xabar yuborilmadi: %s", admin_id, e)

    await message.answer(t("topup_sent_to_admins", lang))
