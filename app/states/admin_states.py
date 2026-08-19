from aiogram.fsm.state import State, StatesGroup


class ApplicationReviewStates(StatesGroup):
    reject_reason = State()
    more_docs_comment = State()
    wrong_status_comment = State()


class BroadcastStates(StatesGroup):
    message = State()


class SettingsStates(StatesGroup):
    trial_days = State()
    price = State()
    duration = State()
    reminders = State()
    channel = State()
