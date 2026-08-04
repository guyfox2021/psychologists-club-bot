from aiogram.fsm.state import State, StatesGroup


class DocumentUploadStates(StatesGroup):
    uploading = State()
