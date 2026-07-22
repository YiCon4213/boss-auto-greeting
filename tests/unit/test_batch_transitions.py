import pytest

from agent_app.domain.enums import BatchStatus
from agent_app.domain.transitions import (
    InvalidBatchTransition,
    next_batch_status,
)


def test_batch_allows_collection_path():
    assert (
        next_batch_status(BatchStatus.DRAFT, "start_collection")
        is BatchStatus.COLLECTING
    )
    assert (
        next_batch_status(BatchStatus.COLLECTING, "collection_complete")
        is BatchStatus.COLLECTED
    )


def test_batch_rejects_execution_before_approval():
    with pytest.raises(InvalidBatchTransition):
        next_batch_status(BatchStatus.COLLECTED, "execute")


def test_batch_supports_explicit_pause_and_resume_paths():
    assert next_batch_status(BatchStatus.COLLECTING, "pause") is BatchStatus.PAUSED
    assert (
        next_batch_status(BatchStatus.PAUSED, "resume_collection")
        is BatchStatus.COLLECTING
    )
    assert (
        next_batch_status(BatchStatus.EXECUTING, "security_pause")
        is BatchStatus.PAUSED_SECURITY
    )
    assert (
        next_batch_status(BatchStatus.PAUSED_SECURITY, "resume_execution")
        is BatchStatus.EXECUTING
    )
