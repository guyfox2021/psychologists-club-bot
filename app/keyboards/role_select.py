from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import Role
from app.database.models.enums import UserRoleCode
from app.keyboards.callback_data import RoleCB

# `Role.label_uk` stays plain (no emoji) since it's also used to build the
# Telegram member tag, and tags don't allow emoji. The button-only emoji and
# display order live here instead.
_ROLE_EMOJI = {
    UserRoleCode.STUDENT.value: "🎓",
    UserRoleCode.PSYCHOLOGIST_STARTER.value: "🌱",
    UserRoleCode.PSYCHOLOGIST.value: "🧠",
    UserRoleCode.SUPERVISOR.value: "👨‍🏫",
}
_ROLE_ORDER = list(_ROLE_EMOJI.keys())


def role_select_keyboard(roles: list[Role]) -> InlineKeyboardMarkup:
    ordered_roles = sorted(
        roles,
        key=lambda role: _ROLE_ORDER.index(role.code) if role.code in _ROLE_ORDER else len(_ROLE_ORDER),
    )
    builder = InlineKeyboardBuilder()
    for role in ordered_roles:
        emoji = _ROLE_EMOJI.get(role.code)
        text = f"{emoji} {role.label_uk}" if emoji else role.label_uk
        builder.button(text=text, callback_data=RoleCB(code=role.code))
    builder.adjust(1)
    return builder.as_markup()
