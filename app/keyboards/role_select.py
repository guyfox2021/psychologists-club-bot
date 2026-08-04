from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import Role
from app.keyboards.callback_data import RoleCB


def role_select_keyboard(roles: list[Role]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for role in roles:
        builder.button(text=role.label_uk, callback_data=RoleCB(code=role.code))
    builder.adjust(1)
    return builder.as_markup()
