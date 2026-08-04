from pydantic import BaseModel, ConfigDict, Field


class MonobankInvoiceCreateResponse(BaseModel):
    """Response from POST /api/merchant/invoice/create."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    invoice_id: str = Field(alias="invoiceId")
    page_url: str = Field(alias="pageUrl")


class MonobankWalletData(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    card_token: str | None = Field(default=None, alias="cardToken")
    wallet_id: str | None = Field(default=None, alias="walletId")
    status: str | None = None


class MonobankPaymentInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    masked_pan: str | None = Field(default=None, alias="maskedPan")
    approval_code: str | None = Field(default=None, alias="approvalCode")
    payment_system: str | None = Field(default=None, alias="paymentSystem")


class MonobankInvoiceStatus(BaseModel):
    """Shared shape for GET /invoice/status responses, webHookUrl callbacks, and the
    wallet/payment (charge-by-token) response -- Monobank uses the same status
    vocabulary across all of these."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    invoice_id: str | None = Field(default=None, alias="invoiceId")
    status: str
    amount: int | None = None
    ccy: int | None = None
    reference: str | None = None
    failure_reason: str | None = Field(default=None, alias="failureReason")
    modified_date: str | None = Field(default=None, alias="modifiedDate")
    wallet_data: MonobankWalletData | None = Field(default=None, alias="walletData")
    payment_info: MonobankPaymentInfo | None = Field(default=None, alias="paymentInfo")

    @property
    def is_success(self) -> bool:
        return self.status == "success"

    @property
    def is_final_failure(self) -> bool:
        return self.status in {"failure", "expired", "reversed"}
