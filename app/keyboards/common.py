from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.callback_data import StartCB


def welcome_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Почати перевірку", callback_data=StartCB(action="verify"))
    builder.button(text="❓ FAQ", callback_data=StartCB(action="faq"))
    builder.button(text="📞 Зв'язатися з адміністратором", callback_data=StartCB(action="contact_admin"))
    builder.adjust(1)
    return builder.as_markup()


def back_to_start_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=StartCB(action="back").pack())
    )
    return builder.as_markup()
