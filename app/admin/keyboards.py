from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.admin.callback_data import (
    AdminChangeRoleCB,
    AdminReviewCB,
    BroadcastCB,
    SettingsAdminCB,
    UserAdminCB,
)
from app.database.models import Role, User


def application_review_keyboard(application_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Схвалити", callback_data=AdminReviewCB(action="approve", application_id=application_id)
    )
    builder.button(
        text="❌ Відхилити", callback_data=AdminReviewCB(action="reject", application_id=application_id)
    )
    builder.button(
        text="📎 Запросити документи",
        callback_data=AdminReviewCB(action="request_docs", application_id=application_id),
    )
    builder.button(
        text="🔄 Невідповідний статус",
        callback_data=AdminReviewCB(action="wrong_status", application_id=application_id),
    )
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def user_actions_keyboard(user: User) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if user.is_banned:
        builder.button(text="✅ Розбанити", callback_data=UserAdminCB(action="unban", user_id=user.id))
    else:
        builder.button(text="🚫 Забанити", callback_data=UserAdminCB(action="ban", user_id=user.id))

    if user.is_admin:
        builder.button(
            text="👑 Зняти адміна", callback_data=UserAdminCB(action="remove_admin", user_id=user.id)
        )
    else:
        builder.button(
            text="👑 Зробити адміном", callback_data=UserAdminCB(action="make_admin", user_id=user.id)
        )

    builder.button(
        text="🎓 Змінити роль", callback_data=UserAdminCB(action="change_role", user_id=user.id)
    )
    builder.adjust(2, 1)
    return builder.as_markup()


def role_change_keyboard(user_id: int, roles: list[Role]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for role in roles:
        builder.button(
            text=role.label_uk, callback_data=AdminChangeRoleCB(user_id=user_id, role_code=role.code)
        )
    builder.adjust(1)
    return builder.as_markup()


def broadcast_audience_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Усі", callback_data=BroadcastCB(audience="all"))
    builder.button(text="Студенти", callback_data=BroadcastCB(audience="student"))
    builder.button(text="Психологи", callback_data=BroadcastCB(audience="psychologist"))
    builder.button(text="Супервізори", callback_data=BroadcastCB(audience="supervisor"))
    builder.adjust(1)
    return builder.as_markup()


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Тріал (днів)", callback_data=SettingsAdminCB(action="trial_days"))
    builder.button(text="💵 Ціна підписки", callback_data=SettingsAdminCB(action="price"))
    builder.button(
        text="📆 Тривалість підписки (днів)", callback_data=SettingsAdminCB(action="duration")
    )
    builder.button(text="🔔 Нагадування (днів до)", callback_data=SettingsAdminCB(action="reminders"))
    builder.button(text="📢 Канал спільноти", callback_data=SettingsAdminCB(action="channel"))
    builder.adjust(1)
    return builder.as_markup()
