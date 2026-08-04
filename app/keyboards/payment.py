from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.callback_data import PaymentCB, StartCB


def payment_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Підтвердити спосіб оплати", callback_data=PaymentCB(action="confirm"))
    return builder.as_markup()


def invoice_link_keyboard(invoice_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Перейти до оплати", url=invoice_url)
    return builder.as_markup()


def payment_failed_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатити", callback_data=PaymentCB(action="confirm"))
    builder.button(text="🔄 Оновити картку", callback_data=PaymentCB(action="confirm"))
    builder.button(text="📞 Зв'язатися з адміністратором", callback_data=StartCB(action="contact_admin"))
    builder.button(text="⏳ Спробувати пізніше", callback_data=PaymentCB(action="retry_later"))
    builder.adjust(2, 1, 1)
    return builder.as_markup()
