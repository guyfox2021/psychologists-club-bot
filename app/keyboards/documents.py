from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.callback_data import DocumentsCB


def documents_upload_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Завершити завантаження", callback_data=DocumentsCB(action="done"))
    return builder.as_markup()
