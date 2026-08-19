from aiogram.filters.callback_data import CallbackData


class StartCB(CallbackData, prefix="start"):
    action: str  # verify | faq | contact_admin | back


class RoleCB(CallbackData, prefix="role"):
    code: str  # student | psychologist | supervisor


class DocumentsCB(CallbackData, prefix="docs"):
    action: str  # done


class PaymentCB(CallbackData, prefix="pay"):
    action: str  # confirm | retry_later | cancel_confirm | cancel_abort
