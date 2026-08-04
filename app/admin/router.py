from aiogram import Router

from app.admin.handlers.applications import applications_router
from app.admin.handlers.broadcast import broadcast_router
from app.admin.handlers.payments import payments_router
from app.admin.handlers.settings import settings_router
from app.admin.handlers.stats import stats_router
from app.admin.handlers.subscriptions import subscriptions_router
from app.admin.handlers.users import users_router

admin_router = Router(name="admin")
admin_router.include_router(applications_router)
admin_router.include_router(users_router)
admin_router.include_router(subscriptions_router)
admin_router.include_router(payments_router)
admin_router.include_router(broadcast_router)
admin_router.include_router(settings_router)
admin_router.include_router(stats_router)
