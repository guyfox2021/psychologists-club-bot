import enum


class UserRoleCode(str, enum.Enum):
    STUDENT = "student"
    PSYCHOLOGIST = "psychologist"
    SUPERVISOR = "supervisor"


class ApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEED_MORE_DOCS = "need_more_docs"


class PaymentStatus(str, enum.Enum):
    WAITING = "waiting"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PaymentTransactionType(str, enum.Enum):
    AUTHORIZATION = "authorization"
    TRIAL_CHARGE = "trial_charge"
    RENEWAL_CHARGE = "renewal_charge"


class SubscriptionStatus(str, enum.Enum):
    WAITING = "waiting"
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationType(str, enum.Enum):
    REMINDER_3D = "reminder_3d"
    REMINDER_1D = "reminder_1d"
    PAYMENT_FAILED = "payment_failed"
    ACCESS_RESTORED = "access_restored"
    APPLICATION_STATUS = "application_status"
    BROADCAST = "broadcast"


class NotificationStatus(str, enum.Enum):
    SENT = "sent"
    FAILED = "failed"


class KarmaReactionType(str, enum.Enum):
    HELPED = "helped"  # 🤝
    NOT_HELPED = "not_helped"  # 👎
