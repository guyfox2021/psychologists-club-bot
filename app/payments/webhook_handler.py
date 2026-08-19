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

        if not outcome.verified or outcome.user_id is None:
            return web.Response(status=200)

        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(outcome.user_id)
        if user is None:
            return web.Response(status=200)

        if not outcome.charged:
            # Card verified, but the immediate charge failed -- no access yet.
            # The daily retry job will keep trying automatically.
            await bot.send_message(
                user.telegram_id,
                "⚠️ Картку підтверджено, але списати оплату не вдалося (недостатньо коштів "
                "чи інша причина з боку банку). Ми спробуємо ще раз автоматично, або перевірте "
                "картку і зверніться до адміністратора.",
            )
            return web.Response(status=200)

        settings_repo = SettingsRepository(session)
        bot_settings = await settings_repo.get_or_create()

        if bot_settings.community_chat_id is None:
            logger.warning(
                "Community channel is not configured, cannot grant access to user %s", user.id
            )
            return web.Response(status=200)

        access_service = AccessService(bot)
        invite_link = await access_service.create_invite_link(
            bot_settings.community_chat_id, name=f"user_{user.telegram_id}", member_limit=1
        )

        subscription_repo = SubscriptionRepository(session)
        await subscription_repo.update(user.id, invite_link=invite_link)

        end_text = (
            outcome.subscription_end.strftime("%d.%m.%Y") if outcome.subscription_end else "—"
        )
        await bot.send_message(
            user.telegram_id,
            "🎉 Оплату успішно проведено! Ви отримали доступ до спільноти.\n\n"
            f"🔗 Посилання для вступу: {invite_link}\n\n"
            f"Підписка діє до {end_text}, після чого відбудеться автоматичне продовження. "
            "Скасувати автопродовження можна командою /cancel_subscription.",
        )

    # Monobank requires exactly a plain 200 OK to consider the webhook delivered,
    # otherwise it retries up to 3 times -- no signed acknowledgement body needed.
    return web.Response(status=200)
