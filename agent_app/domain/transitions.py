from agent_app.domain.enums import BatchStatus


class InvalidBatchTransition(ValueError):
    def __init__(self, current: BatchStatus, event: str):
        self.current = current
        self.event = event
        super().__init__(f"Cannot apply {event!r} while batch is {current.value!r}")


TRANSITIONS: dict[tuple[BatchStatus, str], BatchStatus] = {
    (BatchStatus.DRAFT, "start_collection"): BatchStatus.COLLECTING,
    (BatchStatus.COLLECTING, "collection_complete"): BatchStatus.COLLECTED,
    (BatchStatus.COLLECTED, "start_analysis"): BatchStatus.ANALYZING,
    (BatchStatus.ANALYZING, "analysis_complete"): BatchStatus.AWAITING_APPROVAL,
    (BatchStatus.COLLECTED, "skip_analysis"): BatchStatus.AWAITING_APPROVAL,
    (BatchStatus.AWAITING_APPROVAL, "approve"): BatchStatus.APPROVED,
    (BatchStatus.APPROVED, "execute"): BatchStatus.EXECUTING,
    (BatchStatus.EXECUTING, "complete"): BatchStatus.COMPLETED,
    (BatchStatus.COLLECTING, "pause"): BatchStatus.PAUSED,
    (BatchStatus.ANALYZING, "pause"): BatchStatus.PAUSED,
    (BatchStatus.EXECUTING, "pause"): BatchStatus.PAUSED,
    (BatchStatus.COLLECTING, "security_pause"): BatchStatus.PAUSED_SECURITY,
    (BatchStatus.EXECUTING, "security_pause"): BatchStatus.PAUSED_SECURITY,
    (BatchStatus.PAUSED, "resume_collection"): BatchStatus.COLLECTING,
    (BatchStatus.PAUSED, "resume_analysis"): BatchStatus.ANALYZING,
    (BatchStatus.PAUSED, "resume_execution"): BatchStatus.EXECUTING,
    (BatchStatus.PAUSED_SECURITY, "resume_execution"): BatchStatus.EXECUTING,
}

for cancellable in (
    BatchStatus.DRAFT,
    BatchStatus.COLLECTING,
    BatchStatus.COLLECTED,
    BatchStatus.ANALYZING,
    BatchStatus.AWAITING_APPROVAL,
    BatchStatus.APPROVED,
    BatchStatus.EXECUTING,
    BatchStatus.PAUSED,
    BatchStatus.PAUSED_SECURITY,
):
    TRANSITIONS[(cancellable, "cancel")] = BatchStatus.CANCELLED

for fallible in (
    BatchStatus.COLLECTING,
    BatchStatus.COLLECTED,
    BatchStatus.ANALYZING,
    BatchStatus.EXECUTING,
    BatchStatus.PAUSED,
    BatchStatus.PAUSED_SECURITY,
):
    TRANSITIONS[(fallible, "fail")] = BatchStatus.FAILED


def next_batch_status(current: BatchStatus, event: str) -> BatchStatus:
    try:
        return TRANSITIONS[(current, event)]
    except KeyError as error:
        raise InvalidBatchTransition(current, event) from error


def available_batch_actions(current: BatchStatus) -> list[str]:
    return [event for (status, event) in TRANSITIONS if status is current]
