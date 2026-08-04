from aiogram.fsm.state import State, StatesGroup


class QuestionnaireStates(StatesGroup):
    role = State()
    first_name = State()
    last_name = State()
    phone = State()
    email = State()
    city = State()
