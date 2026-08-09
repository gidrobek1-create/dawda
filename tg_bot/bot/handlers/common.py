from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.database import Database
from bot.utils.texts import t

router = Router(name="common")


@router.message(Command("bekor"))
async def cmd_cancel(message: Message, state: FSMContext, db: Database) -> None:
    user = await db.get_user(message.from_user.id)
    lang = user["language"] if user else None

    current = await state.get_state()
    if current is None:
        await message.answer(t("nothing_to_cancel", lang))
        return

    await state.clear()
    await message.answer(t("cancelled", lang))
