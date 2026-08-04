import json
import logging

from aiohttp import web

from app.config import Settings
from app.database.engine import session_scope
from app.database.repositories import SettingsRepository, SubscriptionRepository, UserRepository
from app.payments.monobank_client import MonobankClient
from app.payments.monobank_schemas import MonobankInvoiceStatus
from app.payments.payment_service import PaymentService
from app.services.access_service import AccessService

logger = logging.getLogger(__name__)


async def monobank_webhook_handler(request: web.Request) -> web.Response:
    settings: Settings = request.app["settings"]
    bot = request.app["bot"]

    raw_body = await request.read()
    signature = request.headers.get("X-Sign", "")

    client = MonobankClient(settings)
    if not signature or not await client.verify_webhook_signature(raw_body, signature):
        logger.warning("Monobank webhook: signature mismatch or missing X-Sign header")
        return web.Response(status=403)

    try:
        payload = json.loads(raw_body)
        callback = MonobankInvoiceStatus.model_validate(payload)
    except (ValueError, TypeError):
        logger.exception("Monobank webhook: could not parse payload: %s", raw_body)
        return web.Response(status=400)

    async with session_scope() as session:
        payment_service = PaymentService(session, client)
        outcome = await payment_service.handle_authorization_result(callback)

        if outcome.success and outcome.user_id is not None:
            settings_repo = SettingsRepository(session)
            bot_settings = await settings_repo.get_or_create()
            user_repo = UserRepository(session)
            user = await user_repo.get_by_id(outcome.user_id)

            if user is not None and bot_settings.community_chat_id is not None:
                access_service = AccessService(bot)
                invite_link = await access_service.create_invite_link(
                    bot_settings.community_chat_id,
                    name=f"user_{user.telegram_id}",
                    member_limit=1,
                )

                subscription_repo = SubscriptionRepository(session)
                await subscription_repo.update(user.id, invite_link=invite_link)

                trial_end_text = (
                    outcome.trial_end.strftime("%d.%m.%Y") if outcome.trial_end else "—"
                )
                await bot.send_message(
                    user.telegram_id,
                    "🎉 Спосіб оплати підтверджено! Розпочався ваш безкоштовний пробний період.\n\n"
                    f"🔗 Посилання для вступу до спільноти: {invite_link}\n\n"
                    f"Оплата підключиться автоматично {trial_end_text}, "
                    "після завершення пробного періоду.",
                )
            elif user is not None:
                logger.warning(
                    "Community channel is not configured, cannot grant access to user %s",
                    user.id,
                )

    # Monobank requires exactly a plain 200 OK to consider the webhook delivered,
    # otherwise it retries up to 3 times -- no signed acknowledgement body needed.
    return web.Response(status=200)
