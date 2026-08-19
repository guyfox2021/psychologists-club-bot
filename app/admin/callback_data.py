from aiogram.filters.callback_data import CallbackData


class AdminReviewCB(CallbackData, prefix="admrev"):
    action: str  # approve | reject | request_docs | wrong_status
    application_id: int


class UserAdminCB(CallbackData, prefix="usradm"):
    action: str  # ban | unban | make_admin | remove_admin | change_role
    user_id: int


class AdminChangeRoleCB(CallbackData, prefix="usrrole"):
    user_id: int
    role_code: str


class BroadcastCB(CallbackData, prefix="bcast"):
    audience: str  # all | student | psychologist | supervisor


class SettingsAdminCB(CallbackData, prefix="setadm"):
    action: str  # trial_days | price | duration | reminders | channel | role_prices


class RolePriceCB(CallbackData, prefix="roleprice"):
    role_id: int
