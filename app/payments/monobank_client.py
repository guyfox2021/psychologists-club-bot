import asyncio
import base64
import hashlib
import logging
import time
from typing import Any

import aiohttp
import ecdsa

from app.config import Settings
from app.payments.monobank_schemas import MonobankInvoiceCreateResponse, MonobankInvoiceStatus

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 1.5
_REQUEST_TIMEOUT_SECONDS = 30
_PUBKEY_CACHE_SECONDS = 3600

# Verified against https://monobank.ua/en/api-docs/acquiring (July 2026):
#   - POST /api/merchant/invoice/create (paymentType="verification", amount=0,
#     saveCardData.saveCard=true) tokenizes a card with a genuine zero-charge hold --
#     no verification-amount-then-refund workaround needed, unlike the WayForPay
#     integration this replaces.
#   - POST /api/merchant/wallet/payment charges a previously saved cardToken
#     synchronously (initiationKind="merchant" for our scheduler-driven charges).
#   - Webhook (`webHookUrl`) payload has the same shape as GET /invoice/status and
#     is signed via the `X-Sign` header: ECDSA/SHA-256 over the raw request body,
#     verified with the public key from GET /api/merchant/pubkey (base64(PEM(SPKI))).
#   - Monobank expects a plain 200 OK back from the webhook -- no signed ack body
#     (unlike WayForPay).

_CURRENCY_CODES = {"UAH": 980}


class MonobankError(Exception):
    """Raised when Monobank rejects a request or a network call keeps failing."""


class MonobankClient:
    def __init__(self, settings: Settings) -> None:
        self._token = settings.monobank_token
        self._api_url = settings.monobank_api_url.rstrip("/")
        self._webhook_url = settings.monobank_webhook_url
        self._merchant_domain = settings.monobank_merchant_domain
        self._pubkey_cache: tuple[float, ecdsa.VerifyingKey] | None = None

    @staticmethod
    def currency_code(currency: str) -> int:
        try:
            return _CURRENCY_CODES[currency.upper()]
        except KeyError as error:
            raise MonobankError(f"Unsupported currency for Monobank: {currency}") from error

    def _headers(self) -> dict[str, str]:
        return {"X-Token": self._token}

    async def create_verification_invoice(
        self, order_reference: str, client_email: str | None = None
    ) -> MonobankInvoiceCreateResponse:
        """Create a zero-charge hosted invoice that tokenizes the user's card."""
        payload: dict[str, Any] = {
            "amount": 0,
            "paymentType": "verification",
            "saveCardData": {"saveCard": True, "walletId": order_reference},
            "webHookUrl": self._webhook_url,
            "validity": 3600,
        }
        if client_email:
            payload["merchantPaymInfo"] = {"reference": order_reference, "destination": client_email}

        data = await self._request("POST", "/api/merchant/invoice/create", json=payload)
        return MonobankInvoiceCreateResponse.model_validate(data)

    async def charge_by_token(
        self, card_token: str, amount: float, currency: str = "UAH"
    ) -> MonobankInvoiceStatus:
        """Charge a previously tokenized card without any user interaction."""
        payload: dict[str, Any] = {
            "cardToken": card_token,
            "amount": round(amount * 100),
            "ccy": self.currency_code(currency),
            "initiationKind": "merchant",
        }
        data = await self._request("POST", "/api/merchant/wallet/payment", json=payload)
        return MonobankInvoiceStatus.model_validate(data)

    async def get_invoice_status(self, invoice_id: str) -> MonobankInvoiceStatus:
        data = await self._request(
            "GET", "/api/merchant/invoice/status", params={"invoiceId": invoice_id}
        )
        return MonobankInvoiceStatus.model_validate(data)

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._api_url}{path}"
        last_error: Exception | None = None

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.request(
                        method,
                        url,
                        json=json,
                        params=params,
                        headers=self._headers(),
                        timeout=aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT_SECONDS),
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()
                logger.info("Monobank %s %s response: %s", method, path, data)
                return data
            except (aiohttp.ClientError, TimeoutError) as error:
                last_error = error
                logger.warning(
                    "Monobank %s %s failed (attempt %s/%s): %s",
                    method,
                    path,
                    attempt,
                    _MAX_ATTEMPTS,
                    error,
                )
                if attempt < _MAX_ATTEMPTS:
                    await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)

        raise MonobankError(f"Monobank {method} {path} failed after {_MAX_ATTEMPTS} attempts") from last_error

    async def _get_public_key(self) -> ecdsa.VerifyingKey:
        now = time.monotonic()
        if self._pubkey_cache is not None:
            cached_at, key = self._pubkey_cache
            if now - cached_at < _PUBKEY_CACHE_SECONDS:
                return key

        data = await self._request("GET", "/api/merchant/pubkey")
        pem_bytes = base64.b64decode(data["key"])
        key = ecdsa.VerifyingKey.from_pem(pem_bytes.decode())
        self._pubkey_cache = (now, key)
        return key

    async def verify_webhook_signature(self, raw_body: bytes, signature_b64: str) -> bool:
        try:
            public_key = await self._get_public_key()
            signature = base64.b64decode(signature_b64)
            return public_key.verify(
                signature, raw_body, sigdecode=ecdsa.util.sigdecode_der, hashfunc=hashlib.sha256
            )
        except (ecdsa.BadSignatureError, ValueError, KeyError) as error:
            logger.warning("Monobank webhook signature verification failed: %s", error)
            return False
