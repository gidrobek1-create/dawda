from aiogram.fsm.state import State, StatesGroup


class TopUpStates(StatesGroup):
    waiting_photo = State()
    waiting_amount = State()


class AdminRejectStates(StatesGroup):
    waiting_reason = State()


class AdminStates(StatesGroup):
    waiting_card = State()
    waiting_ref_bonus = State()
    waiting_pay_limit = State()
    waiting_channel = State()
    waiting_admin_id = State()
    # promo paketlar
    waiting_package_name = State()
    waiting_package_price = State()
    waiting_package_rename = State()
    waiting_package_reprice = State()
    waiting_package_codes = State()
