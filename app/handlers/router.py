from aiogram import Router

from app.handlers.chat_member import router as chat_member_router
from app.handlers.common import router as common_router
from app.handlers.documents import router as documents_router
from app.handlers.karma import router as karma_router
from app.handlers.link_moderation import router as link_moderation_router
from app.handlers.payment_flow import router as payment_flow_router
from app.handlers.questionnaire import router as questionnaire_router
from app.handlers.start import router as start_router

user_router = Router(name="user")
user_router.include_router(start_router)
user_router.include_router(common_router)
user_router.include_router(questionnaire_router)
user_router.include_router(documents_router)
user_router.include_router(payment_flow_router)
user_router.include_router(chat_member_router)
# Must run before karma_router: it either deletes a link-violating message
# outright, or defers via SkipHandler so karma tracking still sees the
# message normally -- see app/handlers/link_moderation.py for the full logic.
user_router.include_router(link_moderation_router)
user_router.include_router(karma_router)
