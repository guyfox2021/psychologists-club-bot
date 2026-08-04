from aiogram.fsm.state import State, StatesGroup


class ContactAdminStates(StatesGroup):
    message = State()
