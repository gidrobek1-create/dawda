"""
Yagona admin panel — /admin.

Ilgari sozlamalar bir nechta alohida buyruq bilan boshqarilardi
(/setcard, /setpromoprice, /setreferralbonus, /setpaymentlimit, /addpromo,
/promostats, /addadmin) — bularni eslab yurish qulay emas edi.
Endi hammasi bitta tugmali menyuda: /admin → bo'limni tanlang → qiymatni yozing.
"""

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database import Database
from bot.states import AdminStates

logger = logging.getLogger(__name__)
router = Router(name="admin_panel")


# ---------- yordamchi funksiyalar ----------

async def _role(db: Database, user_id: int) -> str | None:
    return await db.get_admin_role(user_id)


async def _send_or_edit(target, text: str, kb=None) -> None:
    """CallbackQuery bo'lsa mavjud xabarni tahrirlaydi (panel bir joyda "yashaydi"),
    Message bo'lsa yangi xabar yuboradi."""
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb)
        except Exception:
            await target.message.answer(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 To'lov karta", callback_data="adm:card")
    kb.button(text="🔗 Referal bonusi", callback_data="adm:refbonus")
    kb.button(text="⏱ To'lov limiti", callback_data="adm:paylimit")
    kb.button(text="📢 Majburiy kanallar", callback_data="adm:channels")
    kb.button(text="🎟 Promo paketlar", callback_data="adm:promopkgs")
    kb.button(text="👥 Adminlar", callback_data="adm:admins")
    kb.button(text="📊 Statistika", callback_data="adm:stats")
    kb.adjust(2, 2, 1, 2)
    return kb.as_markup()


def back_kb(target: str = "adm:menu"):
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Orqaga", callback_data=target)
    return kb.as_markup()


async def _show_main_menu(target) -> None:
    await _send_or_edit(
        target,
        "⚙️ <b>Admin panel</b>\n\nQaysi bo'limni sozlaymiz?",
        main_menu_kb(),
    )


# ---------- /admin ----------

@router.message(Command("admin"))
async def cmd_admin(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    role = await _role(db, message.from_user.id)
    if role is None:
        return  # oddiy foydalanuvchiga bunday buyruq borligini bildirmaymiz
    if role != "super":
        await message.answer(
            "👮 Siz <b>moderator</b>siz.\n\n"
            "To'lov so'rovlari sizga alohida xabar bo'lib keladi — "
            "ularni to'g'ridan-to'g'ri o'sha xabar ostidagi ✅/❌ tugmalari orqali "
            "hal qilasiz. Sozlamalar bo'limi faqat super-adminlarga ochiq."
        )
        return
    await _show_main_menu(message)


@router.callback_query(F.data == "adm:menu")
async def cb_menu(call: CallbackQuery, db: Database, state: FSMContext) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    await state.clear()
    await call.answer()
    await _show_main_menu(call)


# ---------- oddiy "matn kiriting" sozlamalar (karta, narx, bonus, limit) ----------

_SIMPLE_SETTINGS = {
    "adm:card": (
        AdminStates.waiting_card,
        "💳 Yangi karta ma'lumotini yuboring:\n<code>karta raqami|egasining ismi</code>\n\n"
        "Masalan: <code>8600 1234 5678 9012|Alisher Aliyev</code>",
    ),
    "adm:refbonus": (
        AdminStates.waiting_ref_bonus,
        "🔗 Referal uchun beriladigan bonus summasini (so'mda) yuboring:",
    ),
    "adm:paylimit": (
        AdminStates.waiting_pay_limit,
        "⏱ Bir foydalanuvchi 1 soatda nechta to'lov so'rovi yubora olishi mumkinligini yuboring:",
    ),
}


@router.callback_query(F.data.in_(_SIMPLE_SETTINGS.keys()))
async def cb_ask_simple_setting(call: CallbackQuery, db: Database, state: FSMContext) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    target_state, prompt = _SIMPLE_SETTINGS[call.data]
    await call.answer()
    await state.set_state(target_state)
    await state.update_data(return_to=call.data)
    await _send_or_edit(call, prompt + "\n\nBekor qilish uchun /bekor.", back_kb())


@router.message(AdminStates.waiting_card, F.text)
async def got_card(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    if "|" not in message.text:
        await message.answer("❌ Format noto'g'ri. Namuna: 8600 1234 5678 9012|Ism Familiya")
        return
    number, holder = message.text.split("|", 1)
    await db.set_setting("card_number", number.strip())
    await db.set_setting("card_holder", holder.strip())
    await message.answer(f"✅ Karta yangilandi:\n<b>{number.strip()}</b>\n{holder.strip()}")
    await _show_main_menu(message)


@router.message(AdminStates.waiting_ref_bonus, F.text)
async def got_ref_bonus(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Faqat raqam kiriting.")
        return
    await db.set_setting("referral_bonus_l1", text)
    await message.answer(f"✅ Referal bonusi: <b>{text} so'm</b>")
    await _show_main_menu(message)


@router.message(AdminStates.waiting_pay_limit, F.text)
async def got_pay_limit(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❌ Faqat musbat raqam kiriting.")
        return
    await db.set_setting("payment_request_limit_per_hour", text)
    await message.answer(f"✅ Soatlik to'lov so'rovi limiti: <b>{text}</b>")
    await _show_main_menu(message)


# ---------- Majburiy kanallar ----------

async def _channels_text_and_kb(db: Database):
    channels = await db.get_required_channels()
    kb = InlineKeyboardBuilder()
    if not channels:
        text = (
            "📢 <b>Majburiy kanallar</b>\n\n"
            "Hozircha birorta ham kanal qo'shilmagan — bu holatda bot obunani "
            "umuman tekshirmaydi va foydalanuvchi to'g'ridan-to'g'ri botdan foydalana oladi.\n\n"
            "Kanal qo'shish uchun pastdagi tugmani bosing."
        )
    else:
        lines = ["📢 <b>Majburiy kanallar</b>\n"]
        for ch in channels:
            lines.append(f"• {ch['title'] or ch['chat_id']}")
            kb.button(text=f"🗑 {ch['title'] or ch['chat_id']}", callback_data=f"adm:ch_del:{ch['id']}")
        lines.append("\nO'chirish uchun kerakli kanalni bosing.")
        text = "\n".join(lines)
    kb.button(text="➕ Kanal qo'shish", callback_data="adm:ch_add")
    kb.button(text="⬅️ Orqaga", callback_data="adm:menu")
    kb.adjust(1)
    return text, kb.as_markup()


@router.callback_query(F.data == "adm:channels")
async def cb_channels(call: CallbackQuery, db: Database) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    await call.answer()
    text, kb = await _channels_text_and_kb(db)
    await _send_or_edit(call, text, kb)


@router.callback_query(F.data == "adm:ch_add")
async def cb_channel_add(call: CallbackQuery, db: Database, state: FSMContext) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    await call.answer()
    await state.set_state(AdminStates.waiting_channel)
    await _send_or_edit(
        call,
        "📢 Kanalni yuboring:\n"
        "— kanal usernamesi (masalan <code>@mychannel</code>), yoki\n"
        "— shu kanaldan istalgan xabarni forward qiling (yopiq kanallar uchun ham ishlaydi).\n\n"
        "❗️ <b>Muhim:</b> bot o'sha kanalda admin bo'lishi shart — aks holda "
        "obunani tekshira olmaydi.\n\nBekor qilish uchun /bekor.",
        back_kb("adm:channels"),
    )


@router.message(AdminStates.waiting_channel)
async def got_channel(message: Message, db: Database, state: FSMContext, bot: Bot) -> None:
    await state.clear()

    chat_ref = None
    if message.forward_from_chat:
        chat_ref = message.forward_from_chat.id
    elif message.text:
        text = message.text.strip()
        chat_ref = text if text.startswith(("@", "-100")) else f"@{text.lstrip('@')}"

    if chat_ref is None:
        await message.answer("❌ Kanalni aniqlab bo'lmadi. Qaytadan /admin dan urinib ko'ring.")
        return

    try:
        chat = await bot.get_chat(chat_ref)
    except Exception as e:
        await message.answer(
            f"❌ Kanalni topib bo'lmadi yoki bot u yerda a'zo/admin emas.\nXato: {e}"
        )
        return

    invite_link = None
    if chat.username:
        invite_link = f"https://t.me/{chat.username}"
    else:
        try:
            invite_link = await bot.export_chat_invite_link(chat.id)
        except Exception as e:
            logger.warning("Taklif havolasini olib bo'lmadi (%s): %s", chat.id, e)

    await db.add_required_channel(str(chat.id), chat.title, invite_link)
    await message.answer(f"✅ Kanal qo'shildi: <b>{chat.title}</b>")
    text, kb = await _channels_text_and_kb(db)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("adm:ch_del:"))
async def cb_channel_del(call: CallbackQuery, db: Database) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    channel_id = int(call.data.split(":")[-1])
    await db.remove_required_channel(channel_id)
    await call.answer("🗑 O'chirildi")
    text, kb = await _channels_text_and_kb(db)
    await _send_or_edit(call, text, kb)


# ---------- Promo paketlar ----------
# Har bir paket alohida narx va kodlar zaxirasiga ega (masalan "42 lik — 1500 so'm").
# Foydalanuvchiga xuddi shu ro'yxat "🎁 {nomi} — {narxi} so'm ({mavjudi} ta bor)"
# ko'rinishida chiqadi (bot/handlers/promo.py).

async def _promopkgs_text_and_kb(db: Database):
    packages = await db.list_promo_packages_with_counts()
    kb = InlineKeyboardBuilder()
    if not packages:
        text = (
            "🎟 <b>Promo paketlar</b>\n\n"
            "Hozircha birorta ham paket yo'q. Pastdagi tugma orqali qo'shing "
            "(masalan: nomi — <code>42 lik</code>, narxi — <code>1500</code>)."
        )
    else:
        lines = ["🎟 <b>Promo paketlar</b>\n"]
        for pkg in packages:
            status = "✅" if pkg["active"] else "🚫"
            lines.append(
                f"{status} <b>{pkg['name']}</b> — {pkg['price']} so'm "
                f"(mavjud: {pkg['available']}, ishlatilgan: {pkg['used']})"
            )
            kb.button(text=f"✏️ {pkg['name']}", callback_data=f"adm:pkg:{pkg['id']}")
        text = "\n".join(lines)
    kb.button(text="➕ Yangi paket", callback_data="adm:pkg_add")
    kb.button(text="⬅️ Orqaga", callback_data="adm:menu")
    kb.adjust(1)
    return text, kb.as_markup()


@router.callback_query(F.data == "adm:promopkgs")
async def cb_promopkgs(call: CallbackQuery, db: Database) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    await call.answer()
    text, kb = await _promopkgs_text_and_kb(db)
    await _send_or_edit(call, text, kb)


@router.callback_query(F.data == "adm:pkg_add")
async def cb_pkg_add(call: CallbackQuery, db: Database, state: FSMContext) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    await call.answer()
    await state.set_state(AdminStates.waiting_package_name)
    await _send_or_edit(
        call,
        "🎟 Yangi paket nomini yuboring (masalan: <code>42 lik</code>):\n\nBekor qilish uchun /bekor.",
        back_kb("adm:promopkgs"),
    )


@router.message(AdminStates.waiting_package_name, F.text)
async def got_package_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("❌ Nomi bo'sh bo'lmasin.")
        return
    await state.update_data(package_name=name)
    await state.set_state(AdminStates.waiting_package_price)
    await message.answer(f"💰 Endi <b>{name}</b> narxini (so'mda, faqat raqam) yuboring:")


@router.message(AdminStates.waiting_package_price, F.text)
async def got_package_price(message: Message, db: Database, state: FSMContext) -> None:
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Faqat raqam kiriting.")
        return
    data = await state.get_data()
    name = data.get("package_name", "Paket")
    await state.clear()
    package_id = await db.create_promo_package(name, int(text))
    await message.answer(f"✅ Paket qo'shildi: <b>{name}</b> — {text} so'm")
    text_out, kb = await _package_detail_text_and_kb(db, package_id)
    await message.answer(text_out, reply_markup=kb)


async def _package_detail_text_and_kb(db: Database, package_id: int):
    pkg = await db.get_promo_package(package_id)
    if pkg is None:
        return "❌ Paket topilmadi.", back_kb("adm:promopkgs")
    counts = await db.promo_package_counts(package_id)
    status = "✅ Faol" if pkg["active"] else "🚫 Faolsizlantirilgan"
    text = (
        f"🎟 <b>{pkg['name']}</b>\n\n"
        f"💰 Narxi: <b>{pkg['price']} so'm</b>\n"
        f"✅ Mavjud kodlar: <b>{counts['available']}</b> ta\n"
        f"📤 Ishlatilgan: <b>{counts['used']}</b> ta\n"
        f"📌 Holati: {status}"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Kod qo'shish", callback_data=f"adm:pkg_codes:{package_id}")
    kb.button(text="✏️ Nomini o'zgartirish", callback_data=f"adm:pkg_rename:{package_id}")
    kb.button(text="💰 Narxini o'zgartirish", callback_data=f"adm:pkg_reprice:{package_id}")
    toggle_label = "🚫 Faolsizlantirish" if pkg["active"] else "✅ Faollashtirish"
    kb.button(text=toggle_label, callback_data=f"adm:pkg_toggle:{package_id}")
    kb.button(text="🗑 O'chirish", callback_data=f"adm:pkg_del:{package_id}")
    kb.button(text="⬅️ Orqaga", callback_data="adm:promopkgs")
    kb.adjust(1)
    return text, kb.as_markup()


@router.callback_query(F.data.startswith("adm:pkg:"))
async def cb_pkg_detail(call: CallbackQuery, db: Database) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    package_id = int(call.data.split(":")[-1])
    await call.answer()
    text, kb = await _package_detail_text_and_kb(db, package_id)
    await _send_or_edit(call, text, kb)


@router.callback_query(F.data.startswith("adm:pkg_codes:"))
async def cb_pkg_codes(call: CallbackQuery, db: Database, state: FSMContext) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    package_id = int(call.data.split(":")[-1])
    await call.answer()
    await state.set_state(AdminStates.waiting_package_codes)
    await state.update_data(package_id=package_id)
    await _send_or_edit(
        call,
        "🎟 Yangi promo kodlarni yuboring — har biri alohida qatorda:\n\n"
        "<code>CODE1\nCODE2\nCODE3</code>\n\nBekor qilish uchun /bekor.",
        back_kb(f"adm:pkg:{package_id}"),
    )


@router.message(AdminStates.waiting_package_codes, F.text)
async def got_package_codes(message: Message, db: Database, state: FSMContext) -> None:
    data = await state.get_data()
    package_id = data.get("package_id")
    await state.clear()
    if package_id is None:
        await message.answer("❌ Paket aniqlanmadi. Qaytadan /admin dan urinib ko'ring.")
        return
    lines = [line.strip() for line in message.text.split("\n") if line.strip()]
    if not lines:
        await message.answer("❌ Kodlar topilmadi.")
        return
    added = await db.add_promo_codes(lines, package_id=package_id)
    await message.answer(
        f"✅ {added} ta yangi kod qo'shildi ({len(lines) - added} ta takroriy o'tkazib yuborildi)."
    )
    text, kb = await _package_detail_text_and_kb(db, package_id)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("adm:pkg_rename:"))
async def cb_pkg_rename(call: CallbackQuery, db: Database, state: FSMContext) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    package_id = int(call.data.split(":")[-1])
    await call.answer()
    await state.set_state(AdminStates.waiting_package_rename)
    await state.update_data(package_id=package_id)
    await _send_or_edit(
        call, "✏️ Paketning yangi nomini yuboring:\n\nBekor qilish uchun /bekor.",
        back_kb(f"adm:pkg:{package_id}"),
    )


@router.message(AdminStates.waiting_package_rename, F.text)
async def got_package_rename(message: Message, db: Database, state: FSMContext) -> None:
    data = await state.get_data()
    package_id = data.get("package_id")
    await state.clear()
    name = message.text.strip()
    if package_id is None or not name:
        await message.answer("❌ Xatolik yuz berdi.")
        return
    await db.update_promo_package(package_id, name=name)
    await message.answer(f"✅ Nomi o'zgartirildi: <b>{name}</b>")
    text, kb = await _package_detail_text_and_kb(db, package_id)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("adm:pkg_reprice:"))
async def cb_pkg_reprice(call: CallbackQuery, db: Database, state: FSMContext) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    package_id = int(call.data.split(":")[-1])
    await call.answer()
    await state.set_state(AdminStates.waiting_package_reprice)
    await state.update_data(package_id=package_id)
    await _send_or_edit(
        call, "💰 Paketning yangi narxini (so'mda, faqat raqam) yuboring:\n\nBekor qilish uchun /bekor.",
        back_kb(f"adm:pkg:{package_id}"),
    )


@router.message(AdminStates.waiting_package_reprice, F.text)
async def got_package_reprice(message: Message, db: Database, state: FSMContext) -> None:
    data = await state.get_data()
    package_id = data.get("package_id")
    await state.clear()
    text = message.text.strip()
    if package_id is None or not text.isdigit():
        await message.answer("❌ Faqat raqam kiriting.")
        return
    await db.update_promo_package(package_id, price=int(text))
    await message.answer(f"✅ Narxi o'zgartirildi: <b>{text} so'm</b>")
    text_out, kb = await _package_detail_text_and_kb(db, package_id)
    await message.answer(text_out, reply_markup=kb)


@router.callback_query(F.data.startswith("adm:pkg_toggle:"))
async def cb_pkg_toggle(call: CallbackQuery, db: Database) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    package_id = int(call.data.split(":")[-1])
    pkg = await db.get_promo_package(package_id)
    if pkg is None:
        await call.answer("❌ Topilmadi", show_alert=True)
        return
    await db.set_promo_package_active(package_id, not pkg["active"])
    await call.answer("✅ Holati o'zgartirildi")
    text, kb = await _package_detail_text_and_kb(db, package_id)
    await _send_or_edit(call, text, kb)


@router.callback_query(F.data.startswith("adm:pkg_del:"))
async def cb_pkg_del(call: CallbackQuery, db: Database) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    package_id = int(call.data.split(":")[-1])
    await call.answer()
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Ha, o'chirish", callback_data=f"adm:pkg_del_confirm:{package_id}")
    kb.button(text="⬅️ Bekor qilish", callback_data=f"adm:pkg:{package_id}")
    kb.adjust(1)
    await _send_or_edit(
        call,
        "⚠️ Paket va undagi ishlatilmagan kodlar butunlay o'chiriladi. Rozimisiz?",
        kb.as_markup(),
    )


@router.callback_query(F.data.startswith("adm:pkg_del_confirm:"))
async def cb_pkg_del_confirm(call: CallbackQuery, db: Database) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    package_id = int(call.data.split(":")[-1])
    await db.delete_promo_package(package_id)
    await call.answer("🗑 O'chirildi")
    text, kb = await _promopkgs_text_and_kb(db)
    await _send_or_edit(call, text, kb)


# ---------- Adminlar ----------

async def _admins_text_and_kb(db: Database):
    admins = await db.get_admins()
    kb = InlineKeyboardBuilder()
    lines = ["👥 <b>Adminlar</b>\n"]
    for a in admins:
        role_label = "👑 super" if a["role"] == "super" else "🛡 moderator"
        lines.append(f"• <code>{a['user_id']}</code> — {role_label}")
        kb.button(text=f"🗑 {a['user_id']}", callback_data=f"adm:admin_del:{a['user_id']}")
    kb.button(text="➕ Admin qo'shish", callback_data="adm:admin_add")
    kb.button(text="⬅️ Orqaga", callback_data="adm:menu")
    kb.adjust(1)
    return "\n".join(lines), kb.as_markup()


@router.callback_query(F.data == "adm:admins")
async def cb_admins(call: CallbackQuery, db: Database) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    await call.answer()
    text, kb = await _admins_text_and_kb(db)
    await _send_or_edit(call, text, kb)


@router.callback_query(F.data == "adm:admin_add")
async def cb_admin_add(call: CallbackQuery, db: Database, state: FSMContext) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    await call.answer()
    await state.set_state(AdminStates.waiting_admin_id)
    await _send_or_edit(
        call,
        "👥 Yangi admin Telegram ID'sini yuboring.\n"
        "Moderator sifatida qo'shish uchun: <code>123456789</code>\n"
        "Super-admin sifatida qo'shish uchun: <code>123456789 super</code>\n\n"
        "Bekor qilish uchun /bekor.",
        back_kb("adm:admins"),
    )


@router.message(AdminStates.waiting_admin_id, F.text)
async def got_admin_id(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    parts = message.text.strip().split()
    if not parts or not parts[0].isdigit():
        await message.answer("❌ Telegram ID raqam bo'lishi kerak.")
        return
    uid = int(parts[0])
    role = "super" if len(parts) > 1 and parts[1].lower() == "super" else "moderator"
    await db.add_admin(uid, role)
    await message.answer(f"✅ <code>{uid}</code> — {role} sifatida qo'shildi.")
    text, kb = await _admins_text_and_kb(db)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("adm:admin_del:"))
async def cb_admin_del(call: CallbackQuery, db: Database) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    uid = int(call.data.split(":")[-1])
    if uid == call.from_user.id:
        await call.answer("❌ O'zingizni o'chira olmaysiz.", show_alert=True)
        return
    await db.remove_admin(uid)
    await call.answer("🗑 O'chirildi")
    text, kb = await _admins_text_and_kb(db)
    await _send_or_edit(call, text, kb)


# ---------- Statistika ----------

@router.callback_query(F.data == "adm:stats")
async def cb_stats(call: CallbackQuery, db: Database) -> None:
    if await _role(db, call.from_user.id) != "super":
        await call.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    await call.answer()
    s = await db.get_admin_stats()
    text = (
        "📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{s['users_total']}</b> (faol: {s['users_active']})\n"
        f"⏳ Kutilayotgan to'lovlar: <b>{s['payments_pending']}</b>\n"
        f"💰 Jami to'ldirilgan: <b>{s['total_topup']}</b> so'm\n"
        f"🎟 Promo kodlar — mavjud: <b>{s['promo_available']}</b>, ishlatilgan: <b>{s['promo_used']}</b>\n"
        f"🛡 Adminlar soni: <b>{s['admins_count']}</b>"
    )
    await _send_or_edit(call, text, back_kb())
