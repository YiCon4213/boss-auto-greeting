from enum import StrEnum


class BatchStatus(StrEnum):
    DRAFT = "draft"
    COLLECTING = "collecting"
    COLLECTED = "collected"
    ANALYZING = "analyzing"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    PAUSED = "paused"
    PAUSED_SECURITY = "paused_security"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryStatus(StrEnum):
    APPROVED = "approved"
    LOCATING = "locating"
    REVALIDATING = "revalidating"
    SENDING = "sending"
    SENT = "sent"
    ALREADY_CONTACTED = "already_contacted"
    UNAVAILABLE = "unavailable"
    IDENTITY_MISMATCH = "identity_mismatch"
    SEND_FAILED = "send_failed"
    CANCELLED = "cancelled"
